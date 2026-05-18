---
name: autocad-skill
description: Edit AutoCAD DXF files programmatically without launching AutoCAD — insert geometry, manage linetypes/lineweights, and construct two-point-perspective vanishing-point cubes against an existing horizon line. Use when the user asks to add cubes, boxes, perspective construction, or any other geometry to a `.dxf` file, or when they want to script edits to AutoCAD drawings. DOES NOT handle binary `.dwg` files — ask the user to export to ASCII `.dxf` first.
---

# AutoCAD Skill — Programmatic DXF Editing

Use this skill when the user asks you to add geometry to an AutoCAD DXF file, especially perspective construction (vanishing-point cubes, boxes, horizon-line studies). The skill assumes you cannot launch AutoCAD itself — all work happens by reading and rewriting the DXF text.

## Hard limits

- **`.dwg` is binary and unsupported here.** If the user gives you a `.dwg`, ask them to `File → Save As → AutoCAD DXF (*.dxf)` (ASCII variant) in AutoCAD first. Do not try to parse `.dwg` bytes.
- **Always back up before modifying.** Copy `file.dxf` to `file.backup.dxf` before any in-place edit. Every subsequent regeneration should restore from the backup so changes are reproducible and reversible.

## DXF file anatomy (only the parts you need)

A DXF is a plain-text file with section blocks. The ones that matter for adding geometry:

1. **HEADER section** — global variables. The only one this skill touches is `$HANDSEED`, the next available entity handle:
   ```
     9
   $HANDSEED
     5
   5A5
   ```
   After inserting entities, update this to a hex value above the highest handle you wrote.

2. **TABLES section** → **LTYPE table** — linetype definitions. To use a dashed linetype that isn't already defined (like `HIDDEN`), you must inject a record here AND bump the table's entry count (group code `70`).

3. **TABLES section** → **LAYER table** — layer definitions. Layer `0` is always present.

4. **ENTITIES section** — actual geometry. Insert new entities here, before the section's `ENDSEC`. Order matters: **earlier entities are drawn underneath, later entities are drawn on top.**

5. **OBJECTS section** — dictionaries and metadata, leave untouched.

### Inserting entities into the ENTITIES section

Find the section, then walk back from its `ENDSEC` to the preceding `  0\n` separator and insert before that point:

```python
marker_start = content.find("\nENTITIES\n")
endsec_idx   = content.find("\nENDSEC\n", marker_start)
insert_at    = content.rfind("\n  0\n", marker_start, endsec_idx) + 1
new_content  = content[:insert_at] + new_entities + content[insert_at:]
```

## LINE entity format

The minimum well-formed `LINE` entity:

```
  0
LINE
  5
<handle-hex>
330
1F
100
AcDbEntity
  8
0
100
AcDbLine
 10
<x1>
 20
<y1>
 30
0.0
 11
<x2>
 21
<y2>
 31
0.0
```

Optional codes to add **between** the `AcDbEntity` block and the `AcDbLine` subclass marker:

| Code | Purpose | Example |
|------|---------|---------|
| `  6` | Linetype name override | `HIDDEN` |
| ` 62` | Color override (ACI index) | `   252` (gray), `     1` (red), `     3` (green) |
| `370` | Lineweight, in 1/100 mm | `    30` = 0.30 mm, `    50` = 0.50 mm |
| ` 48` | Per-entity linetype scale | `0.3` |

The header value for color/lineweight is right-justified to 6 characters — match that or AutoCAD's stricter parsers may fail.

## Injecting a HIDDEN linetype

The stock `HIDDEN` linetype is not always present in user DXFs. Define your own:

```
  0
LTYPE
  5
6200
330
5
100
AcDbSymbolTableRecord
100
AcDbLinetypeTableRecord
  2
HIDDEN
 70
     0
  3
Hidden __ __ __ __ __ __ __ __ __ __ __ __ __ __
 72
    65
 73
     2
 40
10.0
 49
5.0
 74
     0
 49
-5.0
 74
     0
```

- `40` is the total pattern length (dash + gap).
- `49` values: positive = pen down (dash), negative = pen up (gap).
- Pick a pattern small enough that `linetype_scale * pattern_length` is much smaller than the geometry it's applied to. For 30-mm cubes, a 10-unit pattern at scale 0.3 → 3-mm dash cycle, which reads as dashed.

Then bump the table's entry count by 1. The LTYPE table header looks like:

