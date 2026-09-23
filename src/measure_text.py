#!/usr/bin/env python3
"""measure_text.py — find out which element the contrast probe is complaining about.

The probe reports a selector or its own tag, not the element. This walks every
text node's element, composites the real background by walking up the ancestors
(the way the eye does), and prints the worst offenders with enough detail to fix
them — tag, class, text, colours, and whether a background-image is involved.

    python measure_text.py [url] [--width 1440]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

sys.path.insert(0, r"C:\Users\use\AppData\Local\hermes\skills\software-development\rendered-ui-verification\scripts")
import ui_probe  # noqa: E402

JS = r"""
(() => {
  function parse(c) {
    const m = (c || '').match(/rgba?\(([^)]+)\)/);
    if (!m) { return null; }
    const p = m[1].split(',').map(x => parseFloat(x));
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }
  function over(fg, bg) {                       // composite fg onto bg
    const a = fg.a;
    return { r: fg.r * a + bg.r * (1 - a), g: fg.g * a + bg.g * (1 - a),
             b: fg.b * a + bg.b * (1 - a), a: 1 };
  }
  function lum(c) {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function ratio(a, b) {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  function stack(el) {                          // what is actually behind this text
    const layers = [];
    let n = el;
    while (n && n !== document.documentElement) {
      const cs = getComputedStyle(n);
      const bg = parse(cs.backgroundColor);
      const hasImg = cs.backgroundImage && cs.backgroundImage !== 'none';
      if ((bg && bg.a > 0) || hasImg) {
        layers.push({ tag: n.tagName.toLowerCase(), cls: (n.className || '').toString().slice(0, 40),
                      bg: bg, img: hasImg });
      }
      n = n.parentElement;
    }
    return layers;
  }

  const out = [];
  const nodes = document.querySelectorAll('h1,h2,h3,h4,p,li,a,label,summary,small,td,th');
  for (const el of nodes) {
    const txt = (el.textContent || '').trim();
    if (!txt) { continue; }
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) { continue; }
    const cs = getComputedStyle(el);
    const fg = parse(cs.color) || { r: 0, g: 0, b: 0, a: 1 };
    if (fg.a === 0) { out.push({ why: 'transparent text', el: el.tagName + '.' + el.className, txt: txt.slice(0, 30) }); continue; }
    const layers = stack(el);
    // composite from the page background up to the text
    let base = parse(getComputedStyle(document.body).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 };
    for (let i = layers.length - 1; i >= 0; i--) {
      if (layers[i].bg && layers[i].bg.a > 0) { base = over(layers[i].bg, base); }
    }
    const cr = ratio(fg, base);
    if (cr < 4.5) {
      out.push({
        ratio: Math.round(cr * 100) / 100,
        el: el.tagName.toLowerCase() + (el.className ? '.' + el.className.toString().split(' ')[0] : ''),
        txt: txt.slice(0, 34),
        colour: cs.color, base: 'rgb(' + Math.round(base.r) + ',' + Math.round(base.g) + ',' + Math.round(base.b) + ')',
        px: parseFloat(cs.fontSize),
        weight: cs.fontWeight,
        layers: layers.map(l => l.tag + (l.cls ? '.' + l.cls.split(' ')[0] : '') + (l.img ? '(image)' : ''))
      });
    }
  }
  out.sort((a, b) => (a.ratio || 0) - (b.ratio || 0));
  return JSON.stringify({ checked: nodes.length, low: out.slice(0, 10) });
})()
"""


async def run(ws, url, width):
    import websockets
    async with websockets.connect(ws, max_size=64_000_000) as sock:
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
                   {"width": width, "height": 950, "deviceScaleFactor": 1, "mobile": width <= 620})
        await send("Page.navigate", {"url": url})
        for _ in range(80):
            if await ev("document.readyState") == "complete":
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(1.4)
        await ev("document.querySelectorAll('[data-rise]').forEach(e => e.classList.add('in'))")
        await asyncio.sleep(0.4)
        return json.loads(await ev(JS) or "{}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--port", type=int, default=9433)
    a = ap.parse_args()

    proc = ui_probe.launch(ui_probe.find_chrome(), a.port)
    try:
        res = asyncio.run(run(ui_probe.attach(a.port), a.url, a.width))
    finally:
        proc.kill()

    print("\n%s  @%dpx" % (a.url, a.width))
    print("  elements with text: %s   below 4.5:1: %s"
          % (res.get("checked"), len(res.get("low", []))))
    for row in res.get("low", []):
        if row.get("why"):
            print("    ! %s  %s  %r" % (row["el"], row["why"], row.get("txt")))
            continue
        print("    %.2f:1  %-22s %-34r colour %s on %s  (%spx w%s)"
              % (row["ratio"], row["el"], row["txt"], row["colour"], row["base"], row["px"], row["weight"]))
        print("           behind: %s" % " < ".join(row["layers"][:4]),
              )


if __name__ == "__main__":
    main()
