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
    # Discovery cluster: one page per query a buyer actually types. Each links back to
    # /pricing, /docs and to its siblings, and the footer links all of them from every
    # page, so a crawler that has already indexed the homepage reaches them on its next
    # visit instead of waiting for them to be found by accident.
    ("mcp-server-for-ui-design.html",  "MCP server for UI design: real screens in your agent",  True),
    ("claude-code-ui-design.html",     "Claude Code UI design: real references over MCP",       True),
    ("cursor-ui-design.html",          "Cursor UI design: give the agent real screens",         True),
    ("figma-mcp-alternative.html",     "Figma MCP alternative: references beyond your files",   True),
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


# Icons live under assets/img/app-icons/ so a changed mark can ship at a new URL: these files
# are served immutable for 30 days, and reusing the old paths kept the previous tile in
# browsers and at the edge.
ICONS = """<link rel="icon" href="assets/img/app-icons/favicon.ico" sizes="any">
<link rel="icon" href="assets/img/app-icons/favicon.svg" type="image/svg+xml">
<link rel="icon" type="image/png" sizes="32x32" href="assets/img/app-icons/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="assets/img/app-icons/favicon-16.png">
<link rel="apple-touch-icon" href="assets/img/app-icons/apple-touch-icon.png">
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

# The library's own taxonomy, used by the chips above the wall. One tag per screen,
# assigned from what the screen demonstrates rather than from the app it came from —
# the question a visitor arrives with is "what does a paywall look like", not "what
# did Trello ship". Order here is the order the chips appear in.
WALL_TAGS = [
    ("product",  "Product & work"),
    ("devdata",  "Developer & data"),
    ("life",     "Life & travel"),
    ("commerce", "Commerce & marketing"),
    ("ai",       "AI & design"),
]


def wall_tag(flow: str) -> str:
    """The kind of screen this is, from the flow name.

    Order matters: a "dashboard empty state" is an empty state first, and
    "All notifications inbox" belongs with settings rather than dashboards.
    The fallback is honest — a landing page is what is left.
    """
    f = (flow or "").lower()
    for key, words in (
        ("product",  ("productivity", "project management", "notes", "collaboration", "hr", "finance")),
        ("devdata",  ("developer", "infrastructure", "data & databases", "security", "analytics")),
        ("commerce", ("commerce", "marketing", "cms")),
        ("ai",       ("ai", "design tools", "media")),
        ("life",     ("travel", "health", "social", "education", "other")),
    ):
        if any(w in f for w in words):
            return key
    return "life"


def _wall_rows() -> list:
    try:
        return json.load(open(WALL_JSON, encoding="utf-8"))
    except Exception:
        return []


def screen_wall() -> str:
    """The library itself, as the page's main object.

    A product whose value is visual should not open with a paragraph about itself.
    Every card is a real screen from the corpus, credited with the app it came from
    and the day it was captured - the same thing the server returns. The tag is the
    filter the chips read; it is data, not decoration.
    """
    rows = _wall_rows()
    esc = lambda v: htmllib.escape(str(v), quote=True)
    out = []
    for r in rows:
        tag = r.get("tag") or wall_tag(r.get("flow", ""))
        out.append(
            '<figure class="wall__card" data-tags="%s">'
            '<img src="%s" alt="%s, %s screen" width="%d" height="%d" loading="lazy" decoding="async">'
            '<figcaption class="wall__meta"><b>%s</b><span>%s &middot; %s</span></figcaption>'
            '</figure>' % (esc(tag), esc(r["file"]), esc(r["app"]), esc(r["flow"]),
                           r.get("w", 460), r.get("h", 900),
                           esc(r["app"]), esc(r["flow"]),
                           ("captured " + esc(r["captured"])) if r.get("captured") else esc(r.get("licence", ""))))
    return chr(10).join(out)


def wall_chips() -> str:
    """Filter chips with the count each one actually holds."""
    rows = _wall_rows()
    if not rows:
        return ""
    from collections import Counter
    counts = Counter(r.get("tag") or wall_tag(r.get("flow", "")) for r in rows)
    out = ['<button class="chip is-active" type="button" data-filter="all">All <span>%d</span></button>' % len(rows)]
    labels = dict(WALL_TAGS)
    for key, n in counts.most_common():
        if n:
            out.append('<button class="chip" type="button" data-filter="%s">%s <span>%d</span></button>'
                       % (key, labels.get(key, key.title()), n))
    return chr(10).join(out)


# The hero's floating library. Each slot is (left %, top %, width px, rotate deg,
# opacity, blur px, float x, float y, duration s, delay ms). Two of the tiles sit
# behind the headline and are blurred on purpose: the type must stay the first read.
HERO_SLOTS = [
    (1.5,  24, 268,  -8, .82, 0, 14, -10, 15,    0),
    (6.0,  62, 224,   5, .80, 0, -12, -14, 18, 700),
    (-2.0,  8, 208,  11, .45, 2, 10,  12, 21, 1400),
    (77.0, 22, 268,   7, .78, 0, -14, -8, 17, 300),
    (70.5, 66, 228,  -6, .80, 0, 12, -12, 19, 950),
    (86.0,  4, 200, -11, .42, 2, -10, 10, 22, 1600),
    (19.0, 80, 188,  -4, .48, 1, 8, -10, 20, 450),
    (64.0, 84, 188,   5, .48, 1, -8, -9, 23, 1100),
    (30.0,  1, 168, -12, .28, 3, 6,  10, 24, 800),
    (57.0,  2, 168,  12, .28, 3, -6, 10, 25, 1300),
]


def hero_tiles() -> str:
    """Real screens tilted around the headline, as the hero's depth of field."""
    rows = _wall_rows()
    if not rows:
        return ""
    order = [0, 10, 4, 12, 8, 16, 2, 20, 6, 22, 14, 18]
    esc = lambda v: htmllib.escape(str(v), quote=True)
    out = []
    for i, (x, y, w, r, o, b, fx, fy, dur, dl) in enumerate(HERO_SLOTS):
        row = rows[order[i % len(order)] % len(rows)]
        out.append(
            '<div class="tile" aria-hidden="true" style="--x:%s%%;--y:%s%%;--w:%dpx;--r:%sdeg;'
            '--o:%s;--b:%dpx;--fx:%dpx;--fy:%dpx;--dur:%ss;--dl:%dms;--d:%.2f">'
            '<span class="tile__bar"><i></i><i></i><i></i></span>'
            '<img src="%s" alt="" width="640" height="400" loading="eager" decoding="async">'
            '</div>' % (x, y, w, r, o, b, fx, fy, dur, dl, w / 240.0, esc(row["file"])))
    return chr(10).join(out)


