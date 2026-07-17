#!/usr/bin/env python3
"""
Build printable crack PNGs from AI-generated fish + dragon masters.

Source masters (no borders / frames):
  minnesota-theme/cracks/ai-source/1-crack-print.png
  minnesota-theme/cracks/ai-source/crack-dragon-print.png

Outputs 832x1248 B&W PNGs for 1-9 crack (composited fish + American
upper-left Arabic numeral) and crack-dragon (no numeral), with light
morphological thicken for 0.4 mm nozzle walls.

Then run CAD:
  cd projects/mahjong-tile
  rm -f assets/minnesota-theme/cracks/svg/{1..9}-crack.svg
  uv run python generate_single_tile.py cracks 1-crack 0.15   # etc.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

PNG_W, PNG_H = 832, 1248
PX_PER_MM = PNG_W / 16.0
MARGIN = 40
GAP = 28  # tighter pack so multi-col ranks (esp. 6) don't look sparse

# American mahjong numeral band (upper-left), same black as art
NUMERAL_HEIGHT_PX = int(4.0 * PX_PER_MM)  # ~4 mm tall
NUMERAL_LEFT = MARGIN + 4
NUMERAL_TOP = MARGIN + 2
# Reserve so fish cluster clears the digit (modest — keep group visually centered)
NUMERAL_RESERVE_LEFT = int(PNG_W * 0.12)
NUMERAL_RESERVE_TOP = int(PNG_H * 0.10)

FONT_CANDIDATES = [
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Black.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
]

REPO = Path(__file__).resolve().parents[1]
AI = REPO / "minnesota-theme" / "cracks" / "ai-source"
OUT = REPO / "minnesota-theme" / "cracks" / "png"
MODEL = Path(
    "/Users/rchoi/Documents/antigravity/modeling/projects/mahjong-tile/"
    "assets/minnesota-theme/cracks/png"
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
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def draw_numeral(canvas: Image.Image, digit: int) -> None:
    """Paste a bold Arabic numeral in the upper-left (black = 0)."""
    # Oversample then downscale for cleaner thick strokes
    scale = 4
    font = load_numeral_font(NUMERAL_HEIGHT_PX * scale)
    text = str(digit)
    # Measure on a temp image
    probe = Image.new("L", (1, 1), 255)
    probe_draw = ImageDraw.Draw(probe)
    bbox = probe_draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = scale * 4
    layer = Image.new("L", (tw + 2 * pad, th + 2 * pad), 255)
    ImageDraw.Draw(layer).text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=0)
    # Thicken strokes to meet ~0.5 mm after downscale
    layer = thicken_black(layer, pixels=max(2, scale // 2))
    layer = layer.resize(
        (max(1, layer.width // scale), max(1, layer.height // scale)),
        Image.Resampling.LANCZOS,
    )
    layer = layer.point(lambda x: 0 if x < 128 else 255, mode="L")
    mask = layer.point(lambda v: 255 if v < 128 else 0)
    canvas.paste(0, (NUMERAL_LEFT, NUMERAL_TOP), mask)


def cell_positions(n: int) -> list[tuple[int, int]]:
    layouts = {
        1: [(0, 0)],
        2: [(0, 0), (0, 1)],
        3: [(0, 0), (0, 1), (0, 2)],
        4: [(0, 0), (1, 0), (0, 1), (1, 1)],
        # 6 = two rows of three (fills width; avoids sparse 2-col towers)
        6: [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)],
        7: [(0, 0), (1, 0), (2, 0), (1, 1), (0, 2), (1, 2), (2, 2)],
        8: [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2), (0, 3), (1, 3)],
        9: [(c, r) for r in range(3) for c in range(3)],
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
    # Center group within the reserved usable rect
    ox = origin_x + (usable_w - group_w) / 2
    oy = origin_y + (usable_h - group_h) / 2

    mask = g.point(lambda v: 255 if v < 128 else 0)
    for c, r in cells:
        x = int(ox + c * (gw + GAP))
        y = int(oy + r * (gh + GAP))
        canvas.paste(0, (x, y), mask)


def place_five(
    canvas: Image.Image,
    glyph: Image.Image,
    *,
    origin_x: float,
    origin_y: float,
    usable_w: float,
    usable_h: float,
) -> None:
    max_gw = (usable_w - GAP) / 2
    max_gh = (usable_h - 2 * GAP) / 3
    g = glyph.copy()
    g.thumbnail((int(max_gw), int(max_gh)), Image.Resampling.LANCZOS)
    g = g.point(lambda x: 0 if x < 128 else 255, mode="L")
    gw, gh = g.width, g.height
    group_w = 2 * gw + GAP
    group_h = 3 * gh + 2 * GAP
    ox = origin_x + (usable_w - group_w) / 2
    oy = origin_y + (usable_h - group_h) / 2
    mask = g.point(lambda v: 255 if v < 128 else 0)
    positions = [
        (ox, oy),
        (ox + gw + GAP, oy),
        (ox + (group_w - gw) / 2, oy + gh + GAP),
        (ox, oy + 2 * (gh + GAP)),
        (ox + gw + GAP, oy + 2 * (gh + GAP)),
    ]
    for x, y in positions:
        canvas.paste(0, (int(x), int(y)), mask)


def fish_region() -> tuple[float, float, float, float]:
    """Return (origin_x, origin_y, usable_w, usable_h) clearing numeral band."""
    origin_x = MARGIN + NUMERAL_RESERVE_LEFT * 0.35  # slight right shift
    origin_y = MARGIN + NUMERAL_RESERVE_TOP
    usable_w = PNG_W - MARGIN - origin_x
    usable_h = PNG_H - MARGIN - origin_y
    return origin_x, origin_y, usable_w, usable_h


def main() -> None:
    fish_src = AI / "1-crack-print.png"
    dragon_src = AI / "crack-dragon-print.png"
    if not fish_src.exists() or not dragon_src.exists():
        raise SystemExit(f"Missing AI masters in {AI}")

    OUT.mkdir(parents=True, exist_ok=True)
    MODEL.mkdir(parents=True, exist_ok=True)

    bw = thicken_black(to_bw(Image.open(fish_src)), pixels=2)
    glyph = bw.crop(content_bbox(bw))

    dims = {
        1: (1, 1),
        2: (1, 2),
        3: (1, 3),
        4: (2, 2),
        6: (3, 2),  # three across, two down
        7: (3, 3),
        8: (2, 4),
        9: (3, 3),
    }
    ox, oy, uw, uh = fish_region()

    for n in range(1, 10):
        canvas = Image.new("L", (PNG_W, PNG_H), 255)
        if n == 5:
            place_five(canvas, glyph, origin_x=ox, origin_y=oy, usable_w=uw, usable_h=uh)
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
            )
        canvas = canvas.point(lambda x: 0 if x < 128 else 255, mode="L")
        if n >= 5:
            canvas = thicken_black(canvas, pixels=1)
        draw_numeral(canvas, n)
        canvas = canvas.point(lambda x: 0 if x < 128 else 255, mode="L")
        for dest in (OUT, MODEL):
            canvas.save(dest / f"{n}-crack.png")
        print(f"Wrote {n}-crack.png (numeral {n})")

    # Remove stale jpeg if present (was 7-crack.jpeg)
    for dest in (OUT, MODEL):
        stale = dest / "7-crack.jpeg"
        if stale.exists():
            stale.unlink()
            print(f"Removed {stale}")

    draw = thicken_black(to_bw(Image.open(dragon_src)), pixels=2)
    crop = draw.crop(content_bbox(draw))
    crop.thumbnail((PNG_W - 2 * MARGIN, PNG_H - 2 * MARGIN), Image.Resampling.LANCZOS)
    crop = crop.point(lambda x: 0 if x < 128 else 255, mode="L")
    full = Image.new("L", (PNG_W, PNG_H), 255)
    full.paste(crop, ((PNG_W - crop.width) // 2, (PNG_H - crop.height) // 2))
    for dest in (OUT, MODEL):
        full.save(dest / "crack-dragon.png")
    print("Wrote crack-dragon.png (no numeral)")


if __name__ == "__main__":
    main()
