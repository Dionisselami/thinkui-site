#!/usr/bin/env python3
"""build.py — stamp the product site from src/ into the served directory.

One place defines the domain, so canonical URLs, Open Graph tags and the sitemap
can never disagree with each other or with the deployed host. Set SITE_URL once,
run this, and the whole site follows.

    python build.py                 # uses SITE_URL below
    python build.py --url https://thinkui.xyz

Writes:
    ../index.html ../pricing.html ../docs.html ../login.html ../signup.html
    ../404.html ../sitemap.xml ../robots.txt ../assets/img/og.png
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import html as htmllib
import os
import re
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))          # .../appvault/src
SITE = os.path.dirname(HERE)                               # .../appvault

# Change this to the domain the site is served from, or pass --url.
SITE_URL = "https://thinkui.xyz"

# The address shown on the legal pages and in the footer contact line.
CONTACT_EMAIL = "support@thinkui.xyz"

BRAND = "ThinkUI"
TAGLINE = ("Interface references your coding agent can actually use — real screens, "
           "flows, components, fonts and icons, each one traceable to its source.")

PAGES = [
    # file,           title,                                                          in sitemap
    ("index.html",    "ThinkUI — UI references for your coding agent, over MCP",       True),
    ("pricing.html",  "Pricing — ThinkUI MCP server",                                  True),
    ("docs.html",     "Quickstart — connecting the ThinkUI MCP server",                True),
    ("examples.html", "What the ThinkUI tools actually return — real MCP responses",   True),
    ("login.html",    "Sign in — ThinkUI",                                             False),
    ("signup.html",   "Create your account — ThinkUI",                                 False),
    ("404.html",      "Page not found — ThinkUI",                                      False),
    ("terms.html",    "Terms of service — ThinkUI",                                    True),
    ("privacy.html",  "Privacy — ThinkUI",                                             True),
]

# pages that must never be indexed (auth surfaces) vs. the 404 (noindex too)
NOINDEX = {"login.html", "signup.html", "404.html"}


IDENTITY = os.path.join(HERE, "identity.json")


def identity() -> dict:
    """The brand geometry, written by ../brand/build_identity.py.

    The mark is not re-typed here: the SVG assets and the social card both read these
    numbers, so the icon in the tab and the mark on the card cannot drift apart.
    """
    import json
    if not os.path.exists(IDENTITY):
        raise SystemExit("missing src/identity.json — run: "
                         "uv run --with fonttools --with uharfbuzz python ../brand/build_identity.py")
    return json.load(open(IDENTITY, encoding="utf-8"))


def inline_logo(name: str, uid: str) -> str:
    """The lockup, inlined so its gradient works and no extra request is made.

    Each placement gets its own gradient id: two lockups on one page sharing ids means
    the second silently renders in the first one's colours.
    """
    path = os.path.join(SITE, "assets", "img", name)
    if not os.path.exists(path):
        raise SystemExit("missing assets/img/%s — run ../brand/build_identity.py" % name)
    svg = open(path, encoding="utf-8").read().strip()
    svg = svg.replace(' id="lg-g"', ' id="%s-g"' % uid).replace(' id="lg-s"', ' id="%s-s"' % uid)
    svg = svg.replace("url(#lg-g)", "url(#%s-g)" % uid).replace("url(#lg-s)", "url(#%s-s)" % uid)
    return svg.replace("<svg ", '<svg class="brand__logo" ', 1)


ICONS = """<link rel="icon" href="assets/img/favicon.ico" sizes="any">
<link rel="icon" href="assets/img/favicon.svg" type="image/svg+xml">
<link rel="icon" type="image/png" sizes="32x32" href="assets/img/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="assets/img/favicon-16.png">
<link rel="apple-touch-icon" href="assets/img/apple-touch-icon.png">
<link rel="manifest" href="site.webmanifest">
<meta name="theme-color" content="__THEME__">
<meta name="apple-mobile-web-app-title" content="ThinkUI">"""


COMPONENTS_JSON = os.path.join(HERE, "_components.json")


def _solo(code: str) -> str:
    """Keep one element and the CSS that dresses it.

    A snippet from the corpus often carries a row of demo variants ("Paste the markup
    and the…") after the component itself. Shrunk into a 260px frame those extra
    siblings show up as clipped fragments, which reads as a broken page rather than a
    component. One element plus every style block is what the caption claims.
    """
    styles = re.findall(r"<style.*?</style>", code, re.S)
    body = re.sub(r"<style.*?</style>", "", code, flags=re.S)
    m = re.match(r"\s*(<([a-zA-Z][\w-]*)[^>]*>.*?</>)", body, re.S)
    return ("".join(styles) + (m.group(1) if m else body)).strip()


def _zoom(code: str) -> float:
    """A component written for a full-width demo section has to be shrunk to sit in a
    260px frame; clipping it looks broken, and a third of a button is worse than a
    small one."""
    n = len(code)
    if n >= 2400:
        return 0.5
    if n >= 1500:
        return 0.62
    if n >= 900:
        return 0.75
    return 1.0


def components_mosaic() -> str:
    """The product's own output, rendered on the page instead of described.

    Each element arrives with global CSS (`button { ... }`), so it cannot go into this
    document: one component's reset would restyle every button on the site. srcdoc plus
    sandbox gives each one its own document - which is also exactly how a buyer should
    isolate a paste.

    Captions use the CATEGORY, not the element's own name. The corpus names are
    generated handles ("new dog 56", "wicked bear 73") and on a sales page they read as
    placeholder test data.
    """
    try:
        data = json.load(open(COMPONENTS_JSON, encoding="utf-8"))
    except Exception:
        return ""
    esc = lambda v: htmllib.escape(str(v), quote=True)
    cells = []
    # Only compact, self-contained categories: a full card or a toggle with display
    # type cannot be shown at phone scale in a fixed frame without looking broken.
    keep = set()   # see note: demo snippets, not clean controls
    shown = [e for e in data.get("elements", [])
             if e.get("category") in keep][:1]
    for el in shown:
        doc = ('<!doctype html><meta charset="utf-8"><style>'
               'html,body{height:100%;margin:0;display:grid;place-items:center;'
               'padding:12px;font-family:system-ui,-apple-system,sans-serif;'
               'background:transparent;color:#1a1613}*{box-sizing:border-box}</style>'
               + ('<div style="zoom:%.2f">' % _zoom(el.get("code", ""))) + re.sub(r"<script.*?</script>", "", el["code"], flags=re.S) + "</div>")
        names = {"Buttons": "Button", "Toggle-switches": "Toggle", "loaders": "Loader",
                 "Inputs": "Input", "Cards": "Card", "Checkboxes": "Checkbox",
                 "Tooltips": "Tooltip"}
        label = names.get(el["category"], (el["category"] or el["name"]).replace("-", " "))
        cells.append(
            '<figure class="mosaic__cell">'
            '<iframe class="mosaic__frame" title="%s, rendered from the server" '
            'scrolling="no" srcdoc="%s"></iframe>'
            '<figcaption class="mosaic__cap">%s <span>MIT</span></figcaption>'
            '</figure>' % (esc(label), esc(doc), esc(label)))

    icons = data.get("icons", [])[:3]
    if icons:
        cells.append(
            '<div class="mosaic__cell">'
            '<div class="mosaic__icons">%s</div>'
            '<div class="mosaic__cap">Icon <span>MIT</span></div>'
            '</div>' % "".join(i["svg"] for i in icons))
    return chr(10).join(cells)


PROOF_JSON = os.path.join(HERE, "_proof.json")


def _proof() -> list:
    try:
        return json.load(open(PROOF_JSON, encoding="utf-8"))
    except Exception:
        return []


def _shot(r: dict, big: bool = False) -> str:
    esc = lambda v: htmllib.escape(str(v), quote=True)
    cap = r.get("caption") or ""
    lic = r.get("licence") or "see source"
    return (
        '<figure class="shot%s">'
        '<img src="%s" alt="%s interface, %s" width="%d" height="%d" loading="%s" decoding="async">'
        '<figcaption class="shot__cap">'
        '<span class="shot__app">%s</span>'
        '<span class="shot__meta">%s%s &middot; %s</span>'
        '</figcaption></figure>' % (
            " shot--big" if big else "",
            esc(r["file"]), esc(r["app"]), esc(r["title"]), r.get("w", 1000), r.get("h", 600),
            "eager" if big else "lazy",
            esc(r["app"]), esc(r["title"]), "", esc(lic)))


def proof_hero() -> str:
    """The first thing a buyer sees should be the thing being sold: a real screen,
    with the project it came from and the licence it carries."""
    rows = _proof()
    return _shot(rows[0], big=True) if rows else ""


def proof_gallery() -> str:
    rows = _proof()[1:]
    return chr(10).join(_shot(r) for r in rows)


WALL_JSON = os.path.join(HERE, "_wall.json")


def screen_wall() -> str:
    """The library itself, as the first thing you see.

    A product whose value is visual should not open with a paragraph about itself.
    Every card is a real screen from the corpus, credited with the app it came from
    and the licence it carries - the same thing the server returns.
    """
    try:
        rows = json.load(open(WALL_JSON, encoding="utf-8"))
    except Exception:
        return ""
    esc = lambda v: htmllib.escape(str(v), quote=True)
    out = []
    for r in rows:
        out.append(
            '<figure class="wall__card">'
            '<img src="%s" alt="%s, %s screen" width="%d" height="%d" loading="lazy" decoding="async">'
            '<figcaption class="wall__meta"><b>%s</b><span>%s &middot; %s</span></figcaption>'
            '</figure>' % (esc(r["file"]), esc(r["app"]), esc(r["flow"]),
                           r.get("w", 460), r.get("h", 900),
                           esc(r["app"]), esc(r["flow"]), esc(r["licence"])))
    return chr(10).join(out)


def tokens(page: str) -> dict:
    return {
        "SITE_URL": SITE_URL.rstrip("/"),
        "YEAR": str(dt.date.today().year),
        "CONTACT_EMAIL": CONTACT_EMAIL,
        "CANONICAL": "%s/%s" % (SITE_URL.rstrip("/"), ""
                                if page == "index.html"
                                else (page[:-5] if page.endswith(".html") and page != "404.html"
                                      else page)),
        "ROBOTS": "noindex, follow" if page in NOINDEX else "index, follow, max-image-preview:large",
        # the browser-chrome colour is the brand ink, read from the identity rather than
        # retyped here, so a palette change cannot leave it behind
        "ICONS": ICONS.replace("__THEME__", identity()["ink"]),
        "LOGO": inline_logo("logo.svg", "lg-nav"),
        "LOGO_INVERSE": inline_logo("logo-inverse.svg", "lg-foot"),
        "COMPONENTS": components_mosaic(),
        "PROOF_HERO": proof_hero(),
        "WALL": screen_wall(),
        "PROOF_GALLERY": proof_gallery(),
    }


PARTIAL = re.compile(r"\{\{>([a-z_]+)\}\}")


def inject_partials(text: str) -> str:
    """Splice src/_name.html into {{>name}} so the nav and footer have one source."""
    def sub(m):
        path = os.path.join(HERE, "_%s.html" % m.group(1))
        if not os.path.exists(path):
            raise SystemExit("missing partial src/_%s.html" % m.group(1))
        return open(path, encoding="utf-8").read().rstrip("\n")
    return PARTIAL.sub(sub, text)


def render(page: str, text: str) -> str:
    text = inject_partials(text)
    for k, v in tokens(page).items():
        text = text.replace("{{%s}}" % k, v)
    # a leftover token means a typo in a template; fail loudly rather than ship it
    left = re.findall(r"\{\{[>A-Z_]+\}\}", text)
    if left:
        raise SystemExit("%s: unresolved token(s) %s" % (page, ", ".join(sorted(set(left)))))
    return text


def asset_version(rel: str) -> str:
    """A short content hash for one asset, or "" if it is not on disk.

    The pages used to reference assets/css/site.css and assets/js/field.js with no version
    at all. That is fine until the file changes: a browser (or a webview, or a CDN) that
    holds the old copy keeps serving it against the new HTML, and the page renders as a
    mix of two builds. That is not hypothetical - it is how a fixed hero animation went on
    being reported as broken. The hash makes every change a new URL, so a stale asset can
    never pair with a fresh page.

    Fonts are deliberately excluded: the @font-face URL in the stylesheet and the preload
    in the markup have to match exactly, and they live in two different files. Renaming the
    woff2 is the way to force a font refresh.
    """
    path = os.path.join(SITE, rel)
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:10]
    except OSError:
        return ""


ASSET_RE = re.compile(r"(assets/[\w./\-]+\.(?:css|js))(?![?\w])")


def version_assets(text: str) -> str:
    def sub(m):
        rel = m.group(1)
        v = asset_version(rel)
        return "%s?v=%s" % (rel, v) if v else rel
    return ASSET_RE.sub(sub, text)


_INT_LINK = re.compile(r'href="(?:\./)?([a-z0-9_-]+)\.html(#[^"]*|\?[^"]*)?"')


def clean_links(text: str) -> str:
    """Point internal links at the extension-less URL that the canonical names.

    The pages are files on disk but the canonical (and the sitemap) say /pricing, so
    leaving every link on /pricing.html made the site advertise a URL it then asked
    Google not to index. Done here rather than in twenty templates so a new page cannot
    quietly reintroduce the .html form.
    """
    def swap(m):
        name, tail = m.group(1), m.group(2) or ""
        return 'href="%s%s"' % ("/" if name == "index" else "/" + name, tail)
    return _INT_LINK.sub(swap, text)


def build_pages():
    made = []
    for page, title, _ in PAGES:
        src = os.path.join(HERE, page)
        if not os.path.exists(src):
            print("  missing src/%s — skipped" % page)
            continue
        text = clean_links(version_assets(render(page, open(src, encoding="utf-8").read())))
        out = os.path.join(SITE, page)
        open(out, "w", encoding="utf-8").write(text)
        if page == "index.html":
            n = sync_faq_schema(out)
            if n:
                print("  faq schema      %d questions synced to the visible copy" % n)
        made.append((page, os.path.getsize(out)))
    return made


def sync_faq_schema(path: str) -> int:
    """Make the FAQPage structured data say exactly what the page says.

    The FAQ exists twice: the visible <details> blocks and the JSON-LD a crawler reads.
    They had drifted apart on five of six answers — one still described a server running
    locally on a hosted product — and a schema that contradicts the page is worse than no
    schema. Derive it from the visible copy so the two cannot disagree.
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    pairs = []
    for m in re.finditer(r'<summary[^>]*>(.*?)</summary>\s*<div class="answer">\s*<p[^>]*>(.*?)</p>',
                         text, re.S):
        q = html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))
        a = html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))
        pairs.append((re.sub(r"\s+", " ", q).strip(), re.sub(r"\s+", " ", a).strip()))
    if not pairs:
        return 0

    block = re.search(r'(<script[^>]*type="application/ld\+json"[^>]*>)(.*?)(</script>)', text, re.S)
    if not block:
        return 0
    try:
        data = json.loads(block.group(2))
    except json.JSONDecodeError:
        return 0

    # The graph may be the document itself, a bare list, or wrapped in a @graph node.
    if isinstance(data, dict) and isinstance(data.get("@graph"), list):
        nodes = data["@graph"]
    else:
        nodes = data if isinstance(data, list) else [data]
    found = False
    for node in nodes:
        if isinstance(node, dict) and node.get("@type") == "FAQPage":
            node["mainEntity"] = [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in pairs]
            found = True
    if not found:
        return 0

    text = text[:block.start(2)] + json.dumps(data, ensure_ascii=False, indent=2) + text[block.end(2):]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return len(pairs)


