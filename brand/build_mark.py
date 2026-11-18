#!/usr/bin/env python3
"""build_mark.py — the ThinkUI cloud mark, as vectors and as rasters.

The mark is one silhouette: six offset lobes and a single trailing thought. It is drawn
from circles on a 64-unit grid so every size is generated from the same geometry rather
than redrawn, and so the raster icons can be rendered at true pixel size instead of being
downscaled from one big image (which is what makes favicons muddy).

    python build_mark.py

Writes into ../assets/img:
    mark.svg             bare mark, currentColor           (inlined where it must follow text)
    mark-block.svg       cream tile + dark mark            (app icon, social avatar)
    favicon.svg          same as the block, for the tab
    logo.svg             lockup for light surfaces
    logo-inverse.svg     lockup for dark surfaces (header, footer)
    favicon-{16..512}.png, apple-touch-icon.png, favicon.ico
"""

from __future__ import annotations

import os
import struct

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.abspath(os.path.join(HERE, "..", "assets", "img"))

GRID = 64
# The silhouette, before the 1.1x horizontal stretch that was chosen as "Wide".
LOBES = [(25, 28, 12.0), (39, 25, 9.0), (46, 33, 7.0), (38, 40, 9.0), (25, 40, 9.5), (33, 33, 10.5)]
DOT = (11.5, 53.0, 3.0)
# The icon keeps the same silhouette but a larger, closer thought: at 16px the lockup's
# 0.65px dot is a smudge, and the whole point of the mark is that it is thinking.
DOT_ICON = (12.2, 51.6, 4.6)
STRETCH = 1.1

CREAM = "#f0dcc8"
INK = "#141414"
LIGHT_INK = "#0c0c0d"
ON_DARK = "#faf9f7"

# The wordmark is the existing drawing, not re-typed: same path, same baseline, so the
# lockup keeps the letterforms the brand already shipped.
WORD_PATH = None
WORD_X, WORD_Y, WORD_SCALE = 38.0, 19.0938, 0.016785
LOCK_W = 94.31
LOCK_H = 26.0


def word_path() -> str:
    """The wordmark path, kept beside this script.

    It is read from brand/wordmark-path.txt rather than logo.svg because this script
    writes logo.svg: reading the file it is about to replace would work once and then
    find the new lockup instead, which is the kind of bug that ships a blank logo.
    """
    global WORD_PATH
    if WORD_PATH:
        return WORD_PATH
    with open(os.path.join(HERE, "wordmark-path.txt"), encoding="utf-8") as fh:
        WORD_PATH = fh.read().strip()
    return WORD_PATH


def stretched(cx: float) -> float:
    """The horizontal stretch, about the centre of the grid."""
    return (cx - GRID / 2) * STRETCH + GRID / 2


def mark_svg(fill: str, transform: str = "", dot=DOT) -> str:
    body = "".join(
        f'<circle cx="{stretched(cx):.2f}" cy="{cy}" r="{r}" fill="{fill}"/>' for cx, cy, r in LOBES
    ) + f'<circle cx="{stretched(dot[0]):.2f}" cy="{dot[1]}" r="{dot[2]}" fill="{fill}"/>'
    return f'<g transform="{transform}">{body}</g>' if transform else f"<g>{body}</g>"


def extents(dot=DOT):
    """Bounding box of the stretched silhouette, including the thought."""
    xs, ys = [], []
    for cx, cy, r in list(LOBES) + [dot]:
        x = stretched(cx)
        xs += [x - r, x + r]
        ys += [cy - r, cy + r]
    return min(xs), min(ys), max(xs), max(ys)


