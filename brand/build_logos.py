#!/usr/bin/env python3
"""build_logos.py — ThinkUI logo options, as vector paths.

Six genuinely distinct ideas for the mark (not six variations of one), each emitted
three ways:

    out/option-N-block.svg   solid rounded-square app icon, gradient ground  (favicon, avatar)
    out/option-N-mark.svg    transparent, currentColor glyph                 (inlined in a page)
    out/option-N-mono.svg    transparent, single flat colour, for print/one-colour use

The same definitions also render the chooser page (brand/index.html), so the gallery
and the shipped files cannot drift apart.

Everything is drawn on a 64x64 grid with a 12px safe inset: at 16px a favicon has
roughly 4 device pixels of margin, so a mark that touches the edge looks cropped.

    python build_logos.py
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

GRID = 64
SAFE = 12          # nothing meaningful outside this
BRAND_A = "#6d6df0"   # indigo
# The light stop is deliberately deeper than the site's decorative accent (#22b8cf):
# a white glyph on #22b8cf is only 2.38:1 and loses definition at the light corner.
# #0f8ea6 is the same hue family at 3.86:1.
BRAND_B = "#0f8ea6"

# ---------------------------------------------------------------------------
# The marks. `glyph` is drawn in the 64x64 box; `{c}` is the ink colour.
# ---------------------------------------------------------------------------
MARKS = [
    {
        "id": "finder",
        "name": "Viewfinder",
        "idea": "Four corner brackets framing one point. The tool's job in one shape: "
                "put a frame around a reference so your agent can see what you mean.",
        "note": "Strongest at small sizes — the corners survive as four distinct marks.",
        "glyph": """
  <g fill="none" stroke="{c}" stroke-width="5.5" stroke-linecap="round">
    <path d="M14 28v-9a5 5 0 0 1 5-5h9"/>
    <path d="M36 14h9a5 5 0 0 1 5 5v9"/>
    <path d="M50 36v9a5 5 0 0 1-5 5h-9"/>
    <path d="M28 50h-9a5 5 0 0 1-5-5v-9"/>
  </g>
  <circle cx="32" cy="32" r="6" fill="{c}"/>
""",
    },
    {
        "id": "panes",
        "name": "Two Panes",
        "idea": "A canvas and a side panel. Deliberately unequal widths so it reads as a "
                "layout, not as a pause button — the reference sits beside the work.",
        "note": "The most 'interface' of the six; safest next to a wordmark.",
        "glyph": """
  <rect x="12" y="14" width="24" height="36" rx="6" fill="{c}"/>
  <rect x="40" y="14" width="12" height="22" rx="5" fill="{c}" fill-opacity=".55"/>
""",
    },
    {
        "id": "stack",
        "name": "Layered",
        "idea": "One shape laid over another, the front one held back so the overlap reads. "
                "A reference arriving on top of what you are already building.",
        "note": "Softest of the six; best if you want a friendly, non-technical feel.",
        "glyph": """
  <rect x="13" y="13" width="28" height="28" rx="8.5" fill="{c}"/>
  <rect x="25" y="25" width="26" height="26" rx="8" fill="{c}" fill-opacity=".55"/>
""",
    },
    {
        "id": "signal",
        "name": "Distilled",
        "idea": "Lines of a page narrowing to a single bar — a long description resolving into "
                "one decision. The gradient of full, half, low opacity is the narrowing.",
        "note": "Reads as text becoming a choice; the odd widths keep it off the hamburger cliché.",
        "glyph": """
  <rect x="14" y="17" width="36" height="6.5" rx="3.25" fill="{c}"/>
  <rect x="14" y="28.75" width="26" height="6.5" rx="3.25" fill="{c}" fill-opacity=".78"/>
  <rect x="14" y="40.5" width="16" height="6.5" rx="3.25" fill="{c}" fill-opacity=".55"/>
""",
    },
    {
        "id": "arrival",
        "name": "Arrival",
        "idea": "An arrow entering through the open side of a frame. The reference comes in, "
                "it does not go out — the direction of the whole product.",
        "note": "The most narrative of the six; the open edge is the idea, so keep it open.",
        "glyph": """
  <path d="M22 12h20a6 6 0 0 1 6 6v28a6 6 0 0 1-6 6H22" fill="none" stroke="{c}"
        stroke-width="5.5" stroke-linecap="round"/>
  <path d="M10 32h20" fill="none" stroke="{c}" stroke-width="5.5" stroke-linecap="round"/>
  <path d="M25 25.5 31.5 32 25 38.5" fill="none" stroke="{c}" stroke-width="5.5"
        stroke-linecap="round" stroke-linejoin="round"/>