def last_change(path: str) -> str:
    """When this page last actually changed.

    The sitemap used to stamp every URL with the build date, so all of them always carried
    the same value no matter which page had been touched - a generator fingerprint, and
    useless to a crawler. Git knows the real answer; the file's mtime is the fallback for a
    checkout without history.
    """
    try:
        out = subprocess.run(["git", "-C", SITE, "log", "-1", "--format=%cs", "--", path],
                             capture_output=True, text=True, timeout=15)
        stamp = (out.stdout or "").strip()
        if out.returncode == 0 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp):
            return stamp
    except Exception:  # noqa: BLE001 - no git, no history, no problem
        pass
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()


def build_sitemap():
    url = SITE_URL.rstrip("/")
    rows = []
    for page, _, listed in PAGES:
        if not listed:
            continue
        loc = url + "/" if page == "index.html" else "%s/%s" % (
            url, page[:-5] if page.endswith(".html") else page)
        priority = "1.0" if page == "index.html" else ("0.9" if page == "pricing.html" else "0.8")
        rows.append("  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n"
                    "    <changefreq>weekly</changefreq>\n    <priority>%s</priority>\n  </url>"
                    % (loc, last_change(os.path.join(HERE, page)), priority))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(rows) + "\n</urlset>\n")
    open(os.path.join(SITE, "sitemap.xml"), "w", encoding="utf-8").write(xml)
    return len(rows)


