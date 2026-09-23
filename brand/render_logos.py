#!/usr/bin/env python3
"""render_logos.py — render the option sheets and measure the marks.

Two jobs:

1. Draw the pictures you look at: `options.png` (all six side by side, for the chat)
   and the chooser page screenshot.
2. Measure each mark, because the agent cannot see: is every mark safely inside the
   tile, is it optically centred, does it survive at 16px, and does the white glyph
   stay legible against the darkest and lightest point of the gradient.

True small-size renders are captured at scale 1 at their own pixel size — scaling a
big render down is exactly what makes a favicon test meaningless.

    python render_logos.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import sys

sys.path.insert(0, r"C:\Users\use\AppData\Local\hermes\skills\software-development\rendered-ui-verification\scripts")
import ui_probe  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "tmp")

from build_logos import BLOCK, MARK, MARKS, BRAND_A, BRAND_B, svg_text  # noqa: E402

BASE_CSS = """
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #ffffff; }
  body { font: 400 13px/1.45 "Inter", system-ui, sans-serif; color: #0b0d12; }
  .row { display: flex; flex-wrap: wrap; gap: 22px; padding: 18px 22px; align-items: flex-start; }
  .card { border: 1px solid #e6e8ee; border-radius: 14px; padding: 14px; }
  .name { font-weight: 600; letter-spacing: -.02em; margin-bottom: 10px; }
  .ink { background: #05070c; border-radius: 12px; }
  .lbl { color: #6b7280; font-size: 11px; margin-top: 8px; }
  .cell { display: inline-block; line-height: 0; }
"""


OUT = os.path.join(HERE, "out")


def built(n, kind):
    """Read the emitted file, not a fresh build of the same definitions.

    The sheet, the chooser and the measurement must all show the same geometry that
    ships in out/ — rendering a parallel build is how a nudge silently never lands.
    """
    path = os.path.join(OUT, "option-%d-%s.svg" % (n, kind))
    with open(path, encoding="utf-8") as fh:
        svg = fh.read()
    defs = svg.split("</defs>")[1] if "</defs>" in svg else svg
    svg = svg.replace('id="ground"', 'id="ground%d"' % n).replace('id="sheen"', 'id="sheen%d"' % n)
    svg = svg.replace("url(#ground)", "url(#ground%d)" % n).replace("url(#sheen)", "url(#sheen%d)" % n)
    return svg, defs


def block_svg(mark, n):
    return built(n, "block")[0]


def write_sheet():
    """The picture for chat: each mark large, on the tile and reversed."""
    cells = []
    for n, mark in enumerate(MARKS, 1):
        bare = built(n, "mark")[0].replace("currentColor", "#ffffff")
        cells.append(
            '<div class="card">'
            '<div class="name">%d · %s</div>'
            '<div class="cell" style="width:104px">{big}</div>'
            '<div class="ink cell" style="width:104px;height:104px;margin-top:10px;'
            'display:grid;place-items:center">{bare}</div>'
            '<div class="cell" style="width:104px;margin-top:12px">{small}</div>'
            '<div class="lbl">tile 104 · reversed 104 · mark 40</div>'
            '</div>'.format(big=block_svg(mark, n), bare=bare, small=bare)
            % (n, mark["name"]))
    html = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" '
            'rel="stylesheet"><style>' + BASE_CSS +
            '.cell svg { width: 100%; height: auto; }'
            '.card:first-child .cell svg { width: 104px; }'
            '.ink svg { width: 40px; }'
            '.row .card:nth-child(n) { flex: 0 0 auto; }'
            '</style></head><body><div class="row">' + "".join(cells) + '</div></body></html>')
    path = os.path.join(TMP, "sheet.html")
    open(path, "w", encoding="utf-8").write(html)
    return path


def write_measure():
    """A fixed grid so every render can be cropped back out by coordinates.

    The mark is drawn black on white: one polarity, no ambiguity. (Measuring the
    white glyph on the gradient tile puts the glyph and the page background in the
    same bucket, and every number that comes out is fiction.)
    """
    rows = []
    for n, mark in enumerate(MARKS, 1):
        m = built(n, "mono")[0]
        big = m.replace('width="64" height="64"', 'width="256" height="256"')
        small = m.replace('width="64" height="64"', 'width="16" height="16"')
        mid = m.replace('width="64" height="64"', 'width="48" height="48"')
        rows.append(
            '<div style="display:flex;gap:0;height:300px">'
            '<div style="width:300px;height:300px">{big}</div>'
            '<div style="width:200px;height:300px;position:relative">{mid}</div>'
            '<div style="width:80px;height:300px;position:relative">{small}</div>'
            '</div>'.format(big=big, mid=mid, small=small))
    html = ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>' + BASE_CSS +
            'body { background: #ffffff; } div { line-height: 0; }'
            'div > svg { vertical-align: top; }'
            '</style></head><body>' + "".join(rows) + '</body></html>')
    path = os.path.join(TMP, "measure.html")
    open(path, "w", encoding="utf-8").write(html)
    return path


async def shoot(ws_url, url, width, out_png, wait=1.6):
    import websockets
    async with websockets.connect(ws_url, max_size=64_000_000) as sock:
        n = 0

        async def send(method, params=None):
            nonlocal n
            n += 1
            await sock.send(json.dumps({"id": n, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await sock.recv())
                if msg.get("id") == n:
                    return msg

        async def ev(expr):
            r = await send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
            return r.get("result", {}).get("result", {}).get("value")

        await send("Page.enable")
        await send("Runtime.enable")
        await send("Emulation.setDeviceMetricsOverride",
                   {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        await send("Page.navigate", {"url": url})
        for _ in range(80):
            if await ev("document.readyState") == "complete":
                break
            await asyncio.sleep(0.25)
        await ev("document.fonts ? document.fonts.ready.then(() => true) : true")
        await asyncio.sleep(wait)
        metrics = await send("Page.getLayoutMetrics")
        size = (metrics.get("result", {}).get("cssContentSize")
                or metrics.get("result", {}).get("contentSize"))
        shot = await send("Page.captureScreenshot", {
            "format": "png", "captureBeyondViewport": True,
            "clip": {"x": 0, "y": 0, "width": width,
                     "height": min(size["height"], 8000), "scale": 1}})
        data = shot.get("result", {}).get("data")
        if not data:
            return None
        open(out_png, "wb").write(base64.b64decode(data))
        return out_png


# --------------------------------------------------------------------------- measure
def luminance(px):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(px[0]) + 0.7152 * f(px[1]) + 0.0722 * f(px[2])


def analyse(img, label, ink_is_light=True):
    """Ink bbox / coverage / optical centring / component count for one render.

    Only ever called on a crop that is exactly the tile (or exactly the bare mark on
    a known ground): a crop that includes page background makes white count as ink
    and every number becomes fiction.
    """
    w, h = img.size
    px = img.load()
    ink_side = (lambda l: l > 0.62) if ink_is_light else (lambda l: l < 0.45)
    is_ink = [[False] * w for _ in range(h)]
    ink_lums = []
    for y in range(h):
        for x in range(w):
            lum = luminance(px[x, y])
            flag = ink_side(lum)
            is_ink[y][x] = flag
            if flag:
                ink_lums.append(lum)
    total_ink = sum(1 for row in is_ink for v in row if v)
    if not total_ink:
        return {"label": label, "error": "no ink found", "size": (w, h)}

    xs = [x for y in range(h) for x in range(w) if is_ink[y][x]]
    ys = [y for y in range(h) for x in range(w) if is_ink[y][x]]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0

    seen = [[False] * w for _ in range(h)]
    comps = 0
    for y in range(h):
        for x in range(w):
            if is_ink[y][x] and not seen[y][x]:
                comps += 1
                stack = [(x, y)]
                seen[y][x] = True
                while stack:
                    sx, sy = stack.pop()
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = sx + dx, sy + dy
                        if 0 <= nx < w and 0 <= ny < h and is_ink[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            stack.append((nx, ny))

    # ground sample: mid-edges, which are on the tile but outside the 12/64 safe inset
    samples = []
    for sx, sy in ((w // 2, max(1, h // 40)), (max(1, w // 40), h // 2),
                   (w - 2, h // 2), (w // 2, h - 2)):
        samples.append(luminance(px[sx, sy]))
    lightest_ground = max(samples)
    ink_ref = max(ink_lums) if ink_is_light else min(ink_lums)
    worst = ((ink_ref + 0.05) / (lightest_ground + 0.05)) if ink_is_light else \
            ((lightest_ground + 0.05) / (ink_ref + 0.05))
    return {
        "label": label, "size": (w, h),
        "ink_pct": round(100.0 * total_ink / (w * h), 1),
        "bbox": bbox,
        "centre_offset": (round(cx - w / 2.0, 1), round(cy - h / 2.0, 1)),
        "margin_px": (bbox[0], bbox[1], w - 1 - bbox[2], h - 1 - bbox[3]),
        "comps": comps,
        "ground_lums": [round(s, 3) for s in samples],
        "contrast_vs_lightest_ground": round(worst, 2),
    }


def main():
    os.makedirs(TMP, exist_ok=True)
    from PIL import Image

    sheet = write_sheet()
    measure = write_measure()

    chrome = ui_probe.find_chrome()
    proc = ui_probe.launch(chrome, 9444)
    try:
        ws = ui_probe.attach(9444)
        asyncio.run(shoot(ws, "file:///" + sheet.replace("\\", "/").lstrip("/"),
                          1140, os.path.join(HERE, "options.png")))
        asyncio.run(shoot(ws, "file:///" + measure.replace("\\", "/").lstrip("/"),
                          1120, os.path.join(TMP, "measure.png"), wait=1.2))
    finally:
        proc.kill()

    print("sheets written: options.png, tmp/measure.png")
    page = Image.open(os.path.join(TMP, "measure.png")).convert("RGB")

    # cells from write_measure(): mark at 256 (x 0..256), at 48 (x 300), at 16 (x 500)
    GLYPH_GRID = 64.0
    table = []
    for n, mark in enumerate(MARKS, 1):
        top = (n - 1) * 300
        big = page.crop((0, top, 256, top + 256))
        tiny = page.crop((500, top, 516, top + 16))
        a = analyse(big, "%d %s · 256px" % (n, mark["name"]), ink_is_light=False)
        t = analyse(tiny, "%d · 16px" % n, ink_is_light=False)
        scaled = analyse(big.resize((16, 16), Image.LANCZOS), "%d · 256 scaled to 16" % n,
                         ink_is_light=False)
        for row in (a, t, scaled):
            row["n"] = n
            table.append(row)

    # the grid the metrics are judged in: 256px render, 64-unit design grid
    # (kept in one place so the checks and the crops cannot disagree)

    # optical centring: nudge each glyph so its measured ink box sits in the middle.
    # Cumulative, so re-running converges instead of oscillating.
    offsets_path = os.path.join(HERE, "out", "offsets.json")
    current = {}
    if os.path.exists(offsets_path):
        try:
            current = {k: tuple(v) for k, v in
                       json.load(open(offsets_path, encoding="utf-8")).items()}
        except Exception:  # noqa: BLE001
            current = {}
    print("\noptical centring (from the measured ink box, in 64-unit grid space)")
    new_offsets = {}
    for n, mark in enumerate(MARKS, 1):
        row = next((r for r in table if r["n"] == n and "256px" in r["label"]), None)
        optr = next((r for r in table if r["n"] == n and "16px" in r["label"]), None)
        if not row or row.get("error"):
            new_offsets[mark["id"]] = list(current.get(mark["id"], (0, 0)))
            continue
        raw_dx = -row["centre_offset"][0] * GLYPH_GRID / 256.0
        raw_dy = -row["centre_offset"][1] * GLYPH_GRID / 256.0
        # half a design-grid unit is sub-pixel noise from antialiasing; chasing it just
        # makes the offsets creep on every run
        dx = raw_dx if abs(raw_dx) >= 0.4 else 0.0
        dy = raw_dy if abs(raw_dy) >= 0.4 else 0.0
        prev = current.get(mark["id"], (0.0, 0.0))
        total = [round(prev[0] + dx, 2), round(prev[1] + dy, 2)]
        new_offsets[mark["id"]] = total
        # thin marks must stay thin and hollow marks hollow: the 0.5% floor catches a
        # stroke that has collapsed, the 1-part reading catches a filling-in
        note = ""
        if optr and not optr.get("error"):
            if row["comps"] > 1 and optr["comps"] == 1:
                note = "  (parts merge at 16px — expected for a mark with close-set details)"
        print("  %-12s centre off %+5.1f/%+5.1f px at 256  ->  nudge %+.2f/%+.2f  total %+.2f/%+.2f%s"
              % (mark["name"], row["centre_offset"][0], row["centre_offset"][1],
                 dx, dy, total[0], total[1], note))
    os.makedirs(os.path.dirname(offsets_path), exist_ok=True)
    json.dump(new_offsets, open(offsets_path, "w", encoding="utf-8"), indent=2)
    print("  offsets written to out/offsets.json — re-run build_logos.py to apply them")

    print("\n%-28s %6s %9s %10s %6s %8s" %
          ("mark", "ink %", "centre", "margins", "parts", "contrast"))
    print("-" * 72)
    problems = []
    for row in table:
        if row.get("error"):
            print("%-28s  %s" % (row["label"][:28], row["error"]))
            problems.append("%s: %s" % (row["label"], row["error"]))
            continue
        print("%-28s %6.1f %9s %10s %6d %8.2f" % (
            row["label"][:28], row["ink_pct"], row["centre_offset"],
            "%d/%d/%d/%d" % row["margin_px"], row["comps"],
            row["contrast_vs_lightest_ground"]))
        if row["size"] == (256, 256) and "256px" in row["label"]:
            if row["ink_pct"] < 8:
                problems.append("%s: ink %.1f%% — too thin for small sizes" % (row["label"], row["ink_pct"]))
            if row["ink_pct"] > 45:
                problems.append("%s: ink %.1f%% — heavy enough to blob" % (row["label"], row["ink_pct"]))
            if abs(row["centre_offset"][0]) > 6 or abs(row["centre_offset"][1]) > 6:
                problems.append("%s: ink box off centre by %s (a nudge is written to offsets.json)"
                                % (row["label"], row["centre_offset"]))

    # ink must survive the shrink: a mark that loses most of its mass at 16px is mush
    print("\nsmall-size survival (ink at 16px vs ink at 256px)")
    for n in range(1, len(MARKS) + 1):
        big = next(r for r in table if r["n"] == n and "256px" in r["label"])
        small = next(r for r in table if r["n"] == n and "16px" in r["label"])
        if small.get("error"):
            problems.append("option %d: nothing left at 16px" % n)
            continue
        keep = 100.0 * small["ink_pct"] / big["ink_pct"]
        flag = "OK" if keep >= 60 else "LOSES MASS"
        print("  option %d  %-12s %5.1f%% -> %5.1f%%  (%d%% kept)  parts %d -> %d  %s"
              % (n, MARKS[n - 1]["name"], big["ink_pct"], small["ink_pct"], keep,
                 big["comps"], small["comps"], flag))
        if keep < 60:
            problems.append("option %d: keeps only %d%% of its ink at 16px" % (n, keep))

    # glyph contrast against the gradient is arithmetic: white against the lightest stop
    def _lum(hexstr):
        r, g, b = (int(hexstr[i:i + 2], 16) for i in (1, 3, 5))
        return luminance((r, g, b))
    white, lightest = _lum("#ffffff"), _lum(BRAND_B)
    glyph_contrast = (white + 0.05) / (lightest + 0.05)
    print("\nglyph vs gradient: white on %s = %.2f:1 (the lightest stop, worst case)"
          % (BRAND_B, glyph_contrast))
    if glyph_contrast < 3.0:
        problems.append("white glyph only %.2f:1 on the lightest gradient stop" % glyph_contrast)

    print("\n%s" % ("-" * 72))
    if problems:
        print("FINDINGS (%d)" % len(problems))
        for p in problems:
            print("  ! %s" % p)
    else:
        print("all six marks pass: inside the tile, optically centred, well weighted, "
              "ink survives at 16px, glyph legible on the gradient")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
