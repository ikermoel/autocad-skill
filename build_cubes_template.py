#!/usr/bin/env python3
"""Generate 4 different cube-layout versions of cubos.dxf.

Each version has 20 cubes:
  - 5 straddling the horizon line
  - 5 above the horizon
  - 5 below the horizon
  - 5 random anywhere in the frame
All with varied sizes and depths, in random non-overlapping positions.
"""

import random
import shutil
import os

BASE = "/Users/ikerm/Desktop/autocad/cubos.dxf"
BACKUP = "/Users/ikerm/Desktop/autocad/cubos.backup.dxf"

# All versions span the full frame uniformly (no left/right bias). What
# changes between them is the random seed AND the size/depth profile so each
# composition lands in a different place AND the cubes themselves look
# different.
VERSIONS = [
    # (path, seed, h_range, d_range, description)
    (BASE,
     11, (8.0, 16.0),  (0.10, 0.16), "small"),
    ("/Users/ikerm/Desktop/autocad/cubos_v2.dxf",
     27, (24.0, 36.0), (0.05, 0.10), "large & shallow"),
    ("/Users/ikerm/Desktop/autocad/cubos_v3.dxf",
     53, (16.0, 24.0), (0.08, 0.13), "medium uniform"),
    ("/Users/ikerm/Desktop/autocad/cubos_v4.dxf",
     91, (8.0, 32.0),  (0.05, 0.18), "high variance"),
]

VPL = (2178.023927342398, 2041.26855251661)
VPR = (2638.023927342397, 2041.26855251661)
HZ_Y = VPL[1]

X_MIN_FRAME, X_MAX_FRAME = 2178.0, 2638.0
Y_MIN_FRAME, Y_MAX_FRAME = 1901.0, 2181.0
X_MARGIN = 12.0
Y_MARGIN = 8.0

# Per-cube size ranges (varied).
H_RANGE     = (12.0, 32.0)
DEPTH_RANGE = (0.07, 0.16)

# Y-center bands for each row category (relative to the horizon).
ABOVE_Y_BAND = (HZ_Y + 22.0, Y_MAX_FRAME - Y_MARGIN - 20.0)
BELOW_Y_BAND = (Y_MIN_FRAME + Y_MARGIN + 20.0, HZ_Y - 22.0)
FREE_Y_BAND  = (Y_MIN_FRAME + Y_MARGIN, Y_MAX_FRAME - Y_MARGIN)

X_BAND = (X_MIN_FRAME + X_MARGIN, X_MAX_FRAME - X_MARGIN)

PADDING = 1.5
MAX_ATTEMPTS_PER_CUBE = 4000

GRAY = 252
LINEWEIGHT = 30
HIDDEN_LTYPE_NAME = "HIDDEN"
HIDDEN_LTYPE_SCALE = 0.3

HANDLE_START_CUBES = 0x7000
HIDDEN_LTYPE_HANDLE = "6200"


def lerp(a, b, t):
    return a + t * (b - a)


def line_intersect(p1, p2, p3, p4):
    x1, y1 = p1; x2, y2 = p2; x3, y3 = p3; x4, y4 = p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if den == 0:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def cube_vertices(xf, yc, h, d):
    yt = yc + h / 2.0
    yb = yc - h / 2.0
    FT = (xf, yt)
    FB = (xf, yb)
    BLT = (lerp(xf, VPL[0], d), lerp(yt, HZ_Y, d))
    BLB = (lerp(xf, VPL[0], d), lerp(yb, HZ_Y, d))
    BRT = (lerp(xf, VPR[0], d), lerp(yt, HZ_Y, d))
    BRB = (lerp(xf, VPR[0], d), lerp(yb, HZ_Y, d))
    BBT = line_intersect(BLT, VPR, BRT, VPL)
    BBB = line_intersect(BLB, VPR, BRB, VPL)
    return dict(FT=FT, FB=FB, BLT=BLT, BLB=BLB, BRT=BRT, BRB=BRB, BBT=BBT, BBB=BBB)


