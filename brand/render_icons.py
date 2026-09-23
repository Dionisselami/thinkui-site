#!/usr/bin/env python3
"""render_icons.py — the raster half of the identity, rendered at true pixel size.

Every PNG is captured at its own size in the browser rather than downscaled from one
big render: scaling a large render down is exactly what makes a favicon muddy, and the
16px render is the one that decides whether the mark survives.

Also writes the multi-frame .ico, the apple touch icon (full-bleed and opaque, because
the platform applies its own mask), the web manifest, and a preview sheet.

    python render_icons.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import struct
import sys

from PIL import Image

sys.path.insert(0, r"C:\Users\use\AppData\Local\hermes\skills\software-development\rendered-ui-verification\scripts")
import ui_probe  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(os.path.join(HERE, ".."))
IDENT = json.load(open(os.path.join(SITE, "src", "identity.json"), encoding="utf-8"))
IMG = os.path.join(SITE, "assets", "img")
TMP = os.path.join(HERE, "tmp")
PORT = 9466

SIZES = [16, 32, 48, 64, 128, 256, 512]
PNG_NAMES = {16: "favicon-16.png", 32: "favicon-32.png", 48: "favicon-48.png",
             64: "favicon-64.png", 128: "favicon-128.png", 256: "favicon-256.png",
             512: "favicon-512.png"}
ICO_FRAMES = [16, 32, 48, 64]


def block_svg():
    with open(os.path.join(IMG, "mark-block.svg"), encoding="utf-8") as fh:
        return fh.read()


def fullbleed_svg(pad=2):
    """Apple masks the icon itself, so a pre-rounded tile would show a rounded tile
    floating inside theirs: square corners, and the ground has to fill the whole
    canvas. Widening the viewBox without growing the ground leaves a transparent ring
    that reads as a hairline border once the platform composites it."""
    svg = block_svg()
    svg = svg.replace('rx="15"', 'rx="0"').replace('rx="14.2"', 'rx="0"')
    # fill the enlarged canvas, keeping the bars where they are
    svg = svg.replace('<rect width="64" height="64" rx="0" fill="url(#tile-g)"/>',
                      '<rect x="-%d" y="-%d" width="%d" height="%d" fill="url(#tile-g)"/>'
                      % (pad, pad, 64 + 2 * pad, 64 + 2 * pad))
    svg = svg.replace('<rect width="64" height="64" rx="0" fill="url(#tile-s)"/>',
                      '<rect x="-%d" y="-%d" width="%d" height="%d" fill="url(#tile-s)"/>'
                      % (pad, pad, 64 + 2 * pad, 64 + 2 * pad))
    svg = svg.replace('<rect x="1" y="1" width="62" height="62" rx="0" fill="none" stroke="#ffffff" '
                      'stroke-opacity=".16" stroke-width="1.2"/>', '')
    svg = svg.replace('viewBox="0 0 64 64"', 'viewBox="-%d -%d %d %d"'
                      % (pad, pad, 64 + 2 * pad, 64 + 2 * pad))
    return svg


async def shoot_all(page_png_bytes_writer):
    """One navigation, then resize-and-capture per size: no crop arithmetic to get
    wrong, and each PNG is a real render at that size."""
    chrome = ui_probe.find_chrome()
    proc = ui_probe.launch(chrome, PORT)
    written = {}
    try:
        import websockets
        async with websockets.connect(ui_probe.attach(PORT), max_size=64_000_000) as sock:
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
                r = await send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                                    "awaitPromise": True})
                return r.get("result", {}).get("result", {}).get("value")

            await send("Page.enable")
            await send("Runtime.enable")
            # without this the capture is composited on white and a favicon with
            # rounded corners ships as a white square with a tile inside it
            await send("Emulation.setDefaultBackgroundColorOverride",
                       {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})

            async def render(svg, size, path, extra_box=None):
                w = extra_box or size
                await send("Emulation.setDeviceMetricsOverride",
                           {"width": w, "height": w, "deviceScaleFactor": 1, "mobile": False})
                await ev("document.body.innerHTML = ''")
                await ev("""(() => {
                    document.documentElement.style.cssText='margin:0;padding:0;background:transparent';
                    document.body.style.cssText='margin:0;padding:0;overflow:hidden';
                    document.body.innerHTML = %s;
                    const s = document.querySelector('svg');
                    s.setAttribute('width', %d); s.setAttribute('height', %d);
                    s.style.display = 'block';
                })()""" % (json.dumps(svg), size, size))
                await asyncio.sleep(0.35)
                shot = await send("Page.captureScreenshot", {
                    "format": "png", "captureBeyondViewport": False,
                    "clip": {"x": 0, "y": 0, "width": w, "height": w, "scale": 1}})
                data = shot.get("result", {}).get("data")
                if not data:
                    return None
                open(path, "wb").write(base64.b64decode(data))
                written[path] = size
                return path

            await send("Page.navigate", {"url": "about:blank"})
            for size in SIZES:
                await render(block_svg(), size, os.path.join(IMG, PNG_NAMES[size]))
            await render(fullbleed_svg(), 180, os.path.join(IMG, "apple-touch-icon.png"))
            await render(fullbleed_svg(), 512, os.path.join(TMP, "fullbleed-512.png"))
            # something to look at: the same source at each size, magnified with real
            # pixels (nearest-neighbour), which is how you judge a 16px favicon
            await render(block_svg(), 64, os.path.join(TMP, "preview-64.png"))
    finally:
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass
    return written


def write_ico(path, frames):
    """A real multi-size .ico with each frame rendered at its own size (Windows and
    older browsers then pick the frame that fits instead of rescaling one bitmap)."""
    blobs = []
    for size in frames:
        with open(os.path.join(IMG, PNG_NAMES[size]), "rb") as fh:
            blobs.append((size, fh.read()))
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries, data = b"", b""
    for size, blob in blobs:
        entries += struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0,
                               0, 0, 1, 32, len(blob), offset)
        data += blob
        offset += len(blob)
    with open(path, "wb") as fh:
        fh.write(header + entries + data)
    return blobs


def audit():
    """Measure what was produced: is the tile covering its canvas, do the bars still
    register at 16px, is the apple icon genuinely full-bleed."""
    problems, report = [], []
    for size in SIZES:
        p = os.path.join(IMG, PNG_NAMES[size])
        im = Image.open(p).convert("RGBA")
        w, h = im.size
        if (w, h) != (size, size):
            problems.append("%s is %dx%d, not %dx%d" % (os.path.basename(p), w, h, size, size))
        px = im.load()
        opaque = white = 0
        # Ink is classified against the two colours that are actually in the icon (the white
        # bars and the tile under them), not by a near-white threshold: the old test only
        # worked while the tile was dark, and read a bright tile's antialiased bar edges as
        # background. Nearest-colour is palette-independent, so this check keeps telling the
        # truth the next time the accent changes.
        def hx(s):
            return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
        with open(os.path.join(SITE, "src", "identity.json"), encoding="utf-8") as fh:
            ident = json.load(fh)
        ta, tb, glyph = hx(ident["tile_a"]), hx(ident["tile_b"]), (255, 255, 255)
        def dist2(p, q):
            return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a > 200:
                    opaque += 1
                    # the tile's gradient runs corner to corner, so lerp it the same way
                    t = (x + y) / float(w + h - 2 or 1)
                    tile = tuple(ta[i] + (tb[i] - ta[i]) * t for i in range(3))
                    if dist2((r, g, b), glyph) < dist2((r, g, b), tile):
                        white += 1
        corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
        opaque_pct = 100.0 * opaque / (w * h)
        white_pct = 100.0 * white / (w * h)
        report.append((os.path.basename(p), size, round(opaque_pct, 1), round(white_pct, 1)))
        if size == 16:
            if white_pct < 7:
                problems.append("16px: bars are only %.1f%% of the icon — washing out" % white_pct)
            if white_pct > 20:
                problems.append("16px: bars read %.1f%% — the tile is losing its ground" % white_pct)
        if opaque_pct < 90:
            problems.append("%s: only %.1f%% opaque — the tile is not covering its canvas"
                            % (os.path.basename(p), opaque_pct))
        if any(c[3] != 0 for c in corners):
            problems.append("%s: corners are not transparent (a white square on a dark "
                            "tab bar)" % os.path.basename(p))

    at = Image.open(os.path.join(IMG, "apple-touch-icon.png")).convert("RGBA")
    apx = at.load()
    transparent = sum(1 for y in range(at.size[1]) for x in range(at.size[0])
                      if apx[x, y][3] < 250)
    corners = [apx[0, 0], apx[at.size[0] - 1, 0], apx[0, at.size[1] - 1],
               apx[at.size[0] - 1, at.size[1] - 1]]
    report.append(("apple-touch-icon.png", at.size[0], 100 - round(100 * transparent / (180 * 180), 2), "—"))
    if transparent:
        problems.append("apple touch icon has %d non-opaque pixels — it must be full-bleed"
                        % transparent)
    if not all(c[3] == 255 for c in corners):
        problems.append("apple touch icon corners are transparent; the mask would show gaps")

    ico_path = os.path.join(IMG, "favicon.ico")
    with Image.open(ico_path) as ico:
        frames = sorted(ico.ico.sizes()) if hasattr(ico, "ico") else []
    report.append(("favicon.ico", os.path.getsize(ico_path), "frames %s" % (frames,), "—"))
    if len(frames) < 3:
        problems.append("favicon.ico carries only %d frames" % len(frames))

    print("%-22s %7s %10s %10s" % ("file", "size", "opaque %", "white %"))
    print("-" * 54)
    for row in report:
        print("%-22s %7s %10s %10s" % row)
    print()
    return problems


def main():
    os.makedirs(TMP, exist_ok=True)
    written = asyncio.run(shoot_all(None))
    print("rendered at true size:")
    for p, size in sorted(written.items(), key=lambda kv: kv[1]):
        print("  %-46s %4dpx  %6d bytes" % (os.path.relpath(p, SITE), size, os.path.getsize(p)))

    write_ico(os.path.join(IMG, "favicon.ico"), ICO_FRAMES)
    print("  %-46s   %s  %6d bytes" % ("assets/img/favicon.ico", ICO_FRAMES,
                                       os.path.getsize(os.path.join(IMG, "favicon.ico"))))

    manifest = {
        "name": "ThinkUI",
        "short_name": "ThinkUI",
        "description": "Interface references for coding agents, over MCP.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": IDENT["ink"],
        "icons": [
            {"src": "assets/img/favicon.svg", "sizes": "any", "type": "image/svg+xml",
             "purpose": "any"},
            {"src": "assets/img/favicon-128.png", "sizes": "128x128", "type": "image/png"},
            {"src": "assets/img/favicon-256.png", "sizes": "256x256", "type": "image/png"},
            {"src": "assets/img/favicon-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "any"},
            {"src": "assets/img/apple-touch-icon.png", "sizes": "180x180", "type": "image/png",
             "purpose": "maskable"},
        ],
    }
    with open(os.path.join(SITE, "site.webmanifest"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    print("  %-46s   %d icons" % ("site.webmanifest", len(manifest["icons"])))

    problems = audit()
    print("%s" % ("-" * 54))
    if problems:
        print("FINDINGS (%d)" % len(problems))
        for p in problems:
            print("  ! %s" % p)
    else:
        print("all sizes clean: tile covers its canvas, bars register at 16px, "
              "apple icon full-bleed, .ico multi-frame")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
