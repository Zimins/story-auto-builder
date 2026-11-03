import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "story_map.py"
BOARD = (ROOT / "tests" / "fixtures" / "board.xml").read_text(encoding="utf-8")
ADOPT = '<sticky id="2:46" x="632" y="280" color="STICKY_YELLOW" author="" width="240" height="240">[ai] 결제: 카드 결제 실패 시 재시도 안내</sticky>'


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], check=True, capture_output=True, text=True).stdout

    def ingest(self, xml):
        f = self.dir / "b.xml"
        f.write_text(xml, encoding="utf-8")
        return json.loads(self.run_cli("ingest", "--xml", str(f), "--state-dir", str(self.dir / "s")))

    def state(self):
        return json.loads((self.dir / "s" / "state.json").read_text())

    def test_maps_layers_and_build_order(self):
        s = self.ingest(BOARD)
        units = self.state()["units"]
        self.assertEqual([(u["step"], u["release"]) for u in units], [
            ("상품 검색", "Release 1"), ("장바구니 담기", "Release 1"), ("결제", "Release 1"),
            ("주문 확인", "Release 1"), ("상품 검색", "Release 2"), ("결제", "Release 2")])
        self.assertEqual(units[2]["goal"], "주문을 완료한다")
        self.assertEqual(units[1]["goal"], "원하는 상품을 찾는다")
        self.assertEqual(units[0]["user"], "구매 고객")
        self.assertEqual(s["openProposals"][0]["id"], "2:46")
        self.assertEqual(s["ignoredNonStickies"], 2)

    def test_only_an_unchanged_read_is_ready(self):
        self.assertFalse(self.ingest(BOARD)["readyToBuild"])
        self.assertTrue(self.ingest(BOARD)["readyToBuild"])
        self.assertFalse(self.ingest(BOARD.replace("카드 결제", "카드/계좌 결제"))["readyToBuild"])

    def test_moving_a_card_within_its_column_is_not_a_change(self):
        self.ingest(BOARD)
        self.assertFalse(self.ingest(BOARD.replace('id="1:18" x="0" y="600"', 'id="1:18" x="10" y="610"'))["changed"])

    def test_shipped_unit_with_new_text_needs_rework(self):
        self.ingest(BOARD)
        uid = self.state()["units"][2]["id"]
        self.run_cli("set-status", uid, "pr_open", "--pr", "http://pr/1", "--state-dir", str(self.dir / "s"))
        self.ingest(BOARD.replace("카드 결제", "카드/계좌 결제"))
        u = next(u for u in self.state()["units"] if u["id"] == uid)
        self.assertEqual((u["status"], u["pr"]), ("changed", "http://pr/1"))

    def test_removed_shipped_unit_is_kept_as_removed(self):
        self.ingest(BOARD)
        uid = self.state()["units"][3]["id"]
        self.run_cli("set-status", uid, "done", "--state-dir", str(self.dir / "s"))
        self.ingest(BOARD.replace('<sticky id="1:48" x="932" y="40" color="STICKY_YELLOW" author="" width="240" height="240">주문 완료 화면</sticky>', ""))
        self.assertEqual(next(u for u in self.state()["units"] if u["id"] == uid)["status"], "removed")

    def test_adopted_proposal_loses_prefix(self):
        self.ingest(BOARD)
        moved = BOARD.replace('<sticky id="2:46" x="32" y="40" color="STICKY_ORANGE" author="" width="240" height="240">[ai] 결제: 카드 결제 실패 시 재시도 안내</sticky>', "")
        moved = moved.replace('<sticky id="1:44"', ADOPT + '\n<sticky id="1:44"')
        self.ingest(moved)
        st = self.state()
        self.assertEqual(st["proposals"]["2:46"]["status"], "adopted")
        self.assertIn("결제: 카드 결제 실패 시 재시도 안내", next(u for u in st["units"] if "2:46" in u["detailIds"])["details"])

    def test_deleted_proposal_is_remembered_as_rejected(self):
        self.ingest(BOARD)
        s = self.ingest(BOARD.replace('<sticky id="2:46" x="32" y="40" color="STICKY_ORANGE" author="" width="240" height="240">[ai] 결제: 카드 결제 실패 시 재시도 안내</sticky>', ""))
        self.assertEqual(s["rejectedProposals"], ["[ai] 결제: 카드 결제 실패 시 재시도 안내"])

    def test_proposal_mid_move_stays_open_then_adopts(self):
        self.ingest(BOARD)
        sticky = '<sticky id="2:46" x="32" y="40" color="STICKY_ORANGE" author="" width="240" height="240">[ai] 결제: 카드 결제 실패 시 재시도 안내</sticky>'
        without = BOARD.replace(sticky, "")
        self.ingest(without.replace("</canvas>", sticky + "</canvas>"))
        self.assertEqual(self.state()["proposals"]["2:46"]["status"], "open")
        self.ingest(without.replace('<sticky id="1:44"', ADOPT + '\n<sticky id="1:44"'))
        self.assertEqual(self.state()["proposals"]["2:46"]["status"], "adopted")

    def test_new_proposal_does_not_delay_a_build(self):
        self.ingest(BOARD)
        extra = '<sticky id="2:99" x="300" y="40" color="STICKY_ORANGE" author="" width="240" height="240">[ai] 새 제안</sticky></section>\n  <shape-with-text'
        self.assertTrue(self.ingest(BOARD.replace("</section>\n  <shape-with-text", extra))["readyToBuild"])

    def test_double_escaped_text_and_custom_colour(self):
        s = self.ingest(BOARD.replace("</canvas>",
            '<sticky id="9:1" x="0" y="3000" color="CUSTOM" author="" width="240" height="240">A &amp;amp; B &amp;lt;태그&amp;gt;</sticky></canvas>'))
        self.assertEqual(s["warnings"][0]["text"], "A & B <태그>")
        self.assertFalse(self.ingest(BOARD.replace("</canvas>",
            '<sticky id="9:1" x="0" y="3000" color="CUSTOM" author="" width="240" height="240">x</sticky></canvas>'))["readyToBuild"])

    def test_map_wrapped_in_a_plain_section_still_slices(self):
        wrapped = BOARD.replace('<canvas id="0:1" name="Page 1" x="0" y="0" width="0" height="0">',
                                '<canvas id="0:1" name="Page 1" x="0" y="0" width="0" height="0"><section id="7:1" name="Story Map" x="100" y="100" width="9" height="9">')
        wrapped = wrapped.replace("</canvas>", "</section></canvas>")
        self.ingest(wrapped)
        self.assertEqual(self.state()["units"][0]["release"], "Release 1")


if __name__ == "__main__":
    unittest.main()