def cube_bbox(v):
    xs = [p[0] for p in v.values()]
    ys = [p[1] for p in v.values()]
    return (min(xs) - PADDING, min(ys) - PADDING,
            max(xs) + PADDING, max(ys) + PADDING)


def bbox_overlap(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def bbox_in_frame(b):
    return (b[0] >= X_MIN_FRAME and b[2] <= X_MAX_FRAME and
            b[1] >= Y_MIN_FRAME and b[3] <= Y_MAX_FRAME)


def try_place(yc_band, placed_bboxes, rng, h_range, d_range, x_band):
    for _ in range(MAX_ATTEMPTS_PER_CUBE):
        xf = rng.uniform(*x_band)
        yc = rng.uniform(*yc_band)
        h  = rng.uniform(*h_range)
        d  = rng.uniform(*d_range)
        v  = cube_vertices(xf, yc, h, d)
        bb = cube_bbox(v)
        if not bbox_in_frame(bb):
            continue
        if any(bbox_overlap(bb, pb) for pb in placed_bboxes):
            continue
        return (xf, yc, h, d), bb
    return None


def place_on_horizon(placed_bboxes, rng, h_range, d_range, x_band):
    for _ in range(MAX_ATTEMPTS_PER_CUBE):
        xf = rng.uniform(*x_band)
        h  = rng.uniform(*h_range)
        d  = rng.uniform(*d_range)
        yc = HZ_Y
        v  = cube_vertices(xf, yc, h, d)
        bb = cube_bbox(v)
        if not bbox_in_frame(bb):
            continue
        if any(bbox_overlap(bb, pb) for pb in placed_bboxes):
            continue
        return (xf, yc, h, d), bb
    return None


def cube_lines(v):
    visible = [
        (v["FT"], v["FB"]),
        (v["FT"], v["BLT"]),
        (v["FT"], v["BRT"]),
        (v["FB"], v["BLB"]),
        (v["FB"], v["BRB"]),
        (v["BLT"], v["BLB"]),
        (v["BRT"], v["BRB"]),
    ]
    hidden = [
        (v["BLT"], v["BBT"]),
        (v["BRT"], v["BBT"]),
        (v["BLB"], v["BBB"]),
        (v["BRB"], v["BBB"]),
        (v["BBT"], v["BBB"]),
    ]
    rays = [
        (v["FT"], VPL),
        (v["FB"], VPL),
        (v["BRT"], VPL),
        (v["BRB"], VPL),
        (v["FT"], VPR),
        (v["FB"], VPR),
        (v["BLT"], VPR),
        (v["BLB"], VPR),
    ]
    return visible, hidden, rays


def line_dxf(handle_hex, p1, p2, color=None, lineweight=None,
             linetype=None, ltscale=None):
    x1, y1 = p1; x2, y2 = p2
    parts = ["  0", "LINE", "  5", handle_hex, "330", "1F",
             "100", "AcDbEntity", "  8", "0"]
    if linetype is not None:
        parts += ["  6", linetype]
    if color is not None:
        parts += [" 62", f"{color:>6}"]
    if lineweight is not None:
        parts += ["370", f"{lineweight:>6}"]
    if ltscale is not None:
        parts += [" 48", f"{ltscale:.6g}"]
    parts += ["100", "AcDbLine",
              " 10", f"{x1:.12g}", " 20", f"{y1:.12g}", " 30", "0.0",
              " 11", f"{x2:.12g}", " 21", f"{y2:.12g}", " 31", "0.0"]
    return "\n".join(parts) + "\n"


HIDDEN_LTYPE_RECORD = f"""  0
LTYPE
  5
{HIDDEN_LTYPE_HANDLE}
330
5
100
AcDbSymbolTableRecord
100
AcDbLinetypeTableRecord
  2
{HIDDEN_LTYPE_NAME}
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
"""


def inject_hidden_linetype(content):
    marker = "TABLE\n  2\nLTYPE\n  5\n5\n330\n0\n100\nAcDbSymbolTable\n 70\n     4\n"
    new_marker = "TABLE\n  2\nLTYPE\n  5\n5\n330\n0\n100\nAcDbSymbolTable\n 70\n     5\n"
    if marker not in content:
        raise SystemExit("LTYPE table header not found")
    content = content.replace(marker, new_marker, 1)
    ltype_pos = content.find("\nLTYPE\n  5\n5\n330\n0\n")
    endtab_pos = content.find("\nENDTAB\n", ltype_pos)
    insert_at = content.rfind("\n  0\n", ltype_pos, endtab_pos) + 1
    content = content[:insert_at] + HIDDEN_LTYPE_RECORD + content[insert_at:]
    return content


def generate_layout(seed, h_range, d_range, x_band):
    rng = random.Random(seed)
    placed_bboxes = []
    cube_params = []

    def batch(n, placer):
        for _ in range(n):
            r = placer()
            if r is None:
                break
            params, bb = r
            cube_params.append(params)
            placed_bboxes.append(bb)

    batch(5, lambda: place_on_horizon(placed_bboxes, rng, h_range, d_range, x_band))
    batch(5, lambda: try_place(ABOVE_Y_BAND, placed_bboxes, rng, h_range, d_range, x_band))
    batch(5, lambda: try_place(BELOW_Y_BAND, placed_bboxes, rng, h_range, d_range, x_band))
    batch(5, lambda: try_place(FREE_Y_BAND,  placed_bboxes, rng, h_range, d_range, x_band))

    return cube_params


def build_dxf(seed, out_path, h_range, d_range, x_band):
    shutil.copyfile(BACKUP, out_path)
    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    content = inject_hidden_linetype(content)
    cube_params = generate_layout(seed, h_range, d_range, x_band)

    handle = HANDLE_START_CUBES
    out = []
    # Rays first (so they sit underneath).
    for (xf, yc, h, d) in cube_params:
        v = cube_vertices(xf, yc, h, d)
        _, _, rays = cube_lines(v)
        for (p1, p2) in rays:
            out.append(line_dxf(f"{handle:X}", p1, p2, color=GRAY))
            handle += 1
    # Cube edges on top.
    for (xf, yc, h, d) in cube_params:
        v = cube_vertices(xf, yc, h, d)
        visible, hidden, _ = cube_lines(v)
        for (p1, p2) in visible:
            out.append(line_dxf(f"{handle:X}", p1, p2,
                                color=None, lineweight=LINEWEIGHT))
            handle += 1
        for (p1, p2) in hidden:
            out.append(line_dxf(f"{handle:X}", p1, p2,
                                color=None, lineweight=LINEWEIGHT,
                                linetype=HIDDEN_LTYPE_NAME,
                                ltscale=HIDDEN_LTYPE_SCALE))
            handle += 1

    new_entities = "".join(out)
    marker_start = content.find("\nENTITIES\n")
    endsec_idx = content.find("\nENDSEC\n", marker_start)
    insert_at = content.rfind("\n  0\n", marker_start, endsec_idx) + 1
    new_content = content[:insert_at] + new_entities + content[insert_at:]

    new_seed = f"{handle + 16:X}"
    new_content = new_content.replace(
        "$HANDSEED\n  5\n6151\n",
        f"$HANDSEED\n  5\n{new_seed}\n",
        1,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return len(cube_params), len(out)


def main():
    for path, seed, h_range, d_range, desc in VERSIONS:
        n_cubes, n_lines = build_dxf(seed, path, h_range, d_range, X_BAND)
        print(f"{os.path.basename(path):16s}  seed={seed:3d}  h={h_range}  d={d_range}  "
              f"({desc})  cubes={n_cubes}  lines={n_lines}")


if __name__ == "__main__":
    main()
