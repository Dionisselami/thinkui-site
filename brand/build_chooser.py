#!/usr/bin/env python3
"""build_chooser.py — the page you look at to pick a mark.

Written from the same MARKS definitions build_logos.py emits, so what you approve on
this page is what ships in out/.

    python build_chooser.py      ->  brand/index.html
"""

from __future__ import annotations

import os

from build_logos import load_offsets  # noqa: F401  (kept beside the other imports)
from build_logos import BLOCK, MARK, MARKS, BRAND_A, BRAND_B, svg_text

HERE = os.path.dirname(os.path.abspath(__file__))

# the mark as it exists on the site today: rounded gradient tile, inner square
CURRENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" aria-label="current mark">
  <defs><linearGradient id="cur" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs>
  <rect width="64" height="64" rx="15" fill="url(#cur)"/>
  <rect x="18" y="18" width="28" height="28" rx="7" fill="#ffffff" fill-opacity=".94"/>
</svg>""".format(a=BRAND_A, b=BRAND_B)

CARD = """
<article class="opt">
  <div class="opt__head">
    <span class="num">{n}</span>
    <div>
      <h2>{name}</h2>
      <p class="idea">{idea}</p>
    </div>
  </div>

  <div class="opt__row">
    <figure class="col col--sizes">
      <figcaption>App icon</figcaption>
      <div class="sizes">
        <span class="s96">{block96}</span>
        <span class="s48">{block48}</span>
        <span class="s24">{block24}</span>
        <span class="s16">{block16}</span>
      </div>
      <p class="tiny">96 · 48 · 24 · <b>16px actual</b></p>
    </figure>

    <figure class="col">
      <figcaption>Mark, on paper and on ink</figcaption>
      <div class="grounds">
        <span class="ground ground--paper">{mark_dark}</span>
        <span class="ground ground--ink">{mark_light}</span>
      </div>
      <p class="tiny">transparent background, one colour</p>
    </figure>

    <figure class="col">
      <figcaption>Lockup</figcaption>
      <div class="lock">
        <span class="lock__mark">{mark_lock}</span>
        <span class="lock__word">Think<span class="ui">UI</span></span>
      </div>
      <p class="tiny">mark sized to the wordmark's cap height</p>
    </figure>
  </div>

  <p class="note">{note}</p>
  <button class="pick" data-hermes-send="Use logo option {n} — {name}">Use {n} · {name}</button>
