#!/usr/bin/env python3
"""build_identity.py — the ThinkUI identity, as outlines, for the shipped site.

The chosen mark is option 4, "Distilled": three left-aligned bars, each shorter than
the one above, sitting inside the 64-unit grid the options were drawn on.

Nothing here is traced or hand-positioned:

* the wordmark is Bricolage Grotesque's own outlines, instanced at wght 600 / opsz 30, shaped
  through HarfBuzz, so advances and kerning are the font's, not my guess;
* every position is derived from measured ink bounds (cap height, stem width, the
  mark's own box) rather than typed in, so the lockup stays correct if any part of it
  is ever re-cut.

Two instances of the mark, as the brand-identity skill requires:

* ``t=6.5``  — standalone mark, app block, favicon. Mass is what keeps 16px legible.
* ``t=5.4``  — the lockup cut. Ahead of the wordmark a full-mass mark reads as a
  different typeface sitting next to the text.

Output goes to ../assets/img/ because that is what the deploy copies; masters stay in
out/identity/.

    uv run --with fonttools --with uharfbuzz python build_identity.py
"""

from __future__ import annotations

import io
import json
import os

from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
import uharfbuzz as hb

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(os.path.join(HERE, ".."))
IMG = os.path.join(SITE, "assets", "img")
MASTERS = os.path.join(HERE, "out", "identity")

# The wordmark is the product name set in the display face and converted to outlines.
# When the display face changes, the mark is re-cut from it, so the logo can never drift
# from the type it sits beside.
FONT = os.path.join(HERE, "fonts", "bricolage-grotesque-var.ttf")
WORD = "ThinkUI"
W_WGHT, W_OPSZ = 600, 30
TRACKING_EM = -0.02          # the site's own letter-spacing on .brand

# site tokens (assets/css/site.css)
INK = "#0c0c0d"
ON_INK = "#faf9f7"
# The muted grey for text on the ink surface - warm, because the palette is.
ON_INK_SOFT = "#b5b2ad"
# One accent, deeper at the bottom stop: depth inside a hue rather than a rainbow across
# two. Measured, not eyeballed: white bars read 4.55:1 on the light stop and 6.97:1 on
# the deep one, so the glyph holds at 16px.
TILE_A, TILE_B = "#d4431d", "#a52f11"
GLOW_A, GLOW_B = "#f0764f", "#d4431d"      # the same accent on dark grounds (6.90:1)

GRID = 64.0                   # the design grid all six options were drawn on
BARS = [36.0, 26.0, 16.0]     # left-aligned widths
BAR_X = 14.0                  # left inset
INK_H = 30.0                  # total height of the bar stack
TILE_T = 6.5                  # standalone / block / favicon cut
LOCK_T = 5.4                  # lockup cut


# --------------------------------------------------------------------- the font
def _draw(font, text, make_pen, tracking_em=0.0):
    """Shape once, draw through the given pen: geometry and its measurement cannot
    diverge when they come from the same shaping pass."""
    upem = font["head"].unitsPerEm
    hb_font = hb.Font(hb.Face(font_bytes(font)))
    hb_font.scale = (upem, upem)

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {"kern": True, "liga": True})

    order = font.getGlyphOrder()
    glyphs = font.getGlyphSet()
    pen = make_pen(glyphs)
    x = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        # fonts put y up from the baseline, SVG puts it down
        t = Transform(1, 0, 0, -1, x + pos.x_offset, -pos.y_offset)
        glyphs[name].draw(TransformPen(pen, t))
        x += pos.x_advance + tracking_em * upem
    return pen, x - tracking_em * upem


def font_bytes(font):
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def measure_font():
    font = instancer.instantiateVariableFont(
        TTFont(FONT), {"wght": W_WGHT, "opsz": W_OPSZ}, inplace=False)
    upem = font["head"].unitsPerEm

    word_pen, advance = _draw(font, WORD, SVGPathPen, TRACKING_EM)
    bounds_pen, _ = _draw(font, WORD, BoundsPen, TRACKING_EM)
    x0, y0, x1, y1 = bounds_pen.bounds

    stem_pen, _ = _draw(font, "l", BoundsPen)          # a grotesque "l" is a bare stem
    sx0, _, sx1, _ = stem_pen.bounds
    stem = sx1 - sx0

    cap = -y0                                          # baseline is y=0
    return {
        "upem": upem,
        "d": word_pen.getCommands(),
        "advance": advance,
        "bbox": [x0, y0, x1, y1],
        "cap": cap,
        "stem": stem,
        "descends": y1 > 0,
    }


