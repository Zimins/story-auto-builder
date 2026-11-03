#!/usr/bin/env python3
"""Turn a FigJam `get_figjam` XML dump into a user story map and implementation units.

Commands:
  ingest --xml FILE [--state-dir DIR]     Parse the board, diff it, update state, print a JSON summary.
  set-status UNIT_ID STATUS [--pr URL] [--note TEXT] [--state-dir DIR]
  show [--state-dir DIR]                  Print the current summary without touching the board.

State lives in .story-map/ (see references/state.md). Standard library only.
"""
import argparse
import hashlib
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_CONFIG = {
    "colors": {
        "STICKY_VIOLET": "user",
        "STICKY_BLUE": "goal",
        "STICKY_GREEN": "step",
        "STICKY_YELLOW": "detail",
    },
    "aiSection": "AI 제안",
    "aiColor": "STICKY_ORANGE",
    "releasePattern": r"(?i)^\s*(mvp|walking\s*skeleton|release|slice|r\d|v\d|릴리[즈스]|슬라이스)",
}
UNSLICED = "미분류"
AI_PREFIX = re.compile(r"(?i)^\s*\[ai\]\s*")
OPEN_STATUSES = {"pending", "changed"}
SHIPPED_STATUSES = {"in_progress", "pr_open", "committed", "done"}
ALL_STATUSES = OPEN_STATUSES | SHIPPED_STATUSES | {"failed", "removed"}


def clean_text(raw):
    """get_figjam escapes sticky text twice; ElementTree undoes only the first layer."""
    return html.unescape(raw or "").strip()


def walk(el, ox, oy, section, out):
    """Flatten the tree into absolute coordinates, since section children are relative."""
    for child in el:
        x, y = ox + float(child.get("x", 0)), oy + float(child.get("y", 0))
        if child.tag == "section":
            sec = {"id": child.get("id"), "name": clean_text(child.get("name")), "y": y,
                   "parent": section["id"] if section else None}
            out["sections"].append(sec)
            walk(child, x, y, sec, out)
        elif child.tag == "sticky":
            out["stickies"].append({
                "id": child.get("id"), "text": clean_text(child.text), "color": child.get("color"),
                "x": x, "y": y, "w": float(child.get("width", 240)), "h": float(child.get("height", 240)),
                "section": section,
            })
        else:
            if child.tag in ("shape-with-text", "text"):
                out["ignored"] += 1
            walk(child, x, y, section, out)


def section_chain(section, by_id):
    while section:
        yield section
        section = by_id.get(section["parent"])


def overlap(a, b):
    return min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])


def center(n):
    return n["x"] + n["w"] / 2


def owner(node, candidates):
    """The last candidate starting at or left of the node's center: a goal spans the steps until the next goal."""
    found = None
    for c in candidates:
        if c["x"] <= center(node):
            found = c
    return found


def brief(n):
    return {"id": n["id"], "text": n["text"]}