</article>
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ThinkUI — logo options</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --ink: #05070c; --ink-2: #0d1119; --paper: #ffffff; --paper-2: #f4f6fa;
    --fg: #0b0d12; --fg-soft: #4a505c; --fg-mute: #6b7280;
    --on-ink: #f7f9fc; --on-ink-soft: #a7b0c0; --on-ink-mute: #7b8595;
    --line: rgba(255,255,255,.10); --line-2: rgba(255,255,255,.18);
    --brand-a: {a}; --brand-b: {b};
    --sans: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--ink); color: var(--on-ink);
    font: 400 15px/1.6 var(--sans); letter-spacing: -.005em;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 1240px; margin: 0 auto; padding: 56px 32px 80px; }}
  header.top {{ max-width: 62ch; margin-bottom: 44px; }}
  .kicker {{ font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: #a5b4fc; }}
  h1 {{ font-size: 40px; line-height: 1.1; letter-spacing: -.03em; margin: 12px 0 14px; font-weight: 600; }}
  header.top p {{ color: var(--on-ink-soft); margin: 0; }}
  header.top p + p {{ margin-top: 10px; }}

  .current {{
    display: flex; align-items: center; gap: 18px; margin: 34px 0 8px;
    padding: 18px 20px; border: 1px dashed var(--line-2); border-radius: 14px;
    background: rgba(255,255,255,.03);
  }}
  .current svg {{ width: 44px; height: 44px; flex: none; }}
  .current p {{ margin: 0; color: var(--on-ink-soft); font-size: 14px; }}
  .current b {{ color: #fff; }}

  .opt {{
    margin-top: 26px; padding: 30px 30px 26px;
    border: 1px solid var(--line); border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,.035), rgba(255,255,255,0));
  }}
  .opt__head {{ display: flex; gap: 16px; align-items: flex-start; }}
  .num {{
    flex: none; width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center;
    background: linear-gradient(140deg, var(--brand-a), var(--brand-b)); color: #fff;
    font: 600 15px/1 var(--sans);
  }}
  .opt h2 {{ font-size: 21px; letter-spacing: -.02em; margin: 4px 0 8px; }}
  .idea {{ margin: 0; color: var(--on-ink-soft); max-width: 74ch; }}
  .note {{ margin: 20px 0 0; font-size: 13.5px; color: var(--on-ink-mute); }}

  .opt__row {{ display: grid; grid-template-columns: 1.25fr 1fr 1fr; gap: 26px; margin-top: 26px; }}
  figure {{ margin: 0; }}
  figcaption {{
    font-size: 11.5px; letter-spacing: .09em; text-transform: uppercase;
    color: var(--on-ink-mute); margin-bottom: 14px;
  }}
  .tiny {{ margin: 12px 0 0; font-size: 12px; color: var(--on-ink-mute); }}
  .tiny b {{ color: var(--on-ink-soft); }}

  .sizes {{ display: flex; align-items: flex-end; gap: 16px; }}
  .sizes span {{ display: block; line-height: 0; }}
  .s96 svg {{ width: 96px; height: 96px; }}
  .s48 svg {{ width: 48px; height: 48px; }}
  .s24 svg {{ width: 24px; height: 24px; }}
  .s16 svg {{ width: 16px; height: 16px; }}

  .grounds {{ display: flex; gap: 14px; }}
  .ground {{
    width: 96px; height: 96px; border-radius: 14px; display: grid; place-items: center;
    border: 1px solid var(--line);
  }}
  .ground svg {{ width: 56px; height: 56px; }}
  .ground--paper {{ background: var(--paper); color: var(--fg); border-color: transparent; }}
  .ground--ink {{ background: var(--ink-2); color: #fff; }}

  .lock {{ display: flex; align-items: center; gap: 12px; padding-top: 18px; }}
  .lock__mark svg {{ width: 22px; height: 22px; display: block; color: #fff; }}
  .lock__word {{ font-size: 30px; font-weight: 600; letter-spacing: -.025em; line-height: 1; }}
  .lock__word .ui {{
    background: linear-gradient(96deg, #a5b4fc, #67e8f9);
    -webkit-background-clip: text; background-clip: text;
    color: transparent; -webkit-text-fill-color: transparent;
  }}

  .pick {{
    margin-top: 22px; padding: 12px 20px; border-radius: 10px; cursor: pointer;
    border: 1px solid var(--line-2); background: rgba(255,255,255,.06); color: #fff;
    font: 550 14px/1 var(--sans);
    transition: background .18s ease, transform .18s ease, border-color .18s ease;
  }}
  .pick:hover {{ background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.34); transform: translateY(-1px); }}

  footer.foot {{ margin-top: 46px; color: var(--on-ink-mute); font-size: 13.5px; }}
  @media (max-width: 980px) {{
    .opt__row {{ grid-template-columns: 1fr; }}
    h1 {{ font-size: 30px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <span class="kicker">ThinkUI · brand</span>
    <h1>Six directions for the mark.</h1>
    <p>Each one is a different idea, not a variation — so pick the idea you want the brand to
      stand for, and I will finish that one properly: outlined wordmark, full icon set,
      favicons, social avatar.</p>
    <p>Before drawing these I ruled out what every AI and developer tool reaches for: a sparkle,
      a brain, a chat bubble, a pair of angle brackets. None of the six is any of those.</p>
  </header>

  <div class="current">
    {current}
    <p><b>What you have now:</b> a plain gradient tile with a square in it — a placeholder,
      not a mark. It carries no idea, which is why it reads as a template.</p>
  </div>

{cards}

  <footer class="foot">
    The files for every option are already written to <code>brand/out/</code> — block (app icon),
    mark (transparent, one colour) and mono. Tell me the number and I will ship the set.
  </footer>
</div>
<script>
  // inside a preview pane the button calls home; in a plain browser it is inert
  document.addEventListener('click', function (ev) {{
    var b = ev.target.closest && ev.target.closest('[data-hermes-send]');
    if (b) {{ b.textContent = 'Picked — tell me in chat if nothing happened'; }}
  }});
</script>
</body>
</html>
"""


def main():
    off = load_offsets()
    cards = ""
    for n, mark in enumerate(MARKS, 1):
        block = svg_text(BLOCK, mark, "#ffffff", "", off).replace('id="ground"', 'id="ground%d"' % n) \
                                                      .replace('id="sheen"', 'id="sheen%d"' % n) \
                                                      .replace('url(#ground)', 'url(#ground%d)' % n) \
                                                      .replace('url(#sheen)', 'url(#sheen%d)' % n)
        bare = svg_text(MARK, mark, "currentColor", "", off)
        cards += CARD.format(
            n=n, name=mark["name"], idea=mark["idea"], note=mark["note"],
            block96=block, block48=block, block24=block, block16=block,
            mark_dark=svg_text(MARK, mark, "#0b0d12", "", off),   # on paper
            mark_light=bare,                                       # on ink
            mark_lock=bare,
        )

    html = PAGE.format(current=CURRENT, cards=cards, a=BRAND_A, b=BRAND_B)
    path = os.path.join(HERE, "index.html")
    open(path, "w", encoding="utf-8").write(html)
    print("wrote %s (%.1f KB, %d options)" % (path, os.path.getsize(path) / 1024, len(MARKS)))


if __name__ == "__main__":
    main()
