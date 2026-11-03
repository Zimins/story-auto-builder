# Writing proposals to FigJam

The script below already follows Figma's `figma-use` and `figma-use-figjam` rules and was tested on a live board, so you can run it as written. Load that guidance only if you need to change it: use those skills, or the MCP resources `skill://figma/figma-use/SKILL.md` and `skill://figma/figma-use-figjam/SKILL.md` through `ReadMcpResourceTool` (load it with `ToolSearch`). Pass the saved `sessionId`, and `skillNames: "resource:figma-use,resource:figma-use-figjam"` only if you loaded them from resources.

Run this with `AI_SECTION_ID` set to `aiSectionId` from the summary (or `null` if there is none), and `PROPOSALS` set to the new texts. It is the only write this skill makes. It creates the section when missing, to the right of everything on the board, and appends after existing stickies, so it never touches other nodes.

```js
const AI_SECTION_ID = null
const PROPOSALS = ['[ai] 결제: 카드 결제 실패 시 재시도 안내']

const h = (r, g, b) => ({ r: r / 255, g: g / 255, b: b / 255 })
const ORANGE = h(0xff, 0xd3, 0xa8)
const COLS = 3, GAP = 40, PAD = 40

let section = AI_SECTION_ID ? await figma.getNodeByIdAsync(AI_SECTION_ID) : null
if (!section) {
  const page = figma.currentPage
  const right = page.children.reduce((m, n) => Math.max(m, n.x + n.width), 0)
  section = figma.createSection()
  section.name = 'AI 제안'
  page.appendChild(section)
  section.x = right + 160
  section.y = 0
  section.resize(COLS * 240 + (COLS - 1) * GAP + PAD * 2, 320)
  section.fills = [{ type: 'SOLID', color: h(0xff, 0xf7, 0xf0) }]
}

const probe = figma.createSticky()
await figma.loadFontAsync(probe.text.fontName)
probe.remove()

const created = []
let index = section.children.filter((n) => n.type === 'STICKY').length
for (const text of PROPOSALS) {
  const s = figma.createSticky()
  s.text.characters = text
  s.fills = [{ type: 'SOLID', color: ORANGE }]
  section.appendChild(s)
  s.x = PAD + (index % COLS) * (240 + GAP)
  s.y = PAD + Math.floor(index / COLS) * (240 + GAP)
  created.push(s.id)
  index++
}

const right = Math.max(...section.children.map((n) => n.x + n.width)) + PAD
const bottom = Math.max(...section.children.map((n) => n.y + n.height)) + PAD
section.resize(Math.max(section.width, right), Math.max(section.height, bottom))
return { sectionId: section.id, createdNodeIds: created }
```

Stickies that overflow grow taller than 240, so a very long proposal may overlap the row below. Keep each one short.