def build_map(xml_text, cfg):
    root = ET.fromstring(xml_text)
    flat = {"sections": [], "stickies": [], "ignored": 0}
    walk(root, 0, 0, None, flat)
    by_section = {s["id"]: s for s in flat["sections"]}
    release_re = re.compile(cfg["releasePattern"])

    kinds = {"user": [], "goal": [], "step": [], "detail": []}
    proposals, warnings, ai_section = [], [], None
    for s in flat["sections"]:
        if s["name"] == cfg["aiSection"]:
            ai_section = s["id"]

    for st in flat["stickies"]:
        chain = list(section_chain(st["section"], by_section))
        if any(s["name"] == cfg["aiSection"] for s in chain):
            proposals.append(brief(st))
            continue
        kind = cfg["colors"].get(st["color"])
        if kind is None:
            reason = ("AI 제안 색이지만 섹션 밖에 있음: 채택하려면 세부사항 색으로 바꾸세요"
                      if st["color"] == cfg["aiColor"] else f"규칙에 없는 색 {st['color']}")
            warnings.append({"id": st["id"], "text": st["text"], "reason": reason})
            continue
        release = next((s for s in chain if release_re.search(s["name"])), None)
        st["release"] = release
        st["text"] = AI_PREFIX.sub("", st["text"])  # adopted proposals become plain requirements
        kinds[kind].append(st)

    for k in kinds:
        kinds[k].sort(key=lambda n: (n["x"], n["y"]))

    placed = set()
    for d in kinds["detail"]:
        best = max(kinds["step"], key=lambda s: overlap(d, s), default=None)
        if best is None or overlap(d, best) <= 0:
            warnings.append({"id": d["id"], "text": d["text"], "reason": "위에 과정 카드가 없음: 구현에서 제외"})
            continue
        best.setdefault("details", []).append(d)
        placed.add(d["id"])

    units, gaps = [], []
    releases = {}
    for step in kinds["step"]:
        goal = owner(step, kinds["goal"])
        if goal is None:
            warnings.append({"id": step["id"], "text": step["text"], "reason": "연결된 목적 카드가 없음: 구현에서 제외"})
            continue
        goal["has_step"] = True
        user = owner(goal, kinds["user"]) or (kinds["user"][0] if kinds["user"] else None)
        details = step.get("details", [])
        if not details:
            gaps.append({"kind": "step_without_details", "id": step["id"], "text": step["text"]})
        groups = {}
        for d in sorted(details, key=lambda n: n["y"]):
            groups.setdefault(d["release"]["id"] if d["release"] else None, []).append(d)
        for rel_id, ds in groups.items():
            rel = ds[0]["release"]
            rel_name = rel["name"] if rel else UNSLICED
            rel_rank = rel["y"] if rel else float("inf")
            releases[rel_name] = rel_rank
            body = {
                "user": user["text"] if user else None,
                "goal": goal["text"],
                "step": step["text"],
                "release": rel_name,
                "details": [d["text"] for d in ds],
            }
            units.append({
                "id": f"{step['id']}@{rel_id or 'unsliced'}",
                "branch": "story/" + re.sub(r"[^0-9a-z]+", "-", f"s{step['id']}-r{rel_id or 'unsliced'}".lower()),
                **body,
                "stepId": step["id"],
                "detailIds": [d["id"] for d in ds],
                "hash": hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12],
                "_order": (rel_rank, step["x"]),
            })
    for g in kinds["goal"]:
        if not g.get("has_step"):
            gaps.append({"kind": "goal_without_steps", "id": g["id"], "text": g["text"]})
    if not kinds["user"]:
        gaps.append({"kind": "no_user", "id": None, "text": "유저 카드가 없음"})

    units.sort(key=lambda u: u.pop("_order"))
    warnings.sort(key=lambda w: w["id"])
    return {
        "users": [brief(u) for u in kinds["user"]],
        "units": units,
        "gaps": gaps,
        "proposals": proposals,
        "warnings": warnings,
        "aiSectionId": ai_section,
        "ignoredNonStickies": flat["ignored"],
        "mapIds": [n["id"] for k in kinds.values() for n in k],
        "boardIds": [st["id"] for st in flat["stickies"]],
        "releases": [n for n, _ in sorted(releases.items(), key=lambda kv: kv[1])],
    }


def merge_units(new_units, prev):
    """Carry each unit's status forward. A shipped unit whose sticky text changed needs rework."""
    merged, seen = [], set()
    for u in new_units:
        seen.add(u["id"])
        old = prev.get(u["id"])
        status, pr, note = "pending", None, None
        if old:
            pr, note = old.get("pr"), old.get("note")
            status = old["status"]
            if old["hash"] != u["hash"]:
                if status in SHIPPED_STATUSES:
                    status = "changed"
                elif status in ("failed", "removed"):
                    status, note = "pending", None
            elif status == "removed":
                status = "changed"
        merged.append({**u, "status": status, "pr": pr, "note": note})
    for uid, old in prev.items():
        if uid not in seen and old["status"] != "pending":
            merged.append({**old, "status": "removed"})
    return merged


def merge_proposals(current, map_ids, board_ids, prev):
    """A proposal that left the AI section is adopted once it joins the map, and rejected only when deleted."""
    merged = dict(prev)
    live = {p["id"] for p in current}
    for p in current:
        merged[p["id"]] = {"text": p["text"], "status": "open"}
    for pid, p in prev.items():
        if pid not in live and p["status"] == "open":
            if pid in map_ids:
                merged[pid] = {**p, "status": "adopted"}
            elif pid not in board_ids:
                merged[pid] = {**p, "status": "rejected"}
    return merged


def next_unit(units):
    return next((u for u in units if u["status"] in OPEN_STATUSES), None)


