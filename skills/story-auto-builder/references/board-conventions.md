# Board conventions

Based on Jeff Patton's user story mapping: activities form a left-to-right **backbone** in time order, stories hang below as **ribs** with the most necessary on top, and the top of the map is the **walking skeleton**, the smallest end-to-end system. There is no industry-standard color scheme, so this skill fixes one by layer.

## Reading the layout

```
[유저]                                    violet
[목적 A ──────────] [목적 B ────────]     blue    backbone
[과정1]  [과정2]    [과정3]  [과정4]      green   time flows left to right
┌ Release 1 ──────────────────────────┐
│[세부]   [세부]     [세부]   [세부]    │  yellow  higher = more essential
└─────────────────────────────────────┘
┌ Release 2 ──────────────────────────┐
│[세부]              [세부]             │
└─────────────────────────────────────┘
                     ┌ AI 제안 ───────┐
                     │[ai] ...        │  orange
                     └────────────────┘
```

- **Goal to step:** a step belongs to the nearest goal starting at or left of its center. Goals may sit above only their first step.
- **Step to detail:** a detail belongs to the step it overlaps horizontally the most. No overlap gives a warning, and the card is left out.
- **Release:** a section whose name matches `releasePattern` (`MVP`, `Walking skeleton`, `Release 1`, `R2`, `v1`, `릴리즈`, `슬라이스`). Other sections are ignored, so a map wrapped in a plain `Story Map` section still works. Details outside any release land in `미분류`, built last.
- **Multiple users:** a goal belongs to the nearest user at or left of its center.

Stacking several separate maps on one board is not supported: columns would merge. Use one board per map.

## What `get_figjam` actually returns

Verified on a live board on 2026-11-03:

- Sticky color arrives as a name such as `STICKY_BLUE`; non-palette fills arrive as `CUSTOM` and cannot be classified. Recolor those with a palette swatch.
- `author` is empty for MCP-created stickies, so authorship cannot identify AI cards. That is why `[ai]` and the section exist.
- Line breaks in sticky text are flattened to spaces, so write one idea per sticky.
- Sticky text is double-escaped; the parser handles it.
- Children of sections use section-relative coordinates; the parser converts them.
- Shapes, text nodes, and connectors are ignored. Only stickies carry meaning, so a legend or annotation will not affect the map. The count appears as `ignoredNonStickies`, which helps when someone used shapes instead of stickies.

## Overrides

`.story-map/config.json`, merged over the defaults key by key:

```json
{
  "colors": {"STICKY_PINK": "user", "STICKY_TEAL": "goal", "STICKY_GREEN": "step", "STICKY_YELLOW": "detail"},
  "aiSection": "AI 제안",
  "aiColor": "STICKY_ORANGE",
  "releasePattern": "(?i)^\\s*(sprint|release)"
}
```

Palette names: `STICKY_WHITE`, `STICKY_GRAY`, `STICKY_GREEN`, `STICKY_TEAL`, `STICKY_BLUE`, `STICKY_VIOLET`, `STICKY_PINK`, `STICKY_RED`, `STICKY_ORANGE`, `STICKY_YELLOW`. Only the names observed in testing are verified: violet, blue, green, yellow, orange. If another color shows up under a different name, the warning prints the exact value to use.
