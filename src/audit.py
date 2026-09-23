#!/usr/bin/env python3
"""audit.py — check the built site the way a crawler and a link checker would.

Run from src/ after build.py:  python audit.py

Checks
  1  every page: title, description, canonical, robots meta, exactly one h1
  2  titles and descriptions are unique across the site
  3  every JSON-LD block is valid JSON
  4  every internal link and asset reference resolves to a file on disk
  5  no template token survived into the output
  6  the product surface does not talk about licensing or about the raw shelves
  7  sitemap.xml parses, and every URL in it is a real page
  8  the Open Graph card is the right size and is not a blank rectangle
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)

PAGES = [
    "index.html", "pricing.html", "docs.html", "login.html",
    "signup.html", "404.html", "terms.html", "privacy.html",
]

# words that must not appear on the product surface
# matched on word boundaries: a bare "MIT" search also hits "submit" and "limit"
BANNED_WORDS = ["licence", "licenses", "license", "publishable", "study-only",
                "redistributable", "open-source licence", "attribution"]
BANNED_TOKENS = [r"\bMIT\b", r"\bApache-2\.0\b", r"\bAGPL\b", r"\bOFL\b", r"\bCC BY\b"]
# the raw shelves the product no longer shows
SHELVES = ["screens.html", "materials.html", "elements.html", "icons.html", "sources.html",
           "/screens", "/materials", "/elements", "/icons", "/sources"]

fails: list[str] = []
warns: list[str] = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def read(name):
    with open(os.path.join(SITE, name), encoding="utf-8") as fh:
        return fh.read()


def one(pattern, text, flags=re.S | re.I):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


print("auditing %d pages\n" % len(PAGES))

titles, descs = {}, {}
all_refs: dict[str, set] = {}

for page in PAGES:
    path = os.path.join(SITE, page)
    check(os.path.exists(path), "%s: missing" % page)
    if not os.path.exists(path):
        continue
    h = read(page)

    title = one(r"<title>(.*?)</title>", h)
    desc = one(r'<meta name="description" content="(.*?)">', h)
    canon = one(r'<link rel="canonical" href="(.*?)">', h)
    robots = one(r'<meta name="robots" content="(.*?)">', h)
    h1s = re.findall(r"<h1[ >]", h, re.I)

    check(title and 15 <= len(title) <= 65, "%s: title length %s" % (page, len(title or "")))
    check(desc and 60 <= len(desc) <= 165, "%s: description length %s" % (page, len(desc or "")))
    check(canon, "%s: no canonical" % page)
    check(robots, "%s: no robots meta" % page)
    check(len(h1s) == 1, "%s: %d h1 elements" % (page, len(h1s)))

    if page in ("login.html", "signup.html", "404.html"):
        check(robots and "noindex" in robots, "%s: should be noindex" % page)
    else:
        check(robots and robots.startswith("index"), "%s: should be indexable" % page)

    if canon:
        if page == "index.html":
            ok = canon.endswith("/")
        else:
            ok = canon.endswith("/" + page)
        check(ok, "%s: canonical points elsewhere (%s)" % (page, canon))
        check(canon.startswith("https://"), "%s: canonical is not absolute" % page)

    titles[page], descs[page] = title, desc

    # json-ld
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try:
            json.loads(block)
        except Exception as exc:  # noqa: BLE001
            fails.append("%s: invalid JSON-LD (%s)" % (page, exc))

    # references that must exist on disk
    refs = set(re.findall(r'(?:href|src)="([^"#]+)"', h))
    # /api/... are backend endpoints the front end posts to, not files to serve
    refs = {r for r in refs if not r.startswith(("http", "mailto:", "//", "/api/"))}
    all_refs[page] = refs

    # tokens and banned language
    for tok in re.findall(r"\{\{[^}]+\}\}", h):
        fails.append("%s: unresolved token %s" % (page, tok))
    low = h.lower()
    for word in BANNED_WORDS:
        if word in low:
            warns.append("%s: mentions %r" % (page, word))
    for tok in BANNED_TOKENS:
        if re.search(tok, h):
            warns.append("%s: mentions %s" % (page, tok))
    for shelf in SHELVES:
        if shelf in h:
            fails.append("%s: links back to a retired shelf (%s)" % (page, shelf))

    print("  %-14s title %2d  desc %3d  h1 %d  refs %2d  %s"
          % (page, len(title or ""), len(desc or ""), len(h1s), len(refs), robots))

# 2 · uniqueness
dupe_t = [t for t in set(titles.values()) if list(titles.values()).count(t) > 1]
dupe_d = [d for d in set(descs.values()) if list(descs.values()).count(d) > 1]
check(not dupe_t, "duplicate titles: %s" % dupe_t)
check(not dupe_d, "duplicate descriptions: %s" % dupe_d)

# 4 · link targets
print("\nlink targets")
missing = []
for page, refs in all_refs.items():
    for r in sorted(refs):
        target = os.path.normpath(os.path.join(SITE, r.split("?")[0]))
        if not os.path.exists(target):
            missing.append("%s -> %s" % (page, r))
check(not missing, "broken internal references:\n    " + "\n    ".join(missing))
print("  checked %d distinct references, %d missing" % (len(set().union(*all_refs.values())), len(missing)))

# 7 · sitemap
print("\nsitemap")
try:
    root = ET.fromstring(read("sitemap.xml"))
    urls = [e.text for e in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    check(len(urls) >= 3, "sitemap has %d urls" % len(urls))
    for u in urls:
        rel = urllib.parse.urlparse(u).path.strip("/")   # "" for the site root
        tail = rel if rel else "index.html"
        check(os.path.exists(os.path.join(SITE, tail)),
              "sitemap lists %s which is not a page" % u)
    print("  %d urls: %s" % (len(urls), ", ".join(urls)))
except Exception as exc:  # noqa: BLE001
    fails.append("sitemap.xml does not parse: %s" % exc)

rb = read("robots.txt")
check("Sitemap: https://" in rb, "robots.txt has no absolute sitemap line")
print("  robots.txt: %d bytes, sitemap line present: %s" % (len(rb), "Sitemap: https://" in rb))

# 8 · og card
print("\nog card")
try:
    from PIL import Image
    img = Image.open(os.path.join(SITE, "assets", "img", "og.png")).convert("RGB")
    w, hgt = img.size
    check((w, hgt) == (1200, 630), "og.png is %dx%d, expected 1200x630" % (w, hgt))
    px = list(img.getdata())
    lum = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in px]
    spread = max(lum) - min(lum)
    mean = sum(lum) / len(lum)
    bright = sum(1 for v in lum if v > 200) / float(len(lum))
    check(spread > 60, "og.png looks blank (luminance spread %.0f)" % spread)
    check(max(lum) > 200, "og.png has no bright text (peak luminance %.0f)" % max(lum))
    check(0.005 < bright < 0.25,
          "og.png bright-pixel share is %.1f%% (expected text, roughly 1-15%%)" % (bright * 100))
    print("  %dx%d, spread %.0f, mean %.0f, peak %.0f, bright pixels %.1f%%"
          % (w, hgt, spread, mean, max(lum), bright * 100))
except ImportError:
    warns.append("Pillow not available: og.png not measured")

# summary
print("\n%s" % ("-" * 62))
if warns:
    print("warnings (%d)" % len(warns))
    for w in warns:
        print("  ~ %s" % w)
if fails:
    print("FAILURES (%d)" % len(fails))
    for f in fails:
        print("  ! %s" % f)
    sys.exit(1)
print("all checks passed")
