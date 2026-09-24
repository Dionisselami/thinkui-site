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
    ("login.html",    "Sign in — ThinkUI",                                             False),
    ("signup.html",   "Create your account — ThinkUI",                                 False),
    ("404.html",      "Page not found — ThinkUI",                                      False),
    ("terms.html",    "Terms of service — ThinkUI",                                    False),
    ("privacy.html",  "Privacy — ThinkUI",                                             False),
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


def tokens(page: str) -> dict:
    return {
        "SITE_URL": SITE_URL.rstrip("/"),
        "YEAR": str(dt.date.today().year),
        "CONTACT_EMAIL": CONTACT_EMAIL,
        "CANONICAL": "%s/%s" % (SITE_URL.rstrip("/"), "" if page == "index.html" else page),
        "ROBOTS": "noindex, follow" if page in NOINDEX else "index, follow, max-image-preview:large",
        # the browser-chrome colour is the brand ink, read from the identity rather than
        # retyped here, so a palette change cannot leave it behind
        "ICONS": ICONS.replace("__THEME__", identity()["ink"]),
        "LOGO": inline_logo("logo.svg", "lg-nav"),
        "LOGO_INVERSE": inline_logo("logo-inverse.svg", "lg-foot"),
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


def build_pages():
    made = []
    for page, title, _ in PAGES:
        src = os.path.join(HERE, page)
        if not os.path.exists(src):
            print("  missing src/%s — skipped" % page)
            continue
        text = render(page, open(src, encoding="utf-8").read())
        out = os.path.join(SITE, page)
        open(out, "w", encoding="utf-8").write(text)
        made.append((page, os.path.getsize(out)))
    return made


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
        loc = url + "/" if page == "index.html" else "%s/%s" % (url, page)
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
    d.text((W - 424, 552), "Runs locally over stdio · Any MCP client",
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
