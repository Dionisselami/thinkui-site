#!/usr/bin/env python3
"""Rewrite the site's library numbers from corpus_stats().

    python site_stats.py <site_dir> "<corpus_stats text>"

Every number the site states about the corpus comes from the server's own corpus_stats
line, so a landing page can never claim more (or less) than the MCP returns. Run it as
the last build step. It fails loudly if a known claim is no longer found, rather than
silently leaving a stale number behind.
"""
import re, sys, pathlib

def parse(t):
    g = lambda p: int(re.search(p, t).group(1))
    return {
        "refs": g(r"(\d+) references"), "flows": g(r"across (\d+) flows"),
        "cats": g(r"(\d+) categories"), "materials": g(r"(\d+) materials"),
        "icons": g(r"(\d+) animated icons"), "sets": g(r"across (\d+) sets"),
        "elements": g(r"(\d+) ready-made"), "shots": g(r"(\d+) screenshots"),
        "products": g(r"across (\d+) products"), "permissive": g(r"(\d+) permissively"),
        "research": g(r"(\d+) shown as research"), "schematic": g(r"(\d+) schematic"),
        "component": g(r"component=(\d+)"), "flow": g(r"flow=(\d+)"), "screen": g(r"screen=(\d+)"),
    }

def c(n):
    return "{:,}".format(n)

def wrap(text, width=72):
    out, line = [], ""
    for w in text.split(" "):
        if line and len(line) + 1 + len(w) > width:
            out.append(line); line = w
        else:
            line = (line + " " + w) if line else w
    out.append(line)
    return "\n".join(out)

def main(site, stats_text):
    s = parse(stats_text)
    N = r"[\d,]+"
    rules = [  # (files, pattern, replacement, required)
        (["index.html"], r'data-count="\d+">%s</b><span>real screenshots' % N,
         'data-count="%d">%s</b><span>real screenshots' % (s["shots"], c(s["shots"])), True),
        (["index.html"], r'data-count="\d+">%s</b><span>products covered' % N,
         'data-count="%d">%s</b><span>products covered' % (s["products"], c(s["products"])), True),
        (["index.html"], r'data-count="\d+">%s</b><span>ready-made components' % N,
         'data-count="%d">%s</b><span>ready-made components' % (s["elements"], c(s["elements"])), True),
        (["index.html"], r'data-count="\d+">%s</b><span>animated icons' % N,
         'data-count="%d">%s</b><span>animated icons' % (s["icons"], c(s["icons"])), True),
        (["index.html"], r'data-count="\d+">%s</b><span>written design references' % N,
         'data-count="%d">%s</b><span>written design references' % (s["refs"], c(s["refs"])), True),
        (["index.html"], r'data-count="\d+">%s</b><span>fonts, icon sets and systems' % N,
         'data-count="%d">%s</b><span>fonts, icon sets and systems' % (s["materials"], c(s["materials"])), True),
        (["index.html", "pricing.html"], r"\b%s of %s are permissively" % (N, N),
         "%s of %s are permissively" % (c(s["permissive"]), c(s["shots"])), True),
        (["figma-mcp-alternative.html"], r"<td>%s interface references" % N,
         "<td>%s interface references" % c(s["refs"]), True),
        (["mcp-server-for-ui-design.html"], r"%s references across \d+ flows and \d+ categories" % N,
         "%s references across %d flows and %d categories" % (c(s["refs"]), s["flows"], s["cats"]), True),
        (["skills.html"], r"The server holds %s references" % N,
         "The server holds %s references" % c(s["refs"]), True),
        (["llms.txt"], r"- %s interface references across \d+ flows and \d+ categories" % N,
         "- %s interface references across %d flows and %d categories" % (c(s["refs"]), s["flows"], s["cats"]), True),
        (["llms.txt"], r"- %s screenshots across products; %s are permissively" % (N, N),
         "- %s screenshots across products; %s are permissively" % (c(s["shots"]), c(s["permissive"])), True),
        (["llms.txt"], r"- %s ready-made UI elements" % N, "- %s ready-made UI elements" % c(s["elements"]), True),
        (["llms.txt"], r"- %s animated icons in \d+ sets" % N,
         "- %s animated icons in %d sets" % (c(s["icons"]), s["sets"]), True),
        (["llms.txt"], r"- %s materials:" % N, "- %s materials:" % c(s["materials"]), True),
        (["examples.html"], r"<pre>\d+ references across.*?screen=\d+\.</pre>",
         "<pre>" + wrap(stats_text.strip()) + "</pre>", True),
    ]
    changed = set()
    for files, pat, rep, required in rules:
        for f in files:
            p = pathlib.Path(site) / f
            t = p.read_bytes().decode("utf-8")
            n = len(re.findall(pat, t, flags=re.S))
            if required and n == 0:
                sys.exit("site_stats: claim not found in %s: %s" % (f, pat))
            nl = "\r\n" if "\r\n" in t else "\n"
            r = rep.replace("\n", nl) if nl != "\n" else rep
            t2 = re.sub(pat, lambda m: r, t, flags=re.S)
            if t2 != t:
                p.write_bytes(t2.encode("utf-8")); changed.add(f)
    print("site_stats: %s" % ", ".join(sorted(changed)) if changed else "site_stats: already current")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