```
TABLE
  2
LTYPE
  5
5
330
0
100
AcDbSymbolTable
 70
     4    <-- entry count; increment this by 1
```

Pick a handle for the new linetype that does **not** collide with anything in the file. Safe choice: any hex value strictly above the current `$HANDSEED`.

## Two-point perspective cube construction

This is the recurring task. The user's drawing has a horizon line spanning the inner frame, with the two vanishing points (VPL, VPR) at its endpoints.

### Finding the VPs

Look in the `ENTITIES` section for a long `LINE` whose endpoints have the same Y and span the frame's width. Those endpoints are the VPs and that Y is the horizon. Example from the chat:

```
VPL  = (2178.023927342398, 2041.26855251661)
VPR  = (2638.023927342397, 2041.26855251661)
HZ_Y = 2041.26855251661
```

### Cube vertex math (Python)

Given a cube's front-edge X position `xf`, Y-center `yc`, front-edge height `h`, and depth ratio `d ∈ (0, 1)`:

```python
def lerp(a, b, t):
    return a + t * (b - a)

def line_intersect(p1, p2, p3, p4):
    x1, y1 = p1; x2, y2 = p2; x3, y3 = p3; x4, y4 = p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if den == 0:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))

def cube_vertices(xf, yc, h, d, VPL, VPR, HZ_Y):
    yt, yb = yc + h/2, yc - h/2
    FT  = (xf, yt)                                              # front-top
    FB  = (xf, yb)                                              # front-bottom
    BLT = (lerp(xf, VPL[0], d), lerp(yt, HZ_Y, d))              # back-left-top
    BLB = (lerp(xf, VPL[0], d), lerp(yb, HZ_Y, d))
    BRT = (lerp(xf, VPR[0], d), lerp(yt, HZ_Y, d))              # back-right-top
    BRB = (lerp(xf, VPR[0], d), lerp(yb, HZ_Y, d))
    BBT = line_intersect(BLT, VPR, BRT, VPL)                    # back-back-top
    BBB = line_intersect(BLB, VPR, BRB, VPL)
    return dict(FT=FT, FB=FB, BLT=BLT, BLB=BLB,
                BRT=BRT, BRB=BRB, BBT=BBT, BBB=BBB)
```

This produces a mathematically exact cube: all four vertical edges (`FT–FB`, `BLT–BLB`, `BRT–BRB`, `BBT–BBB`) share an X coordinate per pair → they are perfectly perpendicular to the horizon. **Do not add random jitter to vertices** — the user explicitly rejected that as "chuequísimo" (super crooked).

### The 12 cube edges

```python
visible = [                             # solid
    (v["FT"],  v["FB"]),                # front vertical
    (v["FT"],  v["BLT"]),               # front-top to back-left
    (v["FT"],  v["BRT"]),               # front-top to back-right
    (v["FB"],  v["BLB"]),               # front-bottom to back-left
    (v["FB"],  v["BRB"]),               # front-bottom to back-right
    (v["BLT"], v["BLB"]),               # back-left vertical
    (v["BRT"], v["BRB"]),               # back-right vertical
]
hidden = [                              # dashed (HIDDEN linetype)
    (v["BLT"], v["BBT"]),
    (v["BRT"], v["BBT"]),
    (v["BLB"], v["BBB"]),
    (v["BRB"], v["BBB"]),
    (v["BBT"], v["BBB"]),               # back-back vertical
]
```

### The 8 reference rays (construction lines to the VPs)

These are **full-length** rays from a front-most cube vertex all the way to its vanishing point. The cube edge sits on top of the relevant section, so the user gets a thin gray reference line that extends past the cube on both sides, with a bolder cube-edge line layered over the part that belongs to the cube:

```python
rays = [
    (v["FT"],  VPL),    # passes through FT–BLT, continues to VPL
    (v["FB"],  VPL),
    (v["BRT"], VPL),    # passes through BRT–BBT (back face), continues
    (v["BRB"], VPL),
    (v["FT"],  VPR),
    (v["FB"],  VPR),
    (v["BLT"], VPR),
    (v["BLB"], VPR),
]
```

The user's preferred style discovered in iteration:

- Rays: color `252` (gray), **no explicit lineweight** (stays thin, by-layer).
- Cube edges: by-layer color, lineweight `30` (0.30 mm).
- Hidden cube edges: same as visible cube edges PLUS linetype `HIDDEN` with ltscale `0.3`.