def wall_count() -> str:
    rows = _wall_rows()
    apps = len({r.get("app") for r in rows})
    return "%d screens &middot; %d products" % (len(rows), apps)



def _corpus_stats():
    """The local corpus, if it is importable at build time (else None)."""
    mcp_dir = os.environ.get("THINKUI_MCP_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(HERE)), "appvault-mcp")
    try:
        if mcp_dir not in sys.path:
            sys.path.insert(0, mcp_dir)
        import corpus as thinkui_corpus  # noqa: PLC0415
        return thinkui_corpus.get_corpus().stats()
    except Exception as exc:  # noqa: BLE001 — the site must build without the corpus
        print("[build] corpus unavailable (%s: %s)" % (type(exc).__name__, exc))
        return None


def corpus_stats_text() -> str:
    """Quote the server's own corpus_stats(), generated so the page cannot go stale.

    The examples page used to carry a hand-pasted sample from when the corpus held
    650 references; by the time it was 1,639 that page was teaching readers a number
    the server would contradict. Import the server, call the tool, wrap for width.
    """
    import textwrap
    mcp_dir = os.environ.get("THINKUI_MCP_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(HERE)), "appvault-mcp")
    try:
        if mcp_dir not in sys.path:
            sys.path.insert(0, mcp_dir)
        import server as thinkui_server  # noqa: PLC0415 — optional build-time dependency
        text = thinkui_server.corpus_stats()
    except Exception as exc:  # noqa: BLE001 — the site must still build without the corpus
        print("[build] corpus_stats() unavailable (%s: %s)" % (type(exc).__name__, exc))
        return "corpus_stats() — run it against your ThinkUI key for live counts."
    return "\n".join(textwrap.wrap(" ".join(text.split()), 78))


def tokens(page: str) -> dict:
    stats = _corpus_stats() or {}
    refs = stats.get("references")
    brief = "real products"
    if stats.get("flows") and stats.get("categories"):
        brief = "%s flows and %s categories" % (stats["flows"], stats["categories"])
    return {
        "SITE_URL": SITE_URL.rstrip("/"),
        "YEAR": str(dt.date.today().year),
        "CONTACT_EMAIL": CONTACT_EMAIL,
        "CORPUS_STATS": corpus_stats_text(),
        "CORPUS_STATS_BRIEF": brief,
        "REFERENCE_COUNT": format(refs, ",") if refs else "thousands of",
        "REFERENCE_COUNT_NUM": str(refs) if refs else "0",
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
        "WALL_CHIPS": wall_chips(),
        "WALL_COUNT": wall_count(),
        "HERO_TILES": hero_tiles(),
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
        text = render(page, open(src, encoding="utf-8").read())
        # Every document gets the page-view beacon, here rather than in each template: a
        # head that misses it is invisible in a dashboard with no data in it. It posts to
        # our own /api/pv (no cookie, no third-party request) so it is inert until the
        # service has a PostHog key.
        if "</body>" in text and "analytics.js" not in text:
            text = text.replace("</body>", '<script src="assets/js/analytics.js" defer></script>\n</body>')
        text = clean_links(version_assets(text))
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
        priority = "1.0" if page == "index.html" else (
            "0.9" if page in ("pricing.html", "mcp-server-for-ui-design.html",
                              "claude-code-ui-design.html", "cursor-ui-design.html",
                              "figma-mcp-alternative.html") else "0.8")
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


def build_llms():
    """llms.txt — the briefing an assistant quotes verbatim.

    Not a ranking factor, but it is read by answer engines, so every line has to be
    something we would stand behind on the pricing page. The counts come from the
    corpus at build time rather than being typed here, and the price table carries the
    same numbers checkout charges. Sweep this file in the same commit as any price or
    plan change.
    """
    url = SITE_URL.rstrip("/")
    s = _corpus_stats() or {}
    def n(k):
        v = s.get(k)
        return format(v, ",") if isinstance(v, int) else "a growing library of"
    refs = n("references")
    imgs = n("images")
    lic = n("images_licensed")
    els = n("ui_elements")
    icons = n("animated_icons")
    mats = n("materials")
    flows = n("flows")
    cats = n("categories")

    text = """# ThinkUI

> ThinkUI is a hosted MCP (Model Context Protocol) server that gives coding agents
> interface references from real, shipped products: screens, flows, ready-made
> components, animated icons and typefaces. It is evidence for design decisions, not
> a component library to copy.

## Connect

- Endpoint: {url}/mcp (streamable HTTP)
- Auth: two ways. OAuth 2.1 for connectors that sign users in (ChatGPT, Claude web,
  Cursor): discovery at {url}/.well-known/oauth-protected-resource, authorization
  server at {url}/.well-known/oauth-authorization-server, dynamic client
  registration, authorization code + PKCE. Or an API key sent as
  `Authorization: Bearer <key>`, issued at {url}/account after signing up at {url}/signup.
- Clients: ChatGPT connectors and Claude web connectors (OAuth), Claude Code, Claude
  Desktop, Cursor, VS Code with Copilot (agent mode), Windsurf, Zed, Codex, and any
  client that supports remote MCP servers.
- Skill: `npx skills add {url} --skill thinkui -y` installs the companion SKILL.md
  that tells an agent when to call the tools.

## Tools

| tool | answers | returns |
|---|---|---|
| find_ui_references | how a screen, flow or pattern is actually designed | screens and flows with the app they came from, the patterns used, the components involved |
| find_ui_elements | what a component should look like | the component's markup and stylesheet, ready to paste (MIT) |
| find_animated_icons | which animated icon fits an action | working animated SVG, no runtime, no icon font (MIT) |
| find_ui_materials | which typeface, icon set or design system to use for a role | candidates with maintenance state and source |
| corpus_stats | what the server holds | counts by category, so an empty result is explained rather than silent |

## Prices (USD)

| plan | price | billing | what the buyer gets |
|---|---|---|---|
| Starter | $9.99 | monthly, cancel anytime | unlimited tool calls, all five tools, components/icons/materials, email support |
| Pro | $19.99 | monthly, cancel anytime | everything in Starter plus priority support and priority when new sources are added |
| Lifetime | $190 | one-time, never renews | everything in Pro, permanent access |

The library and the tools are identical on every plan; only support and seats differ.
Prices are quoted from {url}/pricing.

## Library (generated at build time)

- {refs} interface references across {flows} flows and {cats} categories
- {imgs} screenshots across products; {lic} are permissively licensed, the rest are
  research and comparison references that may not be republished
- {els} ready-made UI elements (HTML + CSS, MIT)
- {icons} animated icons in 6 sets (SVG, MIT)
- {mats} materials: typefaces, icon sets and design systems (open licences)

## Key pages

- {url}/ — what it is and what the tools return
- {url}/pricing — plans, billing and refunds
- {url}/docs — connecting each client, in one config block
- {url}/examples — real tool responses
- {url}/mcp-server-for-ui-design — what a UI-reference MCP server is, and how it
  differs from the Figma MCP server
- {url}/claude-code-ui-design — Claude Code setup (server + skill)
- {url}/cursor-ui-design — Cursor setup
- {url}/figma-mcp-alternative — comparison with the Figma MCP server

## What it does not do

- It does not draw or generate final interfaces. The agent writes the code; ThinkUI
  returns the evidence and the assets.
- It does not grant rights it does not hold. Screenshots keep their own licences and
  study-only screens are marked "do not ship or republish" in the result.
- It does not approximate an answer. A query the library cannot answer returns empty
  and says what the library does hold.

## Contact

support@thinkui.xyz
""".format(url=url, refs=refs, imgs=imgs, lic=lic, els=els, icons=icons,
           mats=mats, flows=flows, cats=cats)
    open(os.path.join(SITE, "llms.txt"), "w", encoding="utf-8", newline="\n").write(text)
    return len(text.splitlines())


# IndexNow: Bing and Yandex accept URLs without any account, which is the only instant
# submission path that exists for a site nobody has registered anywhere yet. The key is
# public by design — it proves control of the host by being served at /<key>.txt.
INDEXNOW_KEY = "9c41f7b2d8a34e6f0b5a91c73e2d6084"


def build_indexnow():
    path = os.path.join(SITE, INDEXNOW_KEY + ".txt")
    open(path, "w", encoding="utf-8", newline="\n").write(INDEXNOW_KEY + "\n")
    return INDEXNOW_KEY


def build_wellknown_mcp():
    """/.well-known/mcp.json — the proof-of-control file open directories look for.

    mcpub.dev (and any directory that adopts the same check) refuses a submission
    without it; the content itself is a descriptor, so make it a true one rather than
    an empty object: an agent that reads it should get the endpoint, the transport and
    where the documentation lives.
    """
    url = SITE_URL.rstrip("/")
    doc = {
        "name": "ThinkUI",
        "description": ("UI references for coding agents: real screens, flows, ready-made "
                        "components, fonts and animated icons."),
        "endpoint": url + "/mcp",
        "transport": "streamable-http",
        "authentication": "oauth2-or-api-key",
        "oauth": {
            "protected_resource_metadata": url + "/.well-known/oauth-protected-resource",
            "authorization_server_metadata": url + "/.well-known/oauth-authorization-server",
        },
        "website": url,
        "documentation": url + "/docs",
        "pricing": url + "/pricing",
        "registry": "io.github.Dionisselami/thinkui",
        "repository": "https://github.com/Dionisselami/thinkui",
    }
    path = os.path.join(SITE, ".well-known", "mcp.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    return path


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

    # The mark: a cream tile holding the cloud drawn by brand/build_mark.py. Same six
    # lobes and one thought, so the social card and the favicon cannot disagree.
    tile, tx, ty = 52, 84, 76
    lobes = [(25, 28, 12.0), (39, 25, 9.0), (46, 33, 7.0), (38, 40, 9.0), (25, 40, 9.5), (33, 33, 10.5)]
    dot = (12.2, 51.6, 4.6)
    stretch = lambda cx: (cx - 32) * 1.1 + 32
    left = min([stretch(cx) - r for cx, _, r in lobes] + [stretch(dot[0]) - dot[2]])
    right = max([stretch(cx) + r for cx, _, r in lobes] + [stretch(dot[0]) + dot[2]])
    top = min([cy - r for _, cy, r in lobes] + [dot[1] - dot[2]])
    bot = max([cy + r for _, cy, r in lobes] + [dot[1] + dot[2]])
    d.rounded_rectangle([(tx, ty), (tx + tile, ty + tile)],
                        radius=tile * 15 / 64, fill=hx("#f0dcc8") + (255,))
    s = (tile * 0.76) / max(right - left, bot - top)
    ox = tx + (tile - (right - left) * s) / 2 - left * s
    oy = ty + (tile - (bot - top) * s) / 2 - top * s
    ink = hx("#141414") + (255,)
    for cx, cy, r in lobes + [dot]:
        x = stretch(cx)
        d.ellipse([(ox + (x - r) * s, oy + (cy - r) * s),
                   (ox + (x + r) * s, oy + (cy + r) * s)], fill=ink)
    d.text((162, 86), ident["word"], font=font(38, "B"), fill=(255, 255, 255, 245))
    d.text((162, 128), "MCP server", font=font(20), fill=hx(ident["on_ink_soft"]) + (255,))

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
    print("  llms.txt       %d lines" % build_llms())
    print("  indexnow key   /%s.txt" % build_indexnow())
    build_wellknown_mcp()
    print("  well-known     /.well-known/mcp.json")
    build_og()
    return 0


if __name__ == "__main__":
    sys.exit(main())