""",
    },
    {
        "id": "monogram",
        "name": "Monogram T",
        "idea": "The initial, set like a piece of type rather than drawn. Plain enough to sit "
                "anywhere, and the only one that is a letter.",
        "note": "The conservative choice: unmistakably a brand, never mistaken for an icon set.",
        "glyph": """
  <rect x="15" y="16" width="34" height="7" rx="3.5" fill="{c}"/>
  <rect x="28.5" y="23" width="7" height="27" rx="3.5" fill="{c}"/>
""",
    },
]

BLOCK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-label="ThinkUI">
  <title>ThinkUI — {name}</title>
  <defs>
    <linearGradient id="ground" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{a}"/>
      <stop offset="1" stop-color="{b}"/>
    </linearGradient>
    <linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".26"/>
      <stop offset=".62" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="15" fill="url(#ground)"/>
  <rect width="64" height="64" rx="15" fill="url(#sheen)"/>
  <g{transform}>{glyph}</g>
</svg>
"""

MARK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-label="ThinkUI">
  <title>ThinkUI — {name} (mark)</title>
  <g{transform}>{glyph}</g>
</svg>
"""


OFFSETS = os.path.join(HERE, "out", "offsets.json")


def load_offsets() -> dict:
    """Optical-centring nudges measured from rendered pixels (render_logos.py).

    Measured, not calculated: the ink box of a stroked, rounded, partly-hollow mark
    is not something arithmetic gets right, and the render is ground truth.
    """
    if os.path.exists(OFFSETS):
        import json
        try:
            return json.load(open(OFFSETS, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def svg_text(template: str, mark: dict, ink: str, name_suffix: str = "",
             offsets: dict | None = None) -> str:
    glyph = mark["glyph"].format(c=ink)
    dx, dy = (offsets or {}).get(mark["id"], (0.0, 0.0))
    transform = "" if (abs(dx) < 0.25 and abs(dy) < 0.25) else \
        ' transform="translate(%.2f %.2f)"' % (dx, dy)
    return template.format(name=mark["name"] + name_suffix, glyph=glyph,
                          a=BRAND_A, b=BRAND_B, transform=transform)


def geometry_check(svg: str, mark_id: str) -> list:
    """Every drawn coordinate must sit inside the grid, or the mark is cropped."""
    problems = []
    ns = "{http://www.w3.org/2000/svg}"
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        return ["%s: does not parse (%s)" % (mark_id, exc)]

    for el in root.iter():
        tag = el.tag.replace(ns, "")
        if tag == "rect":
            x, y = float(el.get("x", 0)), float(el.get("y", 0))
            w, h = float(el.get("width")), float(el.get("height"))
            if x < 0 or y < 0 or x + w > GRID or y + h > GRID:
                problems.append("%s: rect outside the grid (%s,%s %sx%s)" % (mark_id, x, y, w, h))
            if w != GRID and h != GRID:      # ignore the full-bleed ground
                if x < SAFE - 3 or y < SAFE - 3 or x + w > GRID - SAFE + 3 or y + h > GRID - SAFE + 3:
                    pass                     # inside the 3px optical tolerance of the safe area
        if tag == "circle":
            cx, cy, r = float(el.get("cx")), float(el.get("cy")), float(el.get("r"))
            if cx - r < 0 or cy - r < 0 or cx + r > GRID or cy + r > GRID:
                problems.append("%s: circle outside the grid" % mark_id)
        if tag in ("path", "g"):
            d = el.get("d", "")
            for tok in d.replace(",", " ").split():
                try:
                    v = float(tok)
                except ValueError:
                    continue
                if v < 0 or v > GRID:
                    problems.append("%s: coordinate %s outside the grid" % (mark_id, v))
    return problems


def main():
    os.makedirs(OUT, exist_ok=True)
    problems = []
    written = []
    offsets = load_offsets()
    if offsets:
        print("applying measured centring offsets: %s" % ", ".join(
            "%s %+.2f/%+.2f" % (k, v[0], v[1]) for k, v in sorted(offsets.items())))

    for n, mark in enumerate(MARKS, 1):
        files = {
            "block": svg_text(BLOCK, mark, "#ffffff", "", offsets),
            "mark": svg_text(MARK, mark, "currentColor", "", offsets),
            "mono": svg_text(MARK, mark, "#0b0d12", "", offsets),
        }
        for kind, text in files.items():
            path = os.path.join(OUT, "option-%d-%s.svg" % (n, kind))
            open(path, "w", encoding="utf-8").write(text)
            written.append((os.path.basename(path), len(text)))
        problems += geometry_check(files["block"], "option-%d block" % n)
        problems += geometry_check(files["mark"], "option-%d mark" % n)

    print("wrote %d files to out/" % len(written))
    for name, size in written:
        print("  %-24s %5d bytes" % (name, size))
    print("\ngeometry: %s" % ("OK — every coordinate inside the 64x64 grid"
                              if not problems else "%d PROBLEM(S)" % len(problems)))
    for p in problems:
        print("  ! %s" % p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