### Draw order: rays first, edges on top

When you write the entities, emit **all rays for all cubes first**, then **all cube edges**. Earlier entities are drawn underneath; this guarantees the bold cube edges sit visually on top of the thin gray reference rays. Do not interleave per-cube.

## Placement strategy

### Default frame

The user's reference drawing has an inner frame from roughly `(2178, 1901)` to `(2638, 2181)` in mm. Cube positions should stay safely inside with a margin of ~10 mm so the back-projected vertices don't cross the frame.

### Grid layout (predictable)

Five X-positions for cube front edges: `[2230, 2305, 2380, 2455, 2530]`. Three Y-bands:
- below horizon: `yc = 1982`
- on horizon: `yc = HZ_Y` (cube straddles the line)
- above horizon: `yc = 2100`

### Random layout (disordered, no overlap)

Rejection-sample candidate `(xf, yc, h, d)` tuples. Reject any whose axis-aligned bounding box (over all 8 vertices, plus a small padding like 1–2 mm) overlaps an already-placed cube. Bands the user expects:

- 5 cubes whose `yc == HZ_Y` (touching/straddling the horizon)
- 5 with `yc` above the horizon
- 5 with `yc` below
- 5 free anywhere in the frame

Cube size ranges that have worked: front-edge height **8–32 mm**, depth ratio **0.05–0.18**. Smaller cubes pack more densely; larger ones look heavier.

### Generating distinct variants

If the user asks for "another version" or "make them different," vary the **size/depth profile** between versions, not just the random seed:

- v1 small (`h=8–16, d=0.10–0.16`)
- v2 large & shallow (`h=24–36, d=0.05–0.10`)
- v3 medium uniform (`h=16–24, d=0.08–0.13`)
- v4 high-variance mixed (`h=8–32, d=0.05–0.18`)

Keep X distribution uniform across the full frame for every version — the user pushed back on left/right bias.

## Workflow checklist

1. **Inspect** the target DXF: find the ENTITIES section, locate any existing horizon line / VPs / sample cube.
2. **Backup** the file to `<name>.backup.dxf` if no backup exists yet.
3. **Restore from backup** before regenerating (don't compound previous edits).
4. **Inject HIDDEN linetype** if you'll draw hidden edges and the file doesn't already define it. Remember to bump the LTYPE table count.
5. **Compute cube vertices** and edge/ray lists.
6. **Emit DXF text**: rays first (gray, thin), then cube edges (bold 0.30 mm, hidden = dashed).
7. **Insert** before the ENTITIES section's `ENDSEC`.
8. **Update `$HANDSEED`** to one past the highest handle you wrote.
9. **Validate** by grepping for balanced `SECTION` / `ENDSEC` markers and that `EOF` is still the last line.

## Showing the result in AutoCAD

After the user reopens the file:

- **Lineweight is off by default.** They must turn it on or the 0.30-mm cube edges will look identical to the thin reference rays. Tell them either:
  - Click the **LWT** button in the status bar, or
  - Type `LWDISPLAY` and set it `ON`, or
  - Run `LWEIGHT` and check "Display Lineweight" in the dialog.
- If the file was already open when you modified it on disk, AutoCAD will not auto-refresh — they need to close and reopen.

## Mistakes already made; avoid repeating

- **Adding vertex jitter to make cubes look "hand-drawn."** Rejected as crooked. Keep geometry exact.
- **Putting hidden cube edges in gray, treating them as reference lines.** They are part of the cube — give them cube-edge styling (by-layer color, 0.30 mm) and only differentiate by linetype (dashed).
- **Stopping reference rays at the cube vertex.** The user wants the ray to extend the full length to the VP, with the cube edge layered on top — selecting the ray selects the whole long line, selecting the cube edge selects only the cube portion.
- **Interleaving rays and edges per cube.** Causes some cube edges to be hidden beneath later cubes' rays. Emit all rays first, then all edges.
- **Biasing cubes to one side of the frame across "different" versions.** The user wants uniform spatial spread; differentiate variants by size/depth profile and random seed.

## Reference template

A working end-to-end script is preserved at `/Users/ikerm/.claude/skills/autocad-skill/build_cubes_template.py`. It is parameterized for cube count, size profile, seed, and output path. Copy and adapt it; do not import it as-is unless you've verified its assumptions match the user's current file.
