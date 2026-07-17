#!/usr/bin/env python3
"""
Build printable bam PNGs from AI-generated corn + dragon masters.

Source masters (no borders / frames):
  minnesota-theme/bams/ai-source/1-bam-print.png      (detailed kernels; 1-bam only)
  minnesota-theme/bams/ai-source/corn-multi-print.png (solid silhouette; ranks 2–9)
  minnesota-theme/bams/ai-source/bam-dragon-print.png

At multi-rank scale (~4 mm wide corn on 6-bam), kernel holes shrink below a
0.4 mm nozzle and get filled by CAD (area < 0.1 mm²) or closed by inflate.
Ranks 2–9 therefore use a solid corn silhouette; only 1-bam keeps kernels.

Outputs 832x1248 B&W PNGs for 1-9 bam (composited corn + American
upper-left Arabic numeral) and bam-dragon (no numeral), with light
morphological thicken for 0.4 mm nozzle walls.

Then run CAD:
  cd projects/mahjong-tile
  rm -f assets/minnesota-theme/bams/svg/{1..9}-bam.svg
  uv run python generate_single_tile.py bams 1-bam 0.15   # etc.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

PNG_W, PNG_H = 832, 1248
PX_PER_MM = PNG_W / 16.0
MARGIN = 40
# Clear space between corn bboxes; thicken + 0.15 mm inflate eat ~0.4 mm,
# so keep ≥ ~1.4 mm nominal or husks still look fused on multi-col ranks.
GAP = 72

# American mahjong numeral band (upper-left), same black as art.
# Face-down prints the digit on the bed: counter must survive 0.15 mm mesh
# inflate + ~0.15 mm/side elephant foot. Heavy MinFilter thicken / ultra-black
# faces (Arial Black) pinch the "6"/"9" bowl–arch aperture shut — prefer an
# open-aperture display face (Gill Sans SemiBold) and skip numeral thicken.
# Target after inflate: stroke p25 ≥ 0.45 mm, counter opening ≥ 1.2 mm.
NUMERAL_HEIGHT_MM = 9.0
NUMERAL_HEIGHT_PX = int(NUMERAL_HEIGHT_MM * PX_PER_MM)
NUMERAL_LEFT = MARGIN + 4
NUMERAL_TOP = MARGIN + 2
# Keep corn ink clear of the digit on all sides (after thicken + inflate).
NUMERAL_BUFFER_MM = 1.5
NUMERAL_BUFFER_PX = int(NUMERAL_BUFFER_MM * PX_PER_MM)
# Canvas MinFilter thicken for ranks ≥2 expands ink by this many pixels.
POST_THICKEN_PX = 1

# (path, ttc_index) — Gill Sans SemiBold has a naturally open 6/9 aperture.
FONT_CANDIDATES = [
    (Path("/System/Library/Fonts/Supplemental/GillSans.ttc"), 4),  # SemiBold
    (Path("/System/Library/Fonts/HelveticaNeue.ttc"), 10),  # Medium
    (Path("/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"), 0),
    (Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"), 0),
]

REPO = Path(__file__).resolve().parents[1]
AI = REPO / "minnesota-theme" / "bams" / "ai-source"
OUT = REPO / "minnesota-theme" / "bams" / "png"
MODEL = Path(
    "/Users/rchoi/Documents/antigravity/modeling/projects/mahjong-tile/"
    "assets/minnesota-theme/bams/png"
)


def to_bw(im: Image.Image) -> Image.Image:
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im.convert("RGBA")).convert("RGB")
    else:
        im = im.convert("RGB")
    g = ImageOps.grayscale(im)
    return g.point(lambda x: 0 if x < 160 else 255, mode="L")


def thicken_black(bw: Image.Image, pixels: int = 2) -> Image.Image:
    out = bw
    for _ in range(pixels):
        out = out.filter(ImageFilter.MinFilter(3))
    return out


def content_bbox(bw: Image.Image, pad: int = 4):
    inv = ImageOps.invert(bw)
    box = inv.getbbox()
    if not box:
        return (0, 0, bw.width, bw.height)
    x0, y0, x1, y1 = box
    return (
        max(0, x0 - pad),
        max(0, y0 - pad),
        min(bw.width, x1 + pad),
        min(bw.height, y1 + pad),
    )


def load_numeral_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path, index in FONT_CANDIDATES:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size, index=index)
            except OSError:
                continue
    return ImageFont.load_default()


def numeral_layer(digit: int) -> Image.Image:
    """Render the rank digit to a cropped L-mode layer (black = 0)."""
    scale = 4
    font = load_numeral_font(NUMERAL_HEIGHT_PX * scale)
    text = str(digit)
    probe = Image.new("L", (1, 1), 255)
    bbox = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = scale * 6
    layer = Image.new("L", (tw + 2 * pad, th + 2 * pad), 255)
    ImageDraw.Draw(layer).text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=0)
    layer = layer.resize(
        (max(1, layer.width // scale), max(1, layer.height // scale)),
        Image.Resampling.LANCZOS,
    )
    return layer.point(lambda x: 0 if x < 128 else 255, mode="L")


def numeral_ink_bbox(digit: int) -> tuple[int, int, int, int]:
    """Absolute canvas bbox of numeral ink at NUMERAL_LEFT/TOP."""
    layer = numeral_layer(digit)
    inv = ImageOps.invert(layer)
    box = inv.getbbox()
    if not box:
        return (
            NUMERAL_LEFT,
            NUMERAL_TOP,
            NUMERAL_LEFT + layer.width,
            NUMERAL_TOP + layer.height,
        )
    x0, y0, x1, y1 = box
    return (
        NUMERAL_LEFT + x0,
        NUMERAL_TOP + y0,
        NUMERAL_LEFT + x1,
        NUMERAL_TOP + y1,
    )


def numeral_exclusion(digit: int) -> tuple[int, int, int, int]:
    """Numeral ink bbox expanded by NUMERAL_BUFFER — corn must stay outside."""
    x0, y0, x1, y1 = numeral_ink_bbox(digit)
    return (
        max(0, x0 - NUMERAL_BUFFER_PX),
        max(0, y0 - NUMERAL_BUFFER_PX),
        min(PNG_W, x1 + NUMERAL_BUFFER_PX),
        min(PNG_H, y1 + NUMERAL_BUFFER_PX),
    )


def draw_numeral(canvas: Image.Image, digit: int) -> None:
    """Paste an open-aperture Arabic numeral in the upper-left (black = 0)."""
    layer = numeral_layer(digit)
    mask = layer.point(lambda v: 255 if v < 128 else 0)
    canvas.paste(0, (NUMERAL_LEFT, NUMERAL_TOP), mask)


def cell_positions(n: int) -> list[tuple[int, int]]:
    layouts = {
        1: [(0, 0)],
        2: [(0, 0), (0, 1)],
        4: [(0, 0), (1, 0), (0, 1), (1, 1)],
        # 6 = two rows of three (fills width; avoids sparse 2-col towers)
        6: [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)],
        # 3 / 5 / 7–9 = see place_three / place_five / place_seven / place_eight / place_nine
    }
    return layouts[n]


def place_group(
    canvas: Image.Image,
    glyph: Image.Image,
    cells: list[tuple[int, int]],
    cols: int,
    rows: int,
    *,
    origin_x: float,
    origin_y: float,
    usable_w: float,
    usable_h: float,
    align_bottom: bool = False,
    align_top: bool = False,
    exclusion: tuple[int, int, int, int] | None = None,
) -> None:
    """Tight pack glyphs into usable rect starting at (origin_x, origin_y)."""
    max_gw = (usable_w - (cols - 1) * GAP) / cols if cols else usable_w
    max_gh = (usable_h - (rows - 1) * GAP) / rows if rows else usable_h
    g = glyph.copy()
    g.thumbnail((int(max_gw), int(max_gh)), Image.Resampling.LANCZOS)
    g = g.point(lambda x: 0 if x < 128 else 255, mode="L")
    gw, gh = g.width, g.height

    group_w = cols * gw + (cols - 1) * GAP
    group_h = rows * gh + (rows - 1) * GAP
    ox = origin_x + (usable_w - group_w) / 2
    if align_bottom:
        oy = origin_y + usable_h - group_h
    elif align_top:
        oy = origin_y
    else:
        oy = origin_y + (usable_h - group_h) / 2

    if exclusion is not None:
        ox, oy = _shift_group_clear_of_exclusion(ox, oy, gw, gh, cells, exclusion)

    mask = g.point(lambda v: 255 if v < 128 else 0)
    for c, r in cells:
        x = int(ox + c * (gw + GAP))
        y = int(oy + r * (gh + GAP))
        canvas.paste(0, (x, y), mask)


def place_three(
    canvas: Image.Image,
    glyph: Image.Image,
    *,
    origin_x: float,
    origin_y: float,
    usable_w: float,
    usable_h: float,
    exclusion: tuple[int, int, int, int] | None = None,
) -> None:
    """Triangle 1|2: one centered on top, two below, pinned to bottom.

    Glyph size matches rank 4's 2×2 pack (same below-numeral cell limits).
    """
    # Size from rank-4 geometry so 3 and 4 share one corn scale.
    _ox4, _oy4, uw4, uh4 = corn_region_for(4)
    max_gw = (uw4 - GAP) / 2
    max_gh = (uh4 - GAP) / 2
    g = glyph.copy()
    g.thumbnail((int(max_gw), int(max_gh)), Image.Resampling.LANCZOS)
    g = g.point(lambda x: 0 if x < 128 else 255, mode="L")
    gw, gh = g.width, g.height
    group_w = 2 * gw + GAP
    group_h = 2 * gh + GAP
    ox = origin_x + (usable_w - group_w) / 2
    oy = origin_y + usable_h - group_h
    mask = g.point(lambda v: 255 if v < 128 else 0)
    abs_pos = [
        (ox + (group_w - gw) / 2, oy),
        (ox, oy + gh + GAP),
        (ox + gw + GAP, oy + gh + GAP),
    ]
    if exclusion is not None:
        dx, dy = _rigid_shift_for_rects(abs_pos, gw, gh, exclusion)
        abs_pos = [(x + dx, y + dy) for x, y in abs_pos]
    for x, y in abs_pos:
        canvas.paste(0, (int(x), int(y)), mask)


def place_five(
    canvas: Image.Image,
    glyph: Image.Image,
    *,
    origin_x: float,
    origin_y: float,
    usable_w: float,
    usable_h: float,
    exclusion: tuple[int, int, int, int] | None = None,
) -> None:
    """Columns 1|2|2: bottom-left corn + two columns of two, pinned to bottom."""
    _place_column_grid(
        canvas,
        glyph,
        left_rows=(1,),
        n_rows=2,
        origin_x=origin_x,
        origin_y=origin_y,
        usable_w=usable_w,
        usable_h=usable_h,
        align_bottom=True,
        exclusion=exclusion,
    )


def place_seven(
    canvas: Image.Image,
    glyph: Image.Image,
    *,
    origin_x: float,
    origin_y: float,
    usable_w: float,
    usable_h: float,
    exclusion: tuple[int, int, int, int] | None = None,
) -> None:
    """Columns 1|3|3: bottom-left corn + two full-height columns of three."""
    _place_column_grid(
        canvas,
        glyph,
        left_rows=(2,),
        n_rows=3,
        origin_x=origin_x,
        origin_y=origin_y,
        usable_w=usable_w,
        usable_h=usable_h,
        align_bottom=True,
        exclusion=exclusion,
    )


def place_eight(
    canvas: Image.Image,
    glyph: Image.Image,
    *,
    origin_x: float,
    origin_y: float,
    usable_w: float,
    usable_h: float,
    exclusion: tuple[int, int, int, int] | None = None,
) -> None:
    """Columns 2|3|3: left mid+bottom (above the 7's single) + two triples."""
    _place_column_grid(
        canvas,
        glyph,
        left_rows=(1, 2),
        n_rows=3,
        origin_x=origin_x,
        origin_y=origin_y,
        usable_w=usable_w,
        usable_h=usable_h,
        align_bottom=True,
        exclusion=exclusion,
    )


def place_nine(
    canvas: Image.Image,
    glyph: Image.Image,
    *,
    origin_x: float,
    origin_y: float,
    usable_w: float,
    usable_h: float,
    exclusion: tuple[int, int, int, int] | None = None,
) -> None:
    """3×3: mid/right match 7's corn size; left column fits under the numeral.

    A full 3-tall left column at 7's glyph size cannot clear the numeral buffer
    (top-left sits inside the digit). Mid/right keep 7's size and bottom
    alignment; left is sized to the under-numeral band in that column.
    """
    del origin_x, origin_y, usable_w, usable_h  # sized from rank-7 geometry
    ox7, oy7, uw7, uh7 = corn_region_for(7)
    max_gw = (uw7 - 2 * GAP) / 3
    max_gh = (uh7 - 2 * GAP) / 3
    g_large = glyph.copy()
    g_large.thumbnail((int(max_gw), int(max_gh)), Image.Resampling.LANCZOS)
    g_large = g_large.point(lambda x: 0 if x < 128 else 255, mode="L")
    glw, glh = g_large.width, g_large.height

    group_w = 3 * glw + 2 * GAP
    group_h = 3 * glh + 2 * GAP
    ox = ox7 + (uw7 - group_w) / 2
    oy = oy7 + uh7 - group_h

    mask_l = g_large.point(lambda v: 255 if v < 128 else 0)
    for c in (1, 2):
        for r in range(3):
            x = int(ox + c * (glw + GAP))
            y = int(oy + r * (glh + GAP))
            canvas.paste(0, (x, y), mask_l)

    # Left column: three corns stacked fully below the buffered numeral.
    if exclusion is None:
        _ex0, _ey0, _ex1, ey1 = numeral_exclusion(9)
    else:
        _ex0, _ey0, _ex1, ey1 = exclusion
    left_top = float(ey1 + POST_THICKEN_PX)
    left_bottom = oy + group_h
    left_h = max(1.0, left_bottom - left_top)
    max_gh_s = (left_h - 2 * GAP) / 3
    g_small = glyph.copy()
    g_small.thumbnail((glw, int(max_gh_s)), Image.Resampling.LANCZOS)
    g_small = g_small.point(lambda x: 0 if x < 128 else 255, mode="L")
    gsw, gsh = g_small.width, g_small.height
    mask_s = g_small.point(lambda v: 255 if v < 128 else 0)
    # Bottom-align the small stack with the large grid; center in the column slot.
    small_h = 3 * gsh + 2 * GAP
    sy0 = left_bottom - small_h
    sx = int(ox + (glw - gsw) / 2)
    for r in range(3):
        y = int(sy0 + r * (gsh + GAP))
        canvas.paste(0, (sx, y), mask_s)


def _exclusion_hit_pad(
    exclusion: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    ex0, ey0, ex1, ey1 = exclusion
    return ex0, ey0, ex1 + POST_THICKEN_PX, ey1 + POST_THICKEN_PX


def _rect_intersects_exclusion(
    x: float,
    y: float,
    gw: int,
    gh: int,
    exclusion: tuple[int, int, int, int],
) -> bool:
    ex0, ey0, ex1, ey1 = _exclusion_hit_pad(exclusion)
    return not (x + gw <= ex0 or x >= ex1 or y + gh <= ey0 or y >= ey1)


def _rigid_shift_for_rects(
    positions: list[tuple[float, float]],
    gw: int,
    gh: int,
    exclusion: tuple[int, int, int, int],
) -> tuple[float, float]:
    """Return (dx, dy) to move all rects rigidly out of the exclusion."""
    ex0, ey0, ex1, ey1 = _exclusion_hit_pad(exclusion)
    dx = dy = 0.0
    for _ in range(32):
        moved = False
        for x, y in positions:
            xx, yy = x + dx, y + dy
            if not _rect_intersects_exclusion(xx, yy, gw, gh, exclusion):
                continue
            # Prefer drop below the digit when that clears; else slide right.
            need_dy = ey1 - yy
            need_dx = ex1 - xx
            if need_dy <= need_dx:
                dy += need_dy
            else:
                dx += need_dx
            moved = True
            break
        if not moved:
            break
    return dx, dy


def _shift_group_clear_of_exclusion(
    ox: float,
    oy: float,
    gw: int,
    gh: int,
    cells: list[tuple[int, int]],
    exclusion: tuple[int, int, int, int],
) -> tuple[float, float]:
    positions = [(ox + c * (gw + GAP), oy + r * (gh + GAP)) for c, r in cells]
    dx, dy = _rigid_shift_for_rects(positions, gw, gh, exclusion)
    ox, oy = ox + dx, oy + dy
    # Keep the group on-canvas after clearance shifts.
    cols = max(c for c, _r in cells) + 1
    rows = max(r for _c, r in cells) + 1
    group_w = cols * gw + (cols - 1) * GAP
    group_h = rows * gh + (rows - 1) * GAP
    ox = min(ox, float(PNG_W - MARGIN - group_w))
    ox = max(ox, float(MARGIN))
    oy = min(oy, float(PNG_H - MARGIN - group_h))
    oy = max(oy, float(MARGIN))
    return ox, oy


def _place_column_grid(
    canvas: Image.Image,
    glyph: Image.Image,
    *,
    left_rows: tuple[int, ...],
    n_rows: int,
    origin_x: float,
    origin_y: float,
    usable_w: float,
    usable_h: float,
    align_bottom: bool = False,
    align_top: bool = False,
    exclusion: tuple[int, int, int, int] | None = None,
) -> None:
    """3-col pack: sparse left column + full middle/right columns over n_rows."""
    max_gw = (usable_w - 2 * GAP) / 3
    max_gh = (usable_h - (n_rows - 1) * GAP) / n_rows
    g = glyph.copy()
    g.thumbnail((int(max_gw), int(max_gh)), Image.Resampling.LANCZOS)
    g = g.point(lambda x: 0 if x < 128 else 255, mode="L")
    gw, gh = g.width, g.height
    group_w = 3 * gw + 2 * GAP
    group_h = n_rows * gh + (n_rows - 1) * GAP
    ox = origin_x + (usable_w - group_w) / 2
    if align_bottom:
        oy = origin_y + usable_h - group_h
    elif align_top:
        oy = origin_y
    else:
        oy = origin_y + (usable_h - group_h) / 2
    cells = [(0, r) for r in left_rows]
    cells.extend((c, r) for c in (1, 2) for r in range(n_rows))
    if exclusion is not None:
        ox, oy = _shift_group_clear_of_exclusion(ox, oy, gw, gh, cells, exclusion)
    mask = g.point(lambda v: 255 if v < 128 else 0)
    for c, r in cells:
        x = int(ox + c * (gw + GAP))
        y = int(oy + r * (gh + GAP))
        canvas.paste(0, (x, y), mask)


def corn_region_for(n: int) -> tuple[float, float, float, float]:
    """Return (origin_x, origin_y, usable_w, usable_h) for rank n.

    Corn packing must respect numeral_exclusion(n). Width-filling ranks
    (1, 3, 4, 6) sit fully below the exclusion (3 shares 4's corn scale).
    Sparse column ranks (5, 7, 8, 9) use the wide+tall face so mid/right
    columns can reach the top (9 sizes mid/right from rank-7 geometry and
    packs its left column under the digit). Rank 2 packs in the tall strip
    fully right of the exclusion.
    """
    _ex0, _ey0, ex1, ey1 = numeral_exclusion(n)
    thicken_pad = POST_THICKEN_PX if n >= 2 else 0
    if n in (1, 3, 4, 6):
        origin_x = float(MARGIN)
        origin_y = float(ey1 + thicken_pad)
    elif n in (5, 7, 8, 9):
        origin_x = float(MARGIN)
        origin_y = float(MARGIN + 24)
    else:
        # 2: tall strip right of the digit (+ buffer + thicken pad).
        origin_x = float(ex1 + thicken_pad)
        origin_y = float(MARGIN + 24)
    usable_w = PNG_W - MARGIN - origin_x
    usable_h = PNG_H - MARGIN - origin_y
    return origin_x, origin_y, usable_w, usable_h


def load_corn_glyph(path: Path, *, thicken_px: int = 2) -> Image.Image:
    bw = thicken_black(to_bw(Image.open(path)), pixels=thicken_px)
    return bw.crop(content_bbox(bw))


def main() -> None:
    corn_detail_src = AI / "1-bam-print.png"
    corn_multi_src = AI / "corn-multi-print.png"
    dragon_src = AI / "bam-dragon-print.png"
    missing = [p for p in (corn_detail_src, corn_multi_src, dragon_src) if not p.exists()]
    if missing:
        raise SystemExit(f"Missing AI masters: {', '.join(str(p) for p in missing)}")

    OUT.mkdir(parents=True, exist_ok=True)
    MODEL.mkdir(parents=True, exist_ok=True)

    glyph_detail = load_corn_glyph(corn_detail_src, thicken_px=2)
    # Solid multi silhouette: light thicken only (no kernels to close).
    glyph_multi = load_corn_glyph(corn_multi_src, thicken_px=1)

    dims = {
        1: (1, 1),
        2: (1, 2),
        4: (2, 2),
        6: (3, 2),  # three across, two down
    }

    for n in range(1, 10):
        ox, oy, uw, uh = corn_region_for(n)
        excl = numeral_exclusion(n)
        canvas = Image.new("L", (PNG_W, PNG_H), 255)
        glyph = glyph_detail if n == 1 else glyph_multi
        if n == 3:
            place_three(
                canvas, glyph, origin_x=ox, origin_y=oy, usable_w=uw, usable_h=uh, exclusion=excl
            )
        elif n == 5:
            place_five(
                canvas, glyph, origin_x=ox, origin_y=oy, usable_w=uw, usable_h=uh, exclusion=excl
            )
        elif n == 7:
            place_seven(
                canvas, glyph, origin_x=ox, origin_y=oy, usable_w=uw, usable_h=uh, exclusion=excl
            )
        elif n == 8:
            place_eight(
                canvas, glyph, origin_x=ox, origin_y=oy, usable_w=uw, usable_h=uh, exclusion=excl
            )
        elif n == 9:
            place_nine(
                canvas, glyph, origin_x=ox, origin_y=oy, usable_w=uw, usable_h=uh, exclusion=excl
            )
        else:
            cols, rows = dims[n]
            place_group(
                canvas,
                glyph,
                cell_positions(n),
                cols,
                rows,
                origin_x=ox,
                origin_y=oy,
                usable_w=uw,
                usable_h=uh,
                align_bottom=(n == 2),
                exclusion=excl if n == 2 else None,
            )
        canvas = canvas.point(lambda x: 0 if x < 128 else 255, mode="L")
        # Outer-wall thicken for multi-rank solids (safe — no interior holes).
        if n >= 2:
            canvas = thicken_black(canvas, pixels=1)
        draw_numeral(canvas, n)
        canvas = canvas.point(lambda x: 0 if x < 128 else 255, mode="L")
        for dest in (OUT, MODEL):
            canvas.save(dest / f"{n}-bam.png")
        kind = "detail" if n == 1 else "solid-multi"
        print(f"Wrote {n}-bam.png (numeral {n}, {kind})")

    draw = thicken_black(to_bw(Image.open(dragon_src)), pixels=2)
    crop = draw.crop(content_bbox(draw))
    crop.thumbnail((PNG_W - 2 * MARGIN, PNG_H - 2 * MARGIN), Image.Resampling.LANCZOS)
    crop = crop.point(lambda x: 0 if x < 128 else 255, mode="L")
    full = Image.new("L", (PNG_W, PNG_H), 255)
    full.paste(crop, ((PNG_W - crop.width) // 2, (PNG_H - crop.height) // 2))
    for dest in (OUT, MODEL):
        full.save(dest / "bam-dragon.png")
    print("Wrote bam-dragon.png (no numeral)")


if __name__ == "__main__":
    main()