def build_robots():
    url = SITE_URL.rstrip("/")
    txt = ("# ThinkUI\n"
           "User-agent: *\n"
           "Allow: /\n"
           "Disallow: /api/\n"          # the MCP endpoint is for agents, not crawlers
           "Disallow: /login\n"
           "Disallow: /signup\n"
           "\n"
           "Sitemap: %s/sitemap.xml\n" % url)
    open(os.path.join(SITE, "robots.txt"), "w", encoding="utf-8").write(txt)
    return txt.count("Sitemap:")


def build_og():
    """A 1200x630 social card, drawn rather than screenshotted so it stays crisp."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # noqa: BLE001
        print("  Pillow unavailable (%s) — skipped og.png" % exc)
        return False

    W, H = 1200, 630
    ident = identity()

    def hx(s):
        return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))

    # One flat ink, no spotlight. The card used to be painted with a hand-rolled indigo to
    # cyan glow, which is the same atmosphere the site has just dropped, and it dragged the
    # whole card blue. The colour now comes from the identity.
    # Every colour on the card comes from the identity: a cold slate grey used to be
    # hard-coded here, left over from when the palette was blue.
    img = Image.new("RGB", (W, H), hx(ident["ink"]))
    d = ImageDraw.Draw(img, "RGBA")
    wordmark_path = os.path.join(SITE, "brand", "fonts", "bricolage-grotesque-var.ttf")

    def font(size, weight="R"):
        wght = 600 if weight == "B" else 400
        if os.path.exists(wordmark_path):
            try:
                f = ImageFont.truetype(wordmark_path, size)
                # The card must use the wordmark's own weight and optical size, or the type
                # silently reverts to whatever the variable font defaults to. Bricolage
                # Grotesque carries three axes in this order - opsz, wght, wdth - so set all
                # three; fall back to the two that matter if it is ever re-cut without wdth.
                try:
                    f.set_variation_by_axes([ident["opsz"], wght, 100])
                except Exception:  # noqa: BLE001
                    f.set_variation_by_axes([ident["opsz"], wght])
                return f
            except Exception as exc:  # noqa: BLE001
                print("  (wordmark font unavailable: %s)" % exc)
        for name in (["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"] if weight == "B"
                     else ["segoeui.ttf", "arial.ttf"]):
            try:
                return ImageFont.truetype(name, size)
            except Exception:  # noqa: BLE001
                continue
        return ImageFont.load_default()

    # the mark: same geometry as the SVG, scaled from the shared numbers
    tile, tx, ty = 52, 84, 76
    k = tile / ident["grid"]
    # the tile in the brand's own accent, deeper at the bottom: the same one-hue depth the
    # logo has, drawn line by line because Pillow has no gradient
    ta, tb = hx(ident["tile_a"]), hx(ident["tile_b"])
    for i in range(tile):
        t = i / float(tile - 1)
        col = tuple(int(ta[c] + (tb[c] - ta[c]) * t) for c in range(3))
        d.line([(tx, ty + i), (tx + tile, ty + i)], fill=col)
    d.rounded_rectangle([(tx, ty), (tx + tile, ty + tile)],
                        radius=ident["tile_radius"] * k, outline=(255, 255, 255, 70), width=2)
    stack_top = (ident["grid"] - ident["ink_h"]) / 2.0
    gap = (ident["ink_h"] - 3 * ident["tile_t"]) / 2.0
    y = ty + stack_top * k
    for w in ident["bars"]:
        bh = ident["tile_t"] * k
        d.rounded_rectangle([(tx + ident["bar_x"] * k, y),
                             (tx + (ident["bar_x"] + w) * k, y + bh)],
                            radius=bh / 2.0, fill=(255, 255, 255, 240))
        y += (ident["tile_t"] + gap) * k
    d.text((152, 86), ident["word"], font=font(38, "B"), fill=(255, 255, 255, 245))
    d.text((152, 128), "MCP server", font=font(20), fill=hx(ident["on_ink_soft"]) + (255,))

    # headline, wrapped
    head = "Interface references your agent can actually use."
    words, lines, cur = head.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=font(62, "B")) > W - 180:
            lines.append(cur); cur = w
        else:
            cur = trial
    lines.append(cur)
    y = 236
    for ln in lines:
        d.text((84, y), ln, font=font(62, "B"), fill=(255, 255, 255, 250))
        y += 78

    d.text((84, y + 26), "Screens · Flows · Components · Fonts · Icons — traceable to source",
           font=font(25), fill=hx(ident["on_ink_soft"]) + (255,))

    d.line([(84, 520), (W - 84, 520)], fill=(255, 255, 255, 40), width=1)
    d.text((84, 552), urllib.parse.urlparse(SITE_URL).netloc,
           font=font(24, "B"), fill=(255, 255, 255, 220))
    d.text((W - 424, 552), "Hosted · one URL · any MCP client",
           font=font(22), fill=hx(ident["on_ink_soft"]) + (255,))

    out = os.path.join(SITE, "assets", "img", "og.png")
    img.save(out, "PNG", optimize=True)
    print("  og.png %dx%d (%.0f KB)" % (W, H, os.path.getsize(out) / 1024))
    return True


def main():
    global SITE_URL
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=None, help="domain the site is served from")
    args = ap.parse_args()
    if args.url:
        SITE_URL = args.url

    print("building %s" % SITE_URL.rstrip("/"))
    made = build_pages()
    for page, size in made:
        print("  %-14s %6.1f KB" % (page, size / 1024))
    print("  sitemap.xml    %d URLs" % build_sitemap())
    build_robots()
    print("  robots.txt     written")
    build_og()
    return 0


if __name__ == "__main__":
    sys.exit(main())
