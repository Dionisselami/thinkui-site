#!/usr/bin/env python3
"""preview_identity.py — one sheet showing the finished identity, for a human to judge.

The agent cannot see, so this is the looking half: the lockup at three sizes on paper
and on ink, the mark alone, the icon set at its real sizes, and the 16px favicon
magnified with nearest-neighbour so real pixels are on show rather than interpolation.

    python preview_identity.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys

sys.path.insert(0, r"C:\Users\use\AppData\Local\hermes\skills\software-development\rendered-ui-verification\scripts")
import ui_probe  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(os.path.join(HERE, ".."))
TMP = os.path.join(HERE, "tmp")
PORT = 9488

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #eef1f7; }
  body { font: 400 13px/1.5 Inter, system-ui, sans-serif; color: #05070c; width: 1180px; }
  .band { padding: 30px 40px; }
  .band--ink { background: #05070c; color: #f7f9fc; }
  h3 { font: 600 11px/1 Inter; letter-spacing: .14em; text-transform: uppercase;
       color: #6b7280; margin: 0 0 20px; }
  .band--ink h3 { color: #7b8595; }
  .row { display: flex; align-items: flex-end; gap: 44px; flex-wrap: wrap; }
  .cell { text-align: left; }
  .cap { font-size: 11px; color: #6b7280; margin-top: 12px; }
  .band--ink .cap { color: #7b8595; }
  .icons { display: flex; align-items: flex-end; gap: 26px; }
  .px { image-rendering: pixelated; display: block; }
  .frame { background: #fff; border: 1px solid #d8dde8; border-radius: 10px; padding: 16px 20px; }
</style></head><body>
<div class="band">
  <h3>The lockup — on paper</h3>
  <div class="row">
    <div class="cell"><img src="../assets/img/logo.svg" style="height:26px"><div class="cap">26px (header)</div></div>
    <div class="cell"><img src="../assets/img/logo.svg" style="height:40px"><div class="cap">40px</div></div>
    <div class="cell"><img src="../assets/img/logo.svg" style="height:64px"><div class="cap">64px</div></div>
    <div class="cell"><img src="../assets/img/logo-bare.svg" style="height:64px"><div class="cap">no tile, for docs</div></div>
  </div>
</div>
<div class="band band--ink">
  <h3>The lockup — on ink</h3>
  <div class="row">
    <div class="cell"><img src="../assets/img/logo-inverse.svg" style="height:26px"><div class="cap">26px (footer)</div></div>
    <div class="cell"><img src="../assets/img/logo-inverse.svg" style="height:64px"><div class="cap">64px</div></div>
  </div>
</div>
<div class="band">
  <h3>The mark and the icon set — real pixel sizes</h3>
  <div class="row">
    <div class="cell"><img src="../assets/img/mark.svg" style="height:56px"><div class="cap">mark, one colour</div></div>
    <div class="cell"><img src="../assets/img/mark-knockout.svg" style="height:56px"><div class="cap">knockout tile</div></div>
    <div class="cell icons">
      <div><img class="px" src="../assets/img/favicon-16.png" style="width:16px;height:16px"><div class="cap">16</div></div>
      <div><img class="px" src="../assets/img/favicon-32.png" style="width:32px;height:32px"><div class="cap">32</div></div>
      <div><img src="../assets/img/favicon-64.png" style="width:64px;height:64px"><div class="cap">64</div></div>
      <div><img src="../assets/img/favicon-128.png" style="width:128px;height:128px"><div class="cap">128</div></div>
      <div><img src="../assets/img/apple-touch-icon.png" style="width:90px;height:90px"><div class="cap">apple 180</div></div>
    </div>
  </div>
</div>
<div class="band">
  <h3>16px, magnified with real pixels — what a tab actually shows</h3>
  <div class="row">
    <div class="cell"><img class="px" src="../assets/img/favicon-16.png" style="width:128px;height:128px"></div>
    <div class="cell"><img class="px" src="../assets/img/favicon-32.png" style="width:128px;height:128px"></div>
    <div class="cell"><img src="../assets/img/apple-touch-icon.png" style="width:128px;height:128px"><div class="cap">apple touch, full-bleed (unmasked)</div></div>
  </div>
</div>
</body></html>
"""


async def shoot():
    # written beside the site, not into tmp/: the sheet links ../assets/img/*, and a
    # relative path that resolves one level too shallow makes every image a gap
    path = os.path.join(HERE, "identity-preview.html")
    open(path, "w", encoding="utf-8").write(HTML)
    chrome = ui_probe.find_chrome()
    proc = ui_probe.launch(chrome, PORT)
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
            await send("Emulation.setDeviceMetricsOverride",
                       {"width": 1180, "height": 900, "deviceScaleFactor": 2, "mobile": False})
            await send("Page.navigate", {"url": "file:///" + path.replace("\\", "/").lstrip("/")})
            for _ in range(60):
                if await ev("document.readyState") == "complete":
                    break
                await asyncio.sleep(0.25)
            await ev("document.fonts ? document.fonts.ready.then(() => true) : true")
            await asyncio.sleep(1.6)
            # nothing may render at zero size: a broken <img> shows as a gap and reads
            # as a design choice rather than a bug
            broken = await ev("[...document.images].filter(i => !i.complete || i.naturalWidth === 0)"
                              ".map(i => i.getAttribute('src'))")
            metrics = await send("Page.getLayoutMetrics")
            size = (metrics.get("result", {}).get("cssContentSize")
                    or metrics.get("result", {}).get("contentSize"))
            shot = await send("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": True,
                "clip": {"x": 0, "y": 0, "width": 1180, "height": size["height"], "scale": 2}})
            data = shot.get("result", {}).get("data")
            out = os.path.join(HERE, "identity-preview.png")
            open(out, "wb").write(base64.b64decode(data))
            print("broken images: %s" % (broken or "none"))
            print("wrote %s (%.0f KB)" % (out, os.path.getsize(out) / 1024))
            return 1 if broken else 0
    finally:
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(shoot()))
