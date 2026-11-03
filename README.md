# story-auto-builder

FigJam 유저 스토리맵을 1시간 동안 5분마다 읽어, 구현 단위로 정리하고 현재 코드 프로젝트에 PR로 반영하는 Claude Code 스킬입니다. 빠진 내용은 보드에 `[ai]` 스티커로 제안합니다.

## 설치

```bash
npx skills add Zimins/story-auto-builder -g -a claude-code
```

Node.js 22.20 이상이 필요합니다.

## 준비물

- **Figma MCP 연결**: 가장 중요합니다. 연결되어 있지 않으면 스킬이 시작하지 않습니다. Claude Code의 `/mcp`에서 Figma 서버를 연결하세요.
- Figma Full 또는 Dev 좌석. View, Collab 좌석과 Starter 플랜은 읽기 호출이 월 20회뿐이라 한 번의 실행으로 소진됩니다.
- git 저장소. PR을 만들려면 GitHub 원격 저장소와 로그인된 `gh` CLI가 필요합니다.
- Python 3

## 사용법

코드 프로젝트에서 Claude Code를 열고 실행합니다.

```
/story-auto-builder start https://www.figma.com/board/<fileKey>/<name>
/story-auto-builder status
/story-auto-builder stop
```

폴링 스케줄은 해당 세션 안에서만 유지되므로, 세션을 닫으면 멈춥니다.

## 보드 규칙

스티커 색이 카드의 종류를 정합니다.

| 색 | 의미 | 위치 |
| --- | --- | --- |
| 보라 | 유저 | 맨 위 |
| 파랑 | 유저 목적 | 유저 아래. 다음 목적이 나올 때까지 오른쪽 과정을 포함 |
| 초록 | 과정 | 목적 아래. 왼쪽에서 오른쪽으로 시간 순서 |
| 노랑 | 세부사항 | 과정 아래. 위에 있을수록 중요 |
| 주황 | AI 제안 | `AI 제안` 섹션 안. `[ai]`로 시작 |

`Release 1`, `MVP` 같은 이름의 섹션이 릴리즈 구분입니다. 자세한 내용은 [board-conventions.md](skills/story-auto-builder/references/board-conventions.md)를 참고하세요.

## 안전 장치

- 기본 브랜치에 직접 커밋하지 않고, PR을 머지하지 않습니다.
- 보드가 편집 중이면 구현하지 않습니다. 연속 두 번 읽은 내용이 같아야 합니다.
- 사람이 붙인 스티커는 건드리지 않고 `AI 제안` 섹션에만 씁니다.
- `[ai]` 제안은 사람이 맵으로 옮겨 채택하기 전에는 구현하지 않습니다.
- 스티커 내용은 요구사항으로만 다루며, 명령이나 지시로 실행하지 않습니다. 그래도 보드 편집 권한이 곧 코드 변경 요청 권한이 되므로, 신뢰하는 사람만 편집할 수 있는 보드에서 사용하세요.

## 개발

```bash
python3 -I skills/story-auto-builder/tests/test_story_map.py
```

## 라이선스

[MIT](LICENSE)