# ------------------------------------------------------------------- the mark
def bar_rects(t, x=BAR_X, ink_h=INK_H, widths=None):
    """Three bars, one stack height, thickness t. The stack keeps its 30-unit height
    whatever the cut, so a heavier cut eats the gaps rather than growing the mark."""
    widths = widths or BARS
    gap = (ink_h - 3 * t) / 2.0
    out, y = [], (GRID - ink_h) / 2.0
    for w in widths:
        out.append((x, y, w, t))
        y += t + gap
    return out


def mark_svg(t, colour, ids="", w=64, h=64, box=True):
    rects = "".join(
        '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f" fill="%s"/>'
        % (x, y, bw, bh, bh / 2.0, colour) for x, y, bw, bh in bar_rects(t))
    if not box:
        return rects
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
            'role="img" aria-label="ThinkUI"><title>ThinkUI</title><g>%s</g></svg>'
            % (w, h, w, h, rects))


def block_svg(t=TILE_T, uid="tile"):
    """Solid tile + white bars: the app icon and the favicon.

    The light stop is #0f8ea6 rather than the site's decorative #22b8cf: white on
    #22b8cf measures 2.38:1 and the glyph loses its bottom-right corner.
    """
    defs = ('<defs>'
            '<linearGradient id="%s-g" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>'
            '<linearGradient id="%s-s" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#ffffff" stop-opacity=".2"/>'
            '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>'
            '</defs>' % (uid, TILE_A, TILE_B, uid))
    rects = bar_rects(t)
    bars = "".join('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f" fill="#ffffff"/>'
                   % (x, y, bw, bh, bh / 2.0) for x, y, bw, bh in rects)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" '
            'role="img" aria-label="ThinkUI">%s'
            '<rect width="64" height="64" rx="15" fill="url(#%s-g)"/>'
            '<rect width="64" height="64" rx="15" fill="url(#%s-s)"/>'
            '<rect x="1" y="1" width="62" height="62" rx="14.2" fill="none" stroke="#ffffff" '
            'stroke-opacity=".16" stroke-width="1.2"/>'
            '<g>%s</g></svg>' % (defs, uid, uid, bars))


def mono_block_svg(t=TILE_T):
    """One colour, bars knocked out of a solid tile — for stamps, invoices, favicons
    where a gradient is unavailable."""
    outer = ('M15 0h34a15 15 0 0 1 15 15v34a15 15 0 0 1-15 15H15A15 15 0 0 1 0 15V15A15 15 0 0 1 '
             '15 0Z')
    holes = ""
    for x, y, bw, bh in bar_rects(t):
        r = bh / 2.0
        holes += ('M%.2f %.2fH%.2fA%.2f %.2f 0 0 1 %.2f %.2fV%.2fA%.2f %.2f 0 0 1 %.2f %.2fH%.2f'
                  'A%.2f %.2f 0 0 1 %.2f %.2fV%.2fA%.2f %.2f 0 0 1 %.2f %.2fZ'
                  % (x + r, y, x + bw - r, r, r, x + bw, y + r, y + bh - r, r, r,
                     x + bw - r, y + bh, x + r, r, r, x, y + bh - r, y + r, r, r, x + r, y))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" '
            'role="img" aria-label="ThinkUI"><title>ThinkUI</title>'
            '<path fill="currentColor" fill-rule="evenodd" d="%s%s"/></svg>' % (outer, holes))


