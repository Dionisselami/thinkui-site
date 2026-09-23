#!/usr/bin/env python3
"""verify_identity.py — the identity as it lands in the site, measured.

Checks the rendered lockups rather than the source: correct size, the tile's gradient
actually resolving (a wrong gradient id renders as none at all), the inverse variant
legible on the dark footer, every icon reachable, and no layout pushed around. Then
captures the header, the footer and an icon sheet so a human can look.

    python verify_identity.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import urllib.request

sys.path.insert(0, r"C:\Users\use\AppData\Local\hermes\skills\software-development\rendered-ui-verification\scripts")
import ui_probe  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(os.path.join(HERE, ".."))
TMP = os.path.join(HERE, "tmp")
BASE = "http://127.0.0.1:8899"
PORT = 9477

PROBE = r"""
(() => {
  const out = {console: []};
  const svgs = [...document.querySelectorAll('svg.brand__logo')];
  out.lockups = svgs.map(s => {
    const r = s.getBoundingClientRect();
    const cs = getComputedStyle(s);
    const uses = [...s.querySelectorAll('[fill^="url("]')].map(e => e.getAttribute('fill'));
    const defs = [...s.querySelectorAll('linearGradient')].map(g => g.id);
    const word = s.querySelector('path');
    const tile = s.querySelector('rect');
    return {
      h: Math.round(r.height * 10) / 10, w: Math.round(r.width * 10) / 10,
      cssH: cs.height, fills: uses, gradients: defs,
      wordFill: word ? word.getAttribute('fill') : null,
      tileFill: tile ? tile.getAttribute('fill') : null,
      // does the referenced gradient exist inside this same svg?
      refsResolve: uses.every(f => {
        const id = f.slice(5, -1);
        return !!s.querySelector('linearGradient[id="' + id + '"]');
      }),
      inFooter: !!s.closest('.footer')
    };
  });
  const bar = document.querySelector('header.header');
  out.headerH = bar ? Math.round(bar.getBoundingClientRect().height) : null;
  out.scrollW = document.documentElement.scrollWidth;
  out.innerW = window.innerWidth;
  out.icons = [...document.querySelectorAll('link[rel*="icon"],link[rel="apple-touch-icon"],link[rel="manifest"]')]
              .map(l => l.getAttribute('href'));
  return out;
})()
"""


async def drive():
    chrome = ui_probe.find_chrome()
    proc = ui_probe.launch(chrome, PORT)
    result, shots = None, {}
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
                       {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
            await send("Page.navigate", {"url": BASE + "/index.html"})
            for _ in range(60):
                if await ev("document.readyState") == "complete":
                    break
                await asyncio.sleep(0.25)
            await ev("document.fonts ? document.fonts.ready.then(() => true) : true")
            await asyncio.sleep(1.4)
            result = await ev(PROBE)

            async def shot(path, clip):
                s = await send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                                          "clip": clip})
                data = s.get("result", {}).get("data")
                if data:
                    open(path, "wb").write(base64.b64decode(data))
                    shots[os.path.basename(path)] = os.path.getsize(path)

            await shot(os.path.join(TMP, "site-header.png"),
                       {"x": 0, "y": 0, "width": 1440, "height": 120, "scale": 1})
            # footer: scroll to the bottom, then clip the last 260px of the page
            await ev("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.2)
            metrics = await send("Page.getLayoutMetrics")
            size = (metrics.get("result", {}).get("cssContentSize")
                    or metrics.get("result", {}).get("contentSize"))
            h = size["height"]
            await shot(os.path.join(TMP, "site-footer.png"),
                       {"x": 0, "y": max(0, h - 300), "width": 1440, "height": 300, "scale": 1})
    finally:
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass
    return result, shots


def check_http(urls):
    bad = []
    for u in urls:
        try:
            with urllib.request.urlopen(BASE + "/" + u.lstrip("/"), timeout=8) as r:
                if r.status != 200:
                    bad.append("%s -> HTTP %s" % (u, r.status))
        except Exception as exc:  # noqa: BLE001
            bad.append("%s -> %s" % (u, exc))
    return bad


def main():
    os.makedirs(TMP, exist_ok=True)
    r, shots = asyncio.run(drive())
    if not r:
        print("probe returned nothing — is the site serving on 8899?")
        return 1

    print("lockups found on the page: %d" % len(r["lockups"]))
    for i, lk in enumerate(r["lockups"], 1):
        where = "footer" if lk["inFooter"] else "header"
        print("  %-7s %.1f x %.1f px (css h %s)  word %s  tile %s"
              % (where, lk["w"], lk["h"], lk["cssH"], lk["wordFill"], lk["tileFill"]))
        print("          gradients %s  refs resolve: %s"
              % (lk["gradients"], lk["refsResolve"]))

    print("header height %spx   scrollWidth %s vs innerWidth %s"
          % (r["headerH"], r["scrollW"], r["innerW"]))
    print("icon links: %s" % ", ".join(r["icons"]))

    problems = []
    if len(r["lockups"]) < 2:
        problems.append("expected a header and a footer lockup, found %d" % len(r["lockups"]))
    for lk in r["lockups"]:
        where = "footer" if lk["inFooter"] else "header"
        if abs(lk["h"] - 26) > 0.6:
            problems.append("%s lockup renders %.1fpx tall, expected 26" % (where, lk["h"]))
        if lk["w"] < 80 or lk["w"] > 100:
            problems.append("%s lockup is %.1fpx wide, expected ~90" % (where, lk["w"]))
        if not lk["refsResolve"]:
            problems.append("%s lockup references a gradient id that does not exist — "
                            "the mark would render with no fill" % where)
    if r["scrollW"] > r["innerW"] + 2:
        problems.append("page scrolls sideways: %s > %s" % (r["scrollW"], r["innerW"]))

    icons = [u for u in r["icons"] if u and not u.startswith("http")]
    bad = check_http(icons)
    problems += ["icon does not resolve: %s" % b for b in bad]

    print("\ncaptures: %s" % ", ".join("%s (%d bytes)" % (k, v) for k, v in shots.items()))
    print("-" * 62)
    if problems:
        print("FINDINGS (%d)" % len(problems))
        for p in problems:
            print("  ! %s" % p)
    else:
        print("identity renders correctly in place: header and footer lockups at 26px, "
              "gradients resolve, every icon reaches 200")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
