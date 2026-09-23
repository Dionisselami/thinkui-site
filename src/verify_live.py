#!/usr/bin/env python3
"""verify_live.py — drive a real Chrome over CDP and check the site behaves.

ui_probe.py already measures geometry and contrast. This checks the things a
geometry sweep cannot see: whether the animations are actually animating, whether
the reveal system ends with content visible, whether the header switches state,
whether the webfonts loaded, and whether any JavaScript error reached the console.

    python verify_live.py [base_url] [--port 9422]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, r"C:\Users\use\AppData\Local\hermes\skills\software-development\rendered-ui-verification\scripts")
import ui_probe  # noqa: E402  (reuses its Chrome launcher and CDP attach)

PAGES = ["index.html", "pricing.html", "docs.html", "login.html",
         "signup.html", "404.html", "terms.html", "privacy.html"]

# measured on the page: what is actually happening, not what the CSS says should
JS_REPORT = r"""
(() => {
  const cs = (el, prop) => el ? getComputedStyle(el)[prop] : null;
  const aur = document.querySelector('.aurora i');
  const veil = document.querySelector('.veil');
  const grain = document.querySelector('.grain');
  const rise = [...document.querySelectorAll('[data-rise]')];
  return JSON.stringify({
    title: document.title,
    h1: document.querySelectorAll('h1').length,
    lang: document.documentElement.getAttribute('lang'),
    body_bg: cs(document.body, 'backgroundColor'),
    sections: document.querySelectorAll('main section').length,
    rise_total: rise.length,
    rise_in: rise.filter(e => e.classList.contains('in')).length,
    rise_faded: rise.filter(e => parseFloat(cs(e, 'opacity')) === 0).length,
    aurora_animation: cs(aur, 'animationName'),
    aurora_duration: cs(aur, 'animationDuration'),
    veil_animation: cs(veil, 'animationName'),
    beam_animation: cs(document.querySelector('.beam'), 'animationName'),
    grain_texture: grain ? (cs(grain, 'backgroundImage') || '').slice(0, 42) : null,
    ticker_children: (document.querySelector('.ticker__row') || {children: []}).children.length,
    media: [...document.querySelectorAll('img')].map(i => ({src: i.getAttribute('src'), w: i.naturalWidth})),
    has_display: !!document.querySelector('.display'),
    has_mono: !!document.querySelector('.mono, .code pre, code'),
    fonts: {
      status: document.fonts.status,
      inter: document.fonts.check('16px Inter'),
      serif: document.fonts.check('16px "Instrument Serif"'),
      mono: document.fonts.check('16px "JetBrains Mono"')
    }
  });
})()
"""

JS_AFTER_SCROLL = r"""
(() => {
  const h = document.querySelector('header.header');
  if (!h) { return JSON.stringify({ header: null }); }
  return JSON.stringify({
    stuck_class: h.classList.contains('is-stuck'),
    bg: getComputedStyle(h).backgroundColor,
    colour: getComputedStyle(h).color,
    position: getComputedStyle(h).position,
    top_px: Math.round(h.getBoundingClientRect().top),
    nav_visible: getComputedStyle(document.querySelector('.nav')).display
  });
})()
"""

JS_COPY = r"""
(() => {
  const b = document.querySelector('[data-copy]');
  if (!b) { return JSON.stringify({ copy: 'no button on this page' }); }
  b.click();
  const label = b.querySelector('span');
  return new Promise(resolve => setTimeout(() => resolve(JSON.stringify({
    copy: 'clicked',
    label_after: label ? label.textContent : null,
    done_class: b.classList.contains('is-done')
  })), 350));
})()
"""

JS_NO_SCRIPT = r"""
(() => {
  const rise = [...document.querySelectorAll('[data-rise]')];
  const faded = rise.filter(e => parseFloat(getComputedStyle(e).opacity) === 0).length;
  const h1 = document.querySelector('h1');
  return JSON.stringify({
    html_class: document.documentElement.className,
    rise_total: rise.length,
    rise_faded: faded,
    h1_opacity: h1 ? getComputedStyle(h1).opacity : null,
    h1_colour: h1 ? getComputedStyle(h1).color : null
  });
})()
"""


async def run(ws_url, base, want_no_script=True):
    import websockets

    results, errors = [], []
    async with websockets.connect(ws_url, max_size=64_000_000) as ws:
        counter = 0

        async def send(method, params=None, collect=True):
            nonlocal counter
            counter += 1
            await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == counter:
                    return msg
                if collect and msg.get("method") in ("Runtime.consoleAPICalled", "Log.entryAdded",
                                                     "Runtime.exceptionThrown"):
                    errors.append(msg)

        async def ev(expr):
            res = await send("Runtime.evaluate",
                             {"expression": expr, "returnByValue": True, "awaitPromise": True})
            val = res.get("result", {}).get("result", {}).get("value")
            r = res.get("result", {})
            if r.get("exceptionDetails"):
                errors.append({"method": "evaluate-exception",
                               "text": str(r["exceptionDetails"])[:400]})
            return val

        async def load(url, wait=1.5):
            await send("Page.navigate", {"url": url})
            for _ in range(90):
                if await ev("document.readyState") == "complete":
                    break
                await asyncio.sleep(0.25)
            await asyncio.sleep(wait)

        await send("Page.enable")
        await send("Runtime.enable")
        await send("Log.enable")
        await send("Emulation.setDeviceMetricsOverride",
                   {"width": 1440, "height": 950, "deviceScaleFactor": 1, "mobile": False})

        for page in PAGES:
            await ev("window.scrollTo(0, 0)")
            await load("%s/%s" % (base.rstrip("/"), page))
            row = {"page": page}
            for key, expr in (("report", JS_REPORT), ("copy", JS_COPY)):
                raw = await ev(expr)
                try:
                    row.update(json.loads(raw))
                except Exception:  # noqa: BLE001
                    row[key] = raw
            await ev("window.scrollTo(0, 700)")
            await asyncio.sleep(0.5)
            raw = await ev(JS_AFTER_SCROLL)
            try:
                row["scrolled"] = json.loads(raw)
            except Exception:  # noqa: BLE001
                row["scrolled"] = raw
            await ev("window.scrollTo(0, 0)")
            await asyncio.sleep(0.3)

            # the real test of the reveal system: walk the whole page, then count
            # anything that is still invisible
            await ev("""(async () => {
              const h = document.body.scrollHeight;
              for (let y = 0; y <= h; y += 500) {
                window.scrollTo(0, y);
                await new Promise(r => setTimeout(r, 130));
              }
              window.scrollTo(0, h);
              return h;
            })()""")
            await asyncio.sleep(2.0)      # 620ms transition + up to 560ms stagger
            raw = await ev("""JSON.stringify({
              total: document.querySelectorAll('[data-rise]').length,
              faded: [...document.querySelectorAll('[data-rise]')]
                       .filter(e => parseFloat(getComputedStyle(e).opacity) === 0).length,
              never: [...document.querySelectorAll('[data-rise]')]
                       .filter(e => !e.classList.contains('in')).length,
              slowest: [...document.querySelectorAll('[data-rise]')]
                       .filter(e => parseFloat(getComputedStyle(e).opacity) < 1)
                       .map(e => (e.className || '').toString().slice(0, 40)).slice(0, 4)
            })""")
            try:
                row["reveal_end"] = json.loads(raw)
            except Exception:  # noqa: BLE001
                row["reveal_end"] = {"error": str(raw)[:120]}
            await ev("window.scrollTo(0, 0)")
            await asyncio.sleep(0.2)
            results.append(row)
            print("  probed %-14s ok" % page)

        # and once with JavaScript switched off: the content must still be there
        if want_no_script:
            await send("Emulation.setScriptExecutionDisabled", {"value": True})
            await load("%s/index.html" % base.rstrip("/"), wait=1.0)
            raw = await ev(JS_NO_SCRIPT)
            results.append({"page": "index.html", "no_script": raw})

    return results, errors


def report(results, errors):
    bad = 0
    print("\n" + "=" * 66)
    for row in results:
        if "no_script" in row:
            raw = row["no_script"]
            try:
                d = json.loads(raw)
            except Exception:  # noqa: BLE001
                print("\nno-JS pass: could not evaluate (%s)" % str(raw)[:120])
                continue
            faded = d.get("rise_faded")
            ok = faded == 0 and d.get("html_class") == ""
            bad += 0 if ok else 1
            print("\n--- index.html with JavaScript disabled ---")
            print("  html class            : %r  %s" % (d.get("html_class"), "OK" if d.get("html_class") == "" else "FAIL"))
            print("  reveal elements faded : %s of %s  %s"
                  % (faded, d.get("rise_total"), "OK" if faded == 0 else "FAIL"))
            print("  h1 opacity            : %s  colour %s" % (d.get("h1_opacity"), d.get("h1_colour")))
            continue

        p = row["page"]
        issues = []
        end = row.get("reveal_end") or {}
        if end.get("never"):
            issues.append("%d reveal elements never triggered (%s)"
                          % (end["never"], end.get("slowest")))
        if row.get("h1") != 1:
            issues.append("h1 count %s" % row.get("h1"))
        if row.get("title", "").startswith("{{"):
            issues.append("unresolved token in title")
        f = row.get("fonts", {})
        needed = f.get("status") == "loaded" and f.get("inter")
        needed = needed and (f.get("serif") if row.get("has_display") else True)
        needed = needed and (f.get("mono") if row.get("has_mono") else True)
        if not needed:
            issues.append("fonts %s (display=%s mono=%s)"
                          % (f, row.get("has_display"), row.get("has_mono")))
        for img in row.get("media", []):
            if not img.get("w"):
                issues.append("image did not load: %s" % img.get("src"))
        if p == "index.html":
            for key, want in (("aurora_animation", "drift-a"), ("veil_animation", "veil-pan"),
                              ("beam_animation", "beam-sweep")):
                if row.get(key) != want:
                    issues.append("%s is %r (expected %r)" % (key, row.get(key), want))
            if row.get("ticker_children", 0) < 20:
                issues.append("ticker not duplicated (%s children)" % row.get("ticker_children"))
        sc = row.get("scrolled") or {}
        if sc.get("header") is None and "header" in sc:
            pass
        elif not sc.get("stuck_class"):
            issues.append("header did not enter its scrolled state")
        if row.get("label_after") not in (None, "Copied") and row.get("copy") == "clicked":
            issues.append("copy button label %r" % row.get("label_after"))

        bad += 1 if issues else 0
        print("\n--- %s ---" % p)
        print("  title       : %s" % row.get("title"))
        end = row.get("reveal_end") or {}
        print("  reveal      : %d/%d shown on load; after full scroll %s/%s shown, %s never triggered"
              % (row.get("rise_in", 0), row.get("rise_total", 0),
                 (end.get("total", 0) - end.get("faded", 0)), end.get("total", 0), end.get("never")))
        if p == "index.html":
            print("  animation   : aurora=%s/%s  veil=%s  beam=%s"
                  % (row.get("aurora_animation"), row.get("aurora_duration"),
                     row.get("veil_animation"), row.get("beam_animation")))
            print("  ticker      : %s spans" % row.get("ticker_children"))
        ff = row.get("fonts") or {}
        print("  fonts       : %s  (inter %s, serif %s%s, mono %s%s)"
              % (ff.get("status"), ff.get("inter"), ff.get("serif"),
                 "" if row.get("has_display") else " n/a", ff.get("mono"),
                 "" if row.get("has_mono") else " n/a"))
        print("  header      : top=%s  scrolled: stuck=%s bg=%s colour=%s"
              % (row.get("body_bg"), sc.get("stuck_class"), sc.get("bg"), sc.get("colour")))
        print("  copy button : %s" % row.get("label_after"))
        if issues:
            print("  FINDINGS    : %s" % "; ".join(issues))

    real_errors = []
    for e in errors:
        m = e.get("method")
        if m == "Runtime.exceptionThrown":
            real_errors.append(str(e.get("params", {}).get("exceptionDetails", ""))[:200])
        elif m == "Runtime.consoleAPICalled" and e.get("params", {}).get("type") == "error":
            real_errors.append(json.dumps(e.get("params", {}).get("args", []))[:200])
        elif m == "Log.entryAdded" and e.get("params", {}).get("entry", {}).get("level") == "error":
            real_errors.append(e["params"]["entry"].get("text", "")[:200])

    print("\n" + "=" * 66)
    if real_errors:
        print("console errors (%d)" % len(real_errors))
        for t in real_errors[:12]:
            print("  ! %s" % t)
        bad += 1
    else:
        print("console errors: none")
    print("pages with findings: %d" % bad)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="http://127.0.0.1:8899")
    ap.add_argument("--port", type=int, default=9422)
    args = ap.parse_args()

    chrome = ui_probe.find_chrome()
    proc = ui_probe.launch(chrome, args.port)
    try:
        ws_url = ui_probe.attach(args.port)
        results, errors = asyncio.run(run(ws_url, args.base))
    finally:
        proc.kill()
    sys.exit(1 if report(results, errors) else 0)


if __name__ == "__main__":
    main()