def render_backlog(state):
    lines = ["# Story Map Backlog", ""]
    if state["users"]:
        lines += ["유저: " + ", ".join(u["text"] for u in state["users"]), ""]
    last = object()
    for u in state["units"]:
        if u["release"] != last:
            last = u["release"]
            lines += [f"## {last}", ""]
        pr = f" ({u['pr']})" if u.get("pr") else ""
        lines.append(f"- [{u['status']}] `{u['id']}` {u['goal']} > {u['step']}{pr}")
        lines += [f"  - {d}" for d in u["details"]]
    if state["gaps"]:
        lines += ["", "## 빈 곳", ""] + [f"- {g['kind']}: {g['text']}" for g in state["gaps"]]
    if state["warnings"]:
        lines += ["", "## 경고", ""] + [f"- `{w['id']}` {w['text']}: {w['reason']}" for w in state["warnings"]]
    return "\n".join(lines) + "\n"


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def summary(state, changed, stable):
    nxt = next_unit(state["units"])
    counts = {}
    for u in state["units"]:
        counts[u["status"]] = counts.get(u["status"], 0) + 1
    return {
        "changed": changed,
        "stable": stable,
        "readyToBuild": bool(stable and nxt and not state["warnings"]),
        "nextUnit": nxt,
        "statusCounts": counts,
        "releases": state["releases"],
        "gaps": state["gaps"],
        "warnings": state["warnings"],
        "openProposals": [{"id": k, **v} for k, v in state["proposals"].items() if v["status"] == "open"],
        "rejectedProposals": [v["text"] for v in state["proposals"].values() if v["status"] == "rejected"],
        "aiSectionId": state["aiSectionId"],
        "ignoredNonStickies": state["ignoredNonStickies"],
    }


def cmd_ingest(args):
    sd = Path(args.state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    cfg = {**DEFAULT_CONFIG, **load(sd / "config.json", {})}
    prev = load(sd / "state.json", {"units": [], "proposals": {}, "contentHash": None})

    board = build_map(Path(args.xml).read_text(encoding="utf-8"), cfg)
    # Proposals stay out of the fingerprint: writing one must not delay the next build.
    fingerprint = json.dumps(
        [board["users"], [(u["id"], u["hash"]) for u in board["units"]], board["warnings"], board["gaps"]],
        ensure_ascii=False, sort_keys=True)
    content_hash = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    changed = content_hash != prev["contentHash"]
    # A board mid-edit changes between polls; only an unchanged read is safe to build from.
    stable = prev["contentHash"] is not None and not changed

    state = {
        **board,
        "contentHash": content_hash,
        "units": merge_units(board["units"], {u["id"]: u for u in prev["units"]}),
        "proposals": merge_proposals(board["proposals"], set(board["mapIds"]), set(board["boardIds"]), prev["proposals"]),
    }
    (sd / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2))
    (sd / "BACKLOG.md").write_text(render_backlog(state))
    print(json.dumps(summary(state, changed, stable), ensure_ascii=False, indent=2))


def cmd_set_status(args):
    sd = Path(args.state_dir)
    state = json.loads((sd / "state.json").read_text())
    unit = next((u for u in state["units"] if u["id"] == args.unit_id), None)
    if unit is None:
        sys.exit(f"unknown unit: {args.unit_id}")
    unit["status"] = args.status
    if args.pr:
        unit["pr"] = args.pr
    if args.note:
        unit["note"] = args.note
    (sd / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2))
    (sd / "BACKLOG.md").write_text(render_backlog(state))


def cmd_show(args):
    state = json.loads((Path(args.state_dir) / "state.json").read_text())
    print(json.dumps(summary(state, False, False), ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest")
    i.add_argument("--xml", required=True)
    i.add_argument("--state-dir", default=".story-map")
    i.set_defaults(fn=cmd_ingest)
    s = sub.add_parser("set-status")
    s.add_argument("unit_id")
    s.add_argument("status", choices=sorted(ALL_STATUSES))
    s.add_argument("--pr")
    s.add_argument("--note")
    s.add_argument("--state-dir", default=".story-map")
    s.set_defaults(fn=cmd_set_status)
    v = sub.add_parser("show")
    v.add_argument("--state-dir", default=".story-map")
    v.set_defaults(fn=cmd_show)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