def block_svg(mark_fill: str = INK, tile: str = CREAM) -> str:
    """The app icon: a cream tile with the mark inset to a ~10% safe area."""
    x0, y0, x1, y1 = extents(DOT_ICON)
    s = (GRID * 0.80) / max(x1 - x0, y1 - y0)
    tx = (GRID - (x1 - x0) * s) / 2 - x0 * s
    ty = (GRID - (y1 - y0) * s) / 2 - y0 * s
    body = mark_svg(mark_fill, f"translate({tx:.2f} {ty:.2f}) scale({s:.5f})", DOT_ICON)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" '
        f'role="img" aria-label="ThinkUI"><title>ThinkUI</title>'
        f'<rect width="64" height="64" rx="15" fill="{tile}"/>'
        f'<rect x="1" y="1" width="62" height="62" rx="14.2" fill="none" stroke="#000000" '
        f'stroke-opacity=".10" stroke-width="1.2"/>{body}</svg>'
    )


def lockup_svg(mark_fill: str, word_fill: str) -> str:
    s = LOCK_H / 43.0
    tx = -6.45 * s
    ty = -13.0 * s
    mark = mark_svg(mark_fill, f"translate({tx:.3f} {ty:.3f}) scale({s:.5f})")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LOCK_W} {LOCK_H}" '
        f'width="{LOCK_W}" height="{LOCK_H}" role="img" aria-label="ThinkUI"><title>ThinkUI</title>'
        f'{mark}<g transform="translate({WORD_X} {WORD_Y}) scale({WORD_SCALE})">'
        f'<path fill="{word_fill}" d="{word_path()}"/></g></svg>'
    )


def raster(size: int, tile: str | None, mark_fill: str, ss: int = 8) -> Image.Image:
    """Draw at ss x and resample: circles at 16px need the supersample to stay round."""
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if tile:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=S * 15 / 64, fill=tile)
    dot = DOT_ICON if tile else DOT
    x0, y0, x1, y1 = extents(dot)
    if tile:
        s = (S * 0.80) / max(x1 - x0, y1 - y0)
        off_x = (S - (x1 - x0) * s) / 2 - x0 * s
        off_y = (S - (y1 - y0) * s) / 2 - y0 * s
    else:
        s = S / GRID
        off_x, off_y = 0.0, 0.0

    def ellipse(cx, cy, r):
        x, y = stretched(cx), cy
        d.ellipse([off_x + (x - r) * s, off_y + (y - r) * s,
                   off_x + (x + r) * s, off_y + (y + r) * s], fill=mark_fill)

    for lobe in LOBES:
        ellipse(*lobe)
    ellipse(*dot)
    return im.resize((size, size), Image.LANCZOS)


def write_ico(path: str, sizes=(16, 32, 48, 64)) -> None:
    """A multi-frame .ico, written directly: Pillow's ico writer only takes one image."""
    frames = [raster(s, CREAM, INK).convert("RGBA") for s in sizes]
    pngs = []
    for f in frames:
        tmp = path + ".tmp.png"
        f.save(tmp, "PNG")
        pngs.append(open(tmp, "rb").read())
        os.remove(tmp)
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries, blobs = b"", b""
    for size, png in zip(sizes, pngs):
        entries += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        blobs += png
    open(path, "wb").write(header + entries + blobs)


def main() -> None:
    os.makedirs(IMG, exist_ok=True)
    files = {
        "mark.svg": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" '
            f'role="img" aria-label="ThinkUI"><title>ThinkUI</title>{mark_svg("currentColor")}</svg>'
        ),
        "mark-block.svg": block_svg(),
        "favicon.svg": block_svg(),
        "logo.svg": lockup_svg(LIGHT_INK, LIGHT_INK),
        "logo-inverse.svg": lockup_svg(CREAM, ON_DARK),
    }
    for name, text in files.items():
        open(os.path.join(IMG, name), "w", encoding="utf-8").write(text)

    for size in (16, 32, 48, 64, 128, 256, 512):
        raster(size, CREAM, INK).save(os.path.join(IMG, "favicon-%d.png" % size), "PNG", optimize=True)
    # Apple applies its own mask: full-bleed, opaque, no pre-rounded corners.
    raster(180, CREAM, INK).convert("RGB").save(os.path.join(IMG, "apple-touch-icon.png"), "PNG", optimize=True)
    write_ico(os.path.join(IMG, "favicon.ico"))
    print("wrote mark, block, favicon, lockups, PNGs and .ico into", IMG)


if __name__ == "__main__":
    main()
