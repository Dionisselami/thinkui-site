# ThinkUI — product site

The marketing site for the ThinkUI MCP server: landing page, pricing, quickstart,
sign in, sign up, terms, privacy, 404.

It is a **static site**. No framework, no build step beyond one Python script that
stamps the domain into the pages. Upload the folder to any static host, or serve it
from the same server that runs the MCP server.

---

## 1. Build it

```bash
python src/build.py                       # uses SITE_URL inside the script
python src/build.py --url https://your-domain.com
```

`src/build.py` is the **only** place the domain lives. It writes:

| output | what it is |
|---|---|
| `index.html`, `pricing.html`, `docs.html`, `login.html`, `signup.html`, `404.html`, `terms.html`, `privacy.html` | the pages |
| `sitemap.xml` | one `<url>` per indexable page, with `lastmod` |
| `robots.txt` | allows crawling, blocks `/api/`, `/login`, `/signup`, points at the sitemap |
| `assets/img/og.png` | the 1200×630 social card, drawn by the script |

Pages are authored in `src/` as templates and stamped into the folder root. The nav
and footer live in `src/_nav.html` and `src/_footer.html` and are spliced in with
`{{>nav}}` / `{{>footer}}`, so there is one copy of each. What still needs to be set
in `src/build.py`:

```python
SITE_URL      = "https://thinkui.xyz"        # the domain the site is served from
CONTACT_EMAIL = "support@thinkui.xyz"        # address shown on the legal pages
```

If a page still contains a `{{...}}` token the build **fails loudly** rather than
shipping it.

## 2. Preview it

```bash
python serve.py                 # http://127.0.0.1:8899
python serve.py --lan           # also reachable from your phone
```

Routes: `/` `/pricing` `/docs` `/login` `/signup` `/terms` `/privacy`, plus the old
addresses (`/screens`, `/materials`, `/mcp`, …) which redirect rather than 404.

## 3. Deploy it

Upload everything except `src/`, `__pycache__/`, `serve.py` and `*.bat`:

```
index.html  pricing.html  docs.html  login.html  signup.html  404.html
terms.html  privacy.html  sitemap.xml  robots.txt  site.webmanifest
assets/     (css/site.css, js/app.js, img/* — the full icon set and the lockups)
```

For Cloudflare Pages or Netlify the folder is the publish directory and there is
nothing else to configure. Two things worth adding once the host is chosen:

- **404s** — point the host's not-found handler at `404.html` (status 404).
- **Caching** — `assets/*` can be cached hard; the HTML should not be, so a copy
  edit goes live on the next deploy without a purge.

## 3b. The brand

The logo is **outlines, not live text**, so it renders the same on every machine and
never waits on a webfont. It is built once and then only read:

```bash
cd brand
uv run --with fonttools --with uharfbuzz python build_identity.py   # outlines + lockups -> assets/img/
python render_icons.py                                              # PNGs, .ico, apple icon, manifest
python preview_identity.py                                          # identity-preview.png (for eyeballing)
python verify_identity.py                                           # the lockups as they land in the site
python ../src/build.py                                              # stamps the lockups into every page
```

`brand/build_identity.py` pulls Inter's own outlines (instanced at wght 600 / opsz 30,
shaped through HarfBuzz so kerning and advances are the font's), places everything from
**measured ink bounds** — cap height 1506 units, stem 253 — and writes
`src/identity.json`, which the social card reads so the card's mark cannot drift from
the SVG.

The mark is *Distilled*: three left-aligned bars inside a 64-unit grid, in two cuts.

| cut | used for | why |
|---|---|---|
| `t=6.5` | app icon, favicon, standalone mark | mass is what keeps 16px legible |
| `t=5.4` | the lockup, ahead of the wordmark | a full-mass mark beside text reads as a different typeface |

The header lockup is classed `.brand__logo`; `assets/css/site.css` sizes it (26px) and
nothing else about it should be styled per page.

**Changing the brand:** edit the constants at the top of `brand/build_identity.py` and
re-run the four commands. Do not hand-edit `assets/img/*.svg` — the next build
overwrites it.

**Typefaces:** Archivo (display) and Public Sans (body), both OFL 1.1, both served from
our own origin as variable woff2 — `assets/fonts/`, with each notice beside it. Nothing
on a page loads a font from a third party. Inter is still used to draw the wordmark's
outlines at build time: it ships only inside `brand/` (never deployed) and as outlines
inside the logo, with its notice at `brand/Inter-OFL.txt`. Mono is the system stack; we
ship no mono.

## 4. What still has to be wired

Nothing below is blocked — the UI is finished and the pages render; these are the
lines that connect it to a running service.

| # | What | Where | Notes |
|---|---|---|---|
| 1 | Sign-in and sign-up endpoints | `src/login.html`, `src/signup.html` | Both forms post to `/api/auth/sign-in` and `/api/auth/sign-up`; the OAuth buttons point at `/api/auth/google`, `/api/auth/github`, and the reset link at `/api/auth/reset`. Change the paths to whatever your auth service exposes. |
| 2 | Your prices and checkout | `src/index.html`, `src/pricing.html` | Plans are `$0 / $19 / $49`. The plan buttons currently point at `signup.html`; swap them for a checkout URL when billing is live. |
| 3 | Contact address | `src/build.py` → `CONTACT_EMAIL` | Appears on the terms and privacy pages. |
| 4 | Legal review | `src/terms.html`, `src/privacy.html` | Written as a plain-language starting point that matches what the product actually does. Have someone qualified read them before you take money. |
| 5 | The npm package | `src/docs.html` | The docs show `npx -y thinkui-mcp`. Until that package is published, the docs also give the from-a-checkout form (`command: python`, `args: ["…/server.py"]`), which is what runs today. |

## 5. Verify it

```bash
python src/audit.py          # crawler's view: titles, canonicals, JSON-LD, links, sitemap, og.png
python src/verify_live.py    # drives a real Chrome: animations, reveals, fonts, header, no console errors
```

`audit.py` exits non-zero if a description is the wrong length, two pages share a
title, an internal link points at a file that does not exist, a token survived, the
product surface starts talking about licensing, the sitemap is malformed, or the
social card is blank. `verify_live.py` reuses the geometry probe's Chrome launcher
and additionally reloads the landing page **with JavaScript disabled** to prove the
content is readable without it.

For layout, use the shared probe:

```bash
python "…/rendered-ui-verification/scripts/ui_probe.py" http://127.0.0.1:8899/ --widths 1440,1100,900,390
```

## 6. Design notes

- **Light product surface, dark canvas for the hero, the closing call to action and
  the footer.** One accent (`#5b5bd6` → `#22b8c8`), used where it acts: the primary
  button, the highlighted plan, links.
- **Background animation is CSS only** — three drifting blurred fields, a masked
  grid, a slow light sweep and an SVG grain. No canvas, no library, no main-thread
  work. Everything stops under `prefers-reduced-motion: reduce`.
- **Content never depends on JavaScript.** Reveal animations only ever hide an
  element *after* the script has confirmed it can reveal it again: with JS off the
  page is fully visible, and `verify_live.py` checks that on every run.
- **No licence talk on the product surface.** Provenance stays in the tool output;
  the site sells the server.

The earlier corpus-browsing site (screens, materials, elements, icons, sources) is
preserved at `C:\Users\use\appvault-corpus-site-backup`.
