# AutoCAD Skill

> A Claude Code / Codex skill for editing AutoCAD `.dxf` files programmatically — no AutoCAD required.

[![Claude Code](https://img.shields.io/badge/Claude%20Code-skill-d97757)](https://claude.ai/code)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](#license)
[![DXF](https://img.shields.io/badge/format-DXF%20ASCII-green)](#supported-formats)

---

## What it does

This skill teaches an AI coding assistant (Claude Code, Codex, or any agent that loads skill files) how to **modify AutoCAD DXF drawings directly from text** — inserting geometry, managing linetypes and lineweights, and constructing **two-point-perspective vanishing-point cubes** against an existing horizon line.

The original use case: a drafting student who needed dozens of perspective cubes added to a class drawing without re-drawing each one by hand. The skill captures the full DXF-editing workflow, the geometry math, the conventions, and the gotchas learned through iteration.

```
                       horizon line
   ┌─────────────┬──────────────────┬─────────────┐
   │             │                  │             │
   │     ╱──────┐│   ╱──────┐       │┌──────╲     │
   │    ╱   ▢   ││  ╱   ▢   │       ││   ▢   ╲    │
   │   ╱        ││ ╱        │       ││        ╲   │
   │   │────────││ │────────│       ││─────────│  │
  VPL─────────────────────────────────────────────VPR
   │             │                  │             │
   │             │                  │             │
   └─────────────┴──────────────────┴─────────────┘
```

---

## Features

- 📐 **Two-point perspective cubes** — mathematically exact verticals, automatic convergence to user's existing vanishing points.
- 🎨 **Style conventions baked in** — 0.30 mm cube edges, gray construction rays, dashed hidden edges (HIDDEN linetype with scale 0.3).
- 🗂️ **DXF table management** — injects new linetypes into the LTYPE table and bumps entry counts safely.
- 🎲 **Random + grid placement** — bounding-box rejection sampling, configurable size/depth profiles, multiple variants per file.
- 🛡️ **Safe by default** — always backs up before modifying, restores from backup before regenerating.
- 🚫 **Knows what NOT to do** — encoded mistakes from real iteration (no vertex jitter, no left/right bias, no interleaved draw order).

---

## Installation

### Option 1 — Drop into your Claude Code skills folder

```bash
git clone https://github.com/ikermoel/autocad-skill.git ~/.claude/skills/autocad-skill
```

Claude Code will pick up `SKILL.md` automatically the next time you start a session in any project.

### Option 2 — Copy into your project

```bash
mkdir -p .claude/skills/autocad
cp SKILL.md .claude/skills/autocad/
cp build_cubes_template.py .claude/skills/autocad/
```

### Option 3 — Use with Codex / other agents

The `SKILL.md` is plain markdown with YAML frontmatter. Any agent that supports skill/instruction injection can load it. The `build_cubes_template.py` is a standalone Python script with no dependencies beyond the standard library.

---

## How to use

Once installed, just ask Claude in plain language:

> *"Add 15 vanishing-point cubes to `drawing.dxf` — 5 above the horizon, 5 on it, 5 below."*

> *"Insert a cube at coordinates X=2400, Y=2050 into my drawing."*

> *"Generate 4 different layouts of perspective cubes, varying their sizes."*

Claude will:

1. Read the DXF and locate the horizon line / vanishing points.
2. Back up the file to `<name>.backup.dxf`.
3. Compute cube geometry.
4. Inject any missing linetypes (e.g. `HIDDEN`).
5. Write new `LINE` entities into the `ENTITIES` section.
6. Update `$HANDSEED`.
7. Validate the file structure.

---

## Supported formats

| Format | Status | Notes |
|--------|--------|-------|
| `.dxf` (ASCII) | ✅ Full support | All modern DXF versions tested |
| `.dwg` (binary) | ❌ Not supported | Export to DXF first: `File → Save As → AutoCAD DXF (*.dxf)` |
| `.dxf` (binary) | ⚠️ Not tested | Probably won't work — use ASCII variant |

---

## Quick example

Given a DXF with a horizon line from `(2178, 2041)` to `(2638, 2041)`, here is what the skill will produce for a single cube at the front-edge X = 2380, centered above the horizon:

```python
# Cube parameters
xf = 2380.0     # front edge X
yc = 2100.0     # Y center (above horizon)
h  = 28.0       # front edge height in mm
d  = 0.13       # depth ratio toward each VP

# Output:
#   12 LINE entities for the cube edges:
#     - 7 visible (continuous, by-layer color, 0.30 mm lineweight)
#     - 5 hidden (HIDDEN linetype scale 0.3, 0.30 mm lineweight)
#   8 LINE entities for construction rays (color 252 gray, default lineweight)
#   = 20 LINE entities total per cube
```

The cube edges sit visually on top of the gray reference rays — the rays extend past the cube vertices all the way to the vanishing points, but the cube portion of each line gets a bolder layered edge.

---

## Important: viewing the result in AutoCAD

Lineweight display is **OFF by default** in AutoCAD. After opening the modified file, do one of:

- Click the **LWT** button in the bottom status bar, OR
- Type `LWDISPLAY` in the command line and set it to `ON`, OR
- Type `LWEIGHT` and check "Display Lineweight" in the dialog.

Otherwise the 0.30 mm cube edges will look the same as the thin gray reference rays.

If the DXF was already open in AutoCAD when modified, close and reopen it — AutoCAD does not auto-refresh changes from disk.

---

## What's in the box

```
autocad-skill/
├── SKILL.md                      ← the skill instruction file
├── build_cubes_template.py       ← working reference script
└── README.md                     ← this file
```

`SKILL.md` is the main artifact — it gets loaded by Claude/Codex and provides the model with everything it needs to perform AutoCAD DXF edits.

`build_cubes_template.py` is a fully working Python script (standard library only) that generates 4 variant DXF files with 20 perspective cubes each, using rejection-sampled placement and varied size profiles. Copy and adapt for your own drawings.

---

## Why this skill exists

Vanilla LLMs struggle with DXF for three reasons:

1. **The format is finicky.** Group codes are positional, the LTYPE table needs special handling, handles must be unique and the `$HANDSEED` must be kept in sync.
2. **Perspective math is easy to get wrong.** Without explicit guidance, models tend to add "imperfections" (jitter, rotation, mismatched VPs) that look wrong.
3. **The user's style preferences are non-obvious.** Things like "construction rays must extend past the cube, not stop at it" only emerge through iteration.

This skill packages all of that learning so the next person doesn't have to teach it from scratch.

---

## Mistakes the skill knows to avoid

The skill explicitly documents these anti-patterns (from real iteration):

- ❌ Adding random jitter to vertex positions to fake a "hand-drawn" feel — rejected as crooked.
- ❌ Coloring hidden cube edges gray, as if they were reference lines — they are part of the cube.
- ❌ Stopping reference rays at the cube vertex instead of extending to the VP.
- ❌ Interleaving rays and cube edges per-cube (causes later cubes' rays to draw on top of earlier cubes' edges).
- ❌ Biasing cubes to one side of the frame across "different" variants — keep spatial spread uniform; differentiate by size/depth profile.

---

## Roadmap

- [ ] Direct `.dwg` support via ODA File Converter integration
- [ ] One-point and three-point perspective helpers
- [ ] Shadow projection construction
- [ ] Block (`INSERT`) reuse for repeated cube geometry
- [ ] LISP / `.scr` script export for in-AutoCAD execution

---

## Contributing

Bug reports, style tweaks, and new perspective constructions welcome. Open an issue describing what you tried, what you expected, and what the model actually did.

---

## License

MIT — see `LICENSE` (or treat as MIT until added).

---

## Credits

Built iteratively in a Claude Code session by [@ikermoel](https://github.com/ikermoel) — a drafting student who needed perspective cubes in a hurry. The skill exists because Claude eventually figured out what "está chuequísimo" actually meant.
