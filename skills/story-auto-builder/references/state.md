# State files

Everything lives in `.story-map/` at the repository root. It is excluded through `.git/info/exclude`, so it never appears in a commit or conflicts between branches. Open PRs on `story/*` branches are the shared record, and the PR body links back to the board.

| File | Written by | Purpose |
| --- | --- | --- |
| `run.json` | skill | fileKey, deadline, cron id, Figma session, poll count |
| `config.json` | user, optional | color and naming overrides |
| `board.xml` | skill | the latest `get_figjam` output |
| `state.json` | `story_map.py` | units, statuses, proposals, content hash |
| `BACKLOG.md` | `story_map.py` | readable unit list |

## Unit status

| Status | Meaning | Next |
| --- | --- | --- |
| `pending` | not started | build |
| `in_progress` | build agent running | wait |
| `pr_open` | PR exists | review |
| `committed` | on a local branch, no GitHub remote | review |
| `done` | merged, set by hand or when `gh` shows it merged | none |
| `changed` | stickies edited after shipping | update the branch |
| `failed` | checks failed or requirements unclear | retried once the stickies change |
| `removed` | stickies deleted after shipping | a person decides |

A unit's id is `<step node id>@<release section id>`, so renaming a card keeps its identity while moving a detail to another release makes it part of a different unit.