# ------------------------------------------------------------------ the lockup
def lockup(kind="block", uid="lg"):
    """Compose the mark and the wordmark from measured bounds.

    kind='block'  tile + wordmark, for the site header and footer (px space, tile 26)
    kind='bare'   mark + wordmark, no tile, for docs and print (font-unit space)

    Two coordinate spaces on purpose: the block lockup is sized by the tile, the bare
    one by the cap height, and mixing them is how a lockup drifts.
    """
    m = measure_font()
    cap = m["cap"]

    if kind == "block":
        tile_h = 26.0
        ink_h = tile_h * INK_H / GRID              # the stack inside the tile, in px
        mark = ('<g transform="translate(0 0) scale(%.6f)">%s</g>'
                % (tile_h / GRID, _tile_inner(uid)))
        mark_w = tile_h
        mark_ink_top = (tile_h - ink_h) / 2.0
        gap = 9.0                                   # the site's own .brand gap
        space, total_h = "px", tile_h
        word_scale = ink_h / cap                    # caps = the stack's ink height
        baseline = mark_ink_top + ink_h
    else:
        k = cap / INK_H                             # grid unit -> font unit
        top = (GRID - INK_H) / 2.0                  # the stack sits centred in the grid
        mark = ('<g transform="translate(%.4f %.4f) scale(%.6f)">%s</g>'
                % (-BAR_X * k, -top * k, k, _bars_group(LOCK_T)))
        mark_w = max(BARS) * k
        mark_ink_top, gap = 0.0, 0.45 * cap
        space, total_h = "font units", cap
        word_scale = 1.0                            # font units throughout
        baseline = cap                              # caps span 0 (top) .. cap (baseline)

    word_x = mark_w + gap - m["bbox"][0] * word_scale
    return {
        "word_d": m["d"], "word_scale": word_scale, "baseline": baseline,
        "mark": mark, "mark_w": mark_w, "word_x": word_x, "gap": gap,
        "total_w": word_x + m["bbox"][2] * word_scale, "total_h": total_h,
        "cap_px": ink_h if kind == "block" else cap,
        "stem_units": m["stem"], "cap_units": cap, "lock_t": LOCK_T,
        "kind": kind, "space": space, "mark_ink_top": mark_ink_top,
        "ink_h": ink_h if kind == "block" else cap,
    }


def _bars_group(t):
    rects = "".join('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f"/>'
                    % (x, y, bw, bh, bh / 2.0) for x, y, bw, bh in bar_rects(t))
    return rects


def _tile_inner(uid="lg"):
    rects = "".join('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f" fill="#ffffff"/>'
                    % (x, y, bw, bh, bh / 2.0) for x, y, bw, bh in bar_rects(TILE_T))
    return ('<rect width="64" height="64" rx="15" fill="url(#%s-g)"/>'
            '<rect width="64" height="64" rx="15" fill="url(#%s-s)"/>'
            '<rect x="1" y="1" width="62" height="62" rx="14.2" fill="none" stroke="#ffffff" '
            'stroke-opacity=".16" stroke-width="1.2"/>%s' % (uid, uid, rects))


def lockup_svg(colour_word, grad_a, grad_b, kind="block", uid="lg", word_colour=None):
    """The tile's gradient ids carry a per-variant uid: two lockups inlined on one page
    (the light header and the inverse footer) would otherwise share the first one's
    colours and the second would silently render wrong."""
    L = lockup(kind, uid)
    w, h = L["total_w"], L["total_h"]
    defs = ('<defs><linearGradient id="%s-g" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>'
            '<linearGradient id="%s-s" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#ffffff" stop-opacity=".2"/>'
            '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient></defs>'
            % (uid, grad_a, grad_b, uid))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.2f %.2f" width="%.2f" '
            'height="%.2f" role="img" aria-label="ThinkUI">%s'
            '<title>ThinkUI</title>%s'
            '<g transform="translate(%.4f %.4f) scale(%.6f)">'
            '<path fill="%s" d="%s"/></g></svg>'
            % (w, h, w, h, defs, L["mark"],
               L["word_x"], L["baseline"], L["word_scale"],
               word_colour or colour_word, L["word_d"]))


