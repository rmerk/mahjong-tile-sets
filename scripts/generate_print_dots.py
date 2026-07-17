#!/usr/bin/env python3
"""
Build printable dot PNGs from filled bobber + soap masters.

Source masters (no borders / frames):
  minnesota-theme/dots/ai-source/1-dot-print.png   (bobber + ripples)
  minnesota-theme/dots/ai-source/bobber-print.png  (bobber only, ranks 2–9)
  minnesota-theme/dots/ai-source/soap-dragon-print.png

Outputs 832x1248 B&W PNGs for 1-9 dot (composited bobbers + American
upper-left Arabic numeral) and soap-dragon (no numeral), with light
morphological thicken for 0.4 mm nozzle walls.

Layouts follow traditional American mahjong dots (dice-like), packed onto
a fixed face canvas (no tall-canvas hacks for 7–9).

Then run CAD:
  cd projects/mahjong-tile
  rm -f assets/minnesota-theme/dots/svg/{1..9}-dot.svg \\
        assets/minnesota-theme/dots/svg/soap-dragon.svg
  uv run python generate_single_tile.py dots 1-dot 0.15   # etc.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

PNG_W, PNG_H = 832, 1248
PX_PER_MM = PNG_W / 16.0
MARGIN = 40
GAP = 24

# American mahjong numeral band (upper-left), same black as art
NUMERAL_HEIGHT_PX = int(4.0 * PX_PER_MM)  # ~4 mm tall
NUMERAL_LEFT = MARGIN + 4
NUMERAL_TOP = MARGIN + 2
NUMERAL_RESERVE_LEFT = int(PNG_W * 0.12)
NUMERAL_RESERVE_TOP = int(PNG_H * 0.10)

FONT_CANDIDATES = [
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Black.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
]

REPO = Path(__file__).resolve().parents[1]
AI = REPO / "minnesota-theme" / "dots" / "ai-source"
OUT = REPO / "minnesota-theme" / "dots" / "png"
MODEL = Path(
    "/Users/rchoi/Documents/antigravity/modeling/projects/mahjong-tile/"
    "assets/minnesota-theme/dots/png"
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
    scale = 4
    font = load_numeral_font(NUMERAL_HEIGHT_PX * scale)
    text = str(digit)
    probe = Image.new("L", (1, 1), 255)
    probe_draw = ImageDraw.Draw(probe)
    bbox = probe_draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = scale * 4
    layer = Image.new("L", (tw + 2 * pad, th + 2 * pad), 255)
    ImageDraw.Draw(layer).text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=0)
    layer = thicken_black(layer, pixels=max(2, scale // 2))
    layer = layer.resize(
        (max(1, layer.width // scale), max(1, layer.height // scale)),
        Image.Resampling.LANCZOS,
    )
    layer = layer.point(lambda x: 0 if x < 128 else 255, mode="L")
    mask = layer.point(lambda v: 255 if v < 128 else 0)
    canvas.paste(0, (NUMERAL_LEFT, NUMERAL_TOP), mask)


def motif_region() -> tuple[float, float, float, float]:
    """Return (origin_x, origin_y, usable_w, usable_h) clearing numeral band."""
    origin_x = MARGIN + NUMERAL_RESERVE_LEFT * 0.35
    origin_y = MARGIN + NUMERAL_RESERVE_TOP
    usable_w = PNG_W - MARGIN - origin_x
    usable_h = PNG_H - MARGIN - origin_y
    return origin_x, origin_y, usable_w, usable_h


def _fit_glyph(glyph: Image.Image, max_w: float, max_h: float) -> Image.Image:
    g = glyph.copy()
    g.thumbnail((max(1, int(max_w)), max(1, int(max_h))), Image.Resampling.LANCZOS)
    return g.point(lambda x: 0 if x < 128 else 255, mode="L")


def _paste_glyph(canvas: Image.Image, glyph: Image.Image, x: float, y: float) -> None:
    mask = glyph.point(lambda v: 255 if v < 128 else 0)
    canvas.paste(0, (int(x), int(y)), mask)


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
    max_gw = (usable_w - (cols - 1) * GAP) / cols if cols else usable_w
    max_gh = (usable_h - (rows - 1) * GAP) / rows if rows else usable_h
    g = _fit_glyph(glyph, max_gw, max_gh)
    gw, gh = g.width, g.height
    group_w = cols * gw + (cols - 1) * GAP
    group_h = rows * gh + (rows - 1) * GAP
    ox = origin_x + (usable_w - group_w) / 2
    oy = origin_y + (usable_h - group_h) / 2
    for c, r in cells:
        _paste_glyph(canvas, g, ox + c * (gw + GAP), oy + r * (gh + GAP))


def place_five(
    canvas: Image.Image,
    glyph: Image.Image,
    *,
    origin_x: float,
    origin_y: float,
    usable_w: float,
    usable_h: float,
) -> None:
    """Minnesota / traditional 5-dot: 1 on top, then two rows of two."""
    max_gw = (usable_w - GAP) / 2
    max_gh = (usable_h - 2 * GAP) / 3
    g = _fit_glyph(glyph, max_gw, max_gh)
    gw, gh = g.width, g.height
    group_w = 2 * gw + GAP
    group_h = 3 * gh + 2 * GAP
    ox = origin_x + (usable_w - group_w) / 2
    oy = origin_y + (usable_h - group_h) / 2
    positions = [
        (ox + (group_w - gw) / 2, oy),
        (ox, oy + gh + GAP),
        (ox + gw + GAP, oy + gh + GAP),
        (ox, oy + 2 * (gh + GAP)),
        (ox + gw + GAP, oy + 2 * (gh + GAP)),
    ]
    for x, y in positions:
        _paste_glyph(canvas, g, x, y)


def place_seven(
    canvas: Image.Image,
    glyph: Image.Image,
    *,
    origin_x: float,
    origin_y: float,
    usable_w: float,
    usable_h: float,
) -> None:
    """Traditional American 7-dot: row of 3, center, row of 3."""
    max_gw = (usable_w - 2 * GAP) / 3
    max_gh = (usable_h - 2 * GAP) / 3
    g = _fit_glyph(glyph, max_gw, max_gh)
    gw, gh = g.width, g.height
    group_w = 3 * gw + 2 * GAP
    group_h = 3 * gh + 2 * GAP
    ox = origin_x + (usable_w - group_w) / 2
    oy = origin_y + (usable_h - group_h) / 2
    positions = [
        (ox, oy),
        (ox + gw + GAP, oy),
        (ox + 2 * (gw + GAP), oy),
        (ox + gw + GAP, oy + gh + GAP),
        (ox, oy + 2 * (gh + GAP)),
        (ox + gw + GAP, oy + 2 * (gh + GAP)),
        (ox + 2 * (gw + GAP), oy + 2 * (gh + GAP)),
    ]
    for x, y in positions:
        _paste_glyph(canvas, g, x, y)


def cell_positions(n: int) -> list[tuple[int, int]]:
    layouts = {
        1: [(0, 0)],
        2: [(0, 0), (1, 0)],  # side-by-side (Minnesota)
        3: [(0, 0), (0, 1), (0, 2)],
        4: [(0, 0), (1, 0), (0, 1), (1, 1)],
        6: [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)],
        8: [(c, r) for r in range(4) for c in range(2)],
        9: [(c, r) for r in range(3) for c in range(3)],
    }
    return layouts[n]


def main() -> None:
    one_src = AI / "1-dot-print.png"
    bobber_src = AI / "bobber-print.png"
    soap_src = AI / "soap-dragon-print.png"
    for p in (one_src, bobber_src, soap_src):
        if not p.exists():
            raise SystemExit(f"Missing master: {p}")

    OUT.mkdir(parents=True, exist_ok=True)
    MODEL.mkdir(parents=True, exist_ok=True)

    one_glyph = thicken_black(to_bw(Image.open(one_src)), pixels=2)
    one_glyph = one_glyph.crop(content_bbox(one_glyph))

    bobber = thicken_black(to_bw(Image.open(bobber_src)), pixels=2)
    bobber = bobber.crop(content_bbox(bobber))

    dims = {
        1: (1, 1),
        2: (2, 1),
        3: (1, 3),
        4: (2, 2),
        6: (2, 3),
        8: (2, 4),
        9: (3, 3),
    }
    ox, oy, uw, uh = motif_region()

    for n in range(1, 10):
        canvas = Image.new("L", (PNG_W, PNG_H), 255)
        glyph = one_glyph if n == 1 else bobber
        if n == 5:
            place_five(canvas, glyph, origin_x=ox, origin_y=oy, usable_w=uw, usable_h=uh)
        elif n == 7:
            place_seven(canvas, glyph, origin_x=ox, origin_y=oy, usable_w=uw, usable_h=uh)
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
            canvas.save(dest / f"{n}-dot.png")
        print(f"Wrote {n}-dot.png (numeral {n})")

    soap = thicken_black(to_bw(Image.open(soap_src)), pixels=2)
    crop = soap.crop(content_bbox(soap))
    crop.thumbnail((PNG_W - 2 * MARGIN, PNG_H - 2 * MARGIN), Image.Resampling.LANCZOS)
    crop = crop.point(lambda x: 0 if x < 128 else 255, mode="L")
    full = Image.new("L", (PNG_W, PNG_H), 255)
    full.paste(crop, ((PNG_W - crop.width) // 2, (PNG_H - crop.height) // 2))
    for dest in (OUT, MODEL):
        full.save(dest / "soap-dragon.png")
    print("Wrote soap-dragon.png (no numeral)")


if __name__ == "__main__":
    main()
