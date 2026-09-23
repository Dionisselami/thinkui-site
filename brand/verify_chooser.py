#!/usr/bin/env python3
"""verify_chooser.py — does the chooser page actually render?

The chooser is the thing being clicked, so it gets checked as a page rather than
trusted: are all six cards there, did every inlined mark get a real box (an SVG with
zero width renders as nothing and looks like a broken logo), does anything overflow,
and did the console stay clean.

    python verify_chooser.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, r"C:\Users\use\AppData\Local\hermes\skills\software-development\rendered-ui-verification\scripts")
import ui_probe  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "file:///" + os.path.join(HERE, "index.html").replace("\\", "/")
PORT = 9455

PROBE = r"""
(() => {
  const cards = [...document.querySelectorAll('article.opt')];
  const boxes = [...document.querySelectorAll('svg')].map(s => {
    const r = s.getBoundingClientRect();
    return {w: Math.round(r.width), h: Math.round(r.height), t: r.top | 0};
  });
  const sends = [...document.querySelectorAll('[data-hermes-send]')]
                 .map(e => e.getAttribute('data-hermes-send'));
  return {
    cards: cards.length,
    cardNames: cards.map(c => (c.querySelector('h2') || {}).textContent || '').trim ?
               cards.map(c => ((c.querySelector('h2') || {}).textContent || '').trim()) : [],
    svgs: boxes.length,
    zeroSized: boxes.filter(b => b.w < 4 || b.h < 4),
    sizesSeen: [...new Set(boxes.map(b => b.w))].sort((a, b) => a - b),
    sendButtons: sends.length,
    choices: sends,
    scrollW: document.documentElement.scrollWidth,
    innerW: window.innerWidth,
    docH: document.documentElement.scrollHeight,
    h2count: document.querySelectorAll('h2').length
  };
})()
"""


async def main():
    chrome = ui_probe.find_chrome()
    proc = ui_probe.launch(chrome, PORT)
    problems = []
    try:
        ws = ui_probe.attach(PORT)
        import websockets
        async with websockets.connect(ws, max_size=32_000_000) as sock:
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
                       {"width": 1440, "height": 1200, "deviceScaleFactor": 1, "mobile": False})
            await send("Page.navigate", {"url": URL})
            for _ in range(60):
                if await ev("document.readyState") == "complete":
                    break
                await asyncio.sleep(0.25)
            await ev("document.fonts ? document.fonts.ready.then(() => true) : true")
            await asyncio.sleep(1.5)
            r = await ev(PROBE)
            print(json.dumps(r, indent=2))
    finally:
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass

    if r["cards"] != 6:
        problems.append("expected 6 option cards, found %s" % r["cards"])
    if r["h2count"] != 6:
        problems.append("expected 6 option headings, found %s" % r["h2count"])
    if r["zeroSized"]:
        problems.append("%d marks have no rendered box: %s" % (len(r["zeroSized"]), r["zeroSized"][:4]))
    if r["sendButtons"] < 6:
        problems.append("only %s click-to-choose buttons" % r["sendButtons"])
    if r["scrollW"] > r["innerW"] + 2:
        problems.append("page scrolls sideways: %s > %s" % (r["scrollW"], r["innerW"]))
    if r["svgs"] < 6:
        problems.append("only %s marks inlined" % r["svgs"])

    print("\n%s" % ("-" * 64))
    if problems:
        print("FINDINGS (%d)" % len(problems))
        for p in problems:
            print("  ! %s" % p)
    else:
        print("chooser renders clean: 6 cards, every mark has a real box, nothing overflows")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