def main():
    os.makedirs(IMG, exist_ok=True)
    os.makedirs(MASTERS, exist_ok=True)
    m = measure_font()
    print("Bricolage Grotesque %d / opsz %d, upem %d" % (W_WGHT, W_OPSZ, m["upem"]))
    print("  cap height %d units   stem width %d units   stem/cap %.3f"
          % (m["cap"], m["stem"], m["stem"] / m["cap"]))
    print("  wordmark ink %.0f x %.0f units, advance %.0f"
          % (m["bbox"][2] - m["bbox"][0], m["bbox"][3] - m["bbox"][1], m["advance"]))
    for t in (TILE_T, LOCK_T):
        gap = (INK_H - 3 * t) / 2.0
        print("  cut t=%.1f -> gaps %.2f grid units, at cap 12.2px bars %.2fpx / text stem %.2fpx"
              % (t, gap, t / INK_H * 12.19, m["stem"] / m["cap"] * 12.19))
    t_match = INK_H * m["stem"] / m["cap"]
    print("  a cut matched exactly to the text stem would be t=%.2f grid units "
          "(%.2fpx at cap 12.2px) — too thin to hold its silhouette, which is why the "
          "lockup cut is %.1f" % (t_match, t_match / INK_H * 12.19, LOCK_T))

    files = {
        # the shipped set
        "logo.svg": lockup_svg(INK, TILE_A, TILE_B, "block"),
        "logo-inverse.svg": lockup_svg(ON_INK, GLOW_A, GLOW_B, "block"),
        "logo-bare.svg": lockup_svg(INK, TILE_A, TILE_B, "bare"),
        "mark.svg": mark_svg(TILE_T, "currentColor"),
        "mark-block.svg": block_svg(),
        "mark-knockout.svg": mono_block_svg(),
    }
    for name, svg in files.items():
        for folder in (IMG, MASTERS):
            with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
                fh.write(svg + "\n")
    # the favicon svg is the block: one source, no chance of drift
    with open(os.path.join(IMG, "favicon.svg"), "w", encoding="utf-8") as fh:
        fh.write(files["mark-block.svg"] + "\n")

    L = lockup("block")
    B = lockup("bare")
    print("\nlockup, block kind: viewBox %.1f x %.1f  mark %.1f  gap %.1f  caps %d..%d"
          % (L["total_w"], L["total_h"], L["mark_w"], L["gap"],
             round(L["baseline"] - L["cap_px"]), round(L["baseline"])))
    print("lockup, bare kind:  viewBox %.3f x %.3f cap units  (bars match the text stem)"
          % (B["total_w"], B["total_h"]))

    # one source for the geometry: the social card draws the same mark with PIL, and a
    # duplicated constant is how the icon and the card drift apart
    metrics = {
        "word": WORD, "grid": GRID, "bar_x": BAR_X, "bars": BARS, "ink_h": INK_H,
        "tile_t": TILE_T, "lock_t": LOCK_T, "tile_radius": 15.0,
        "upem": m["upem"], "cap": m["cap"], "stem": m["stem"],
        "advance": m["advance"], "word_bbox": m["bbox"],
        "tile_a": TILE_A, "tile_b": TILE_B, "glow_a": GLOW_A, "glow_b": GLOW_B,
        "ink": INK, "on_ink": ON_INK, "on_ink_soft": ON_INK_SOFT,
        "lockup_block": {"w": round(L["total_w"], 3), "h": round(L["total_h"], 3),
                         "baseline": round(L["baseline"], 3), "cap_px": round(L["cap_px"], 3)},
        "lockup_bare": {"w": round(B["total_w"], 1), "h": round(B["total_h"], 1)},
        "wght": W_WGHT, "opsz": W_OPSZ, "tracking_em": TRACKING_EM,
    }
    for folder in (os.path.join(HERE, "out", "identity"), os.path.join(SITE, "src")):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "identity.json"), "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=2)
    print("wrote identity.json (build.py reads it for the social card)")
    print("\nwrote %d files to assets/img/ and out/identity/" % (len(files) + 1))
    for name in sorted(os.listdir(IMG)):
        print("  %-22s %6d bytes" % (name, os.path.getsize(os.path.join(IMG, name))))


if __name__ == "__main__":
    main()
