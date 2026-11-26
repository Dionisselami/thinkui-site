#!/usr/bin/env python3
"""Swap the marketing site's offer from "12 free calls, no card" to the 3-day trial.

Every replacement asserts it matched, so a template that drifted stops the run instead
of shipping a half-changed page.
"""
import re
import sys

SRC = "src/"


def edit(path, pairs):
    p = SRC + path
    s = open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            if new and new in s:
                continue            # already applied by an earlier run
            raise SystemExit("%s: missing anchor: %s" % (path, old[:70]))
        s = s.replace(old, new)
    open(p, "w", encoding="utf-8", newline="").write(s)
    print("edited", path)


# ---------------------------------------------------------------- nav
edit("_nav.html", [
    ('<a class="btn btn--primary" href="/signup?plan=free">Try free, no card</a>',
     '<a class="btn btn--primary" href="/signup?plan=starter">Start free trial</a>'),
])

# ---------------------------------------------------------------- index
edit("index.html", [
    ('"description": "12 tool calls in total, no card", "url": "{{SITE_URL}}/signup?plan=free" }',
     '"description": "3-day free trial, card required", "url": "{{SITE_URL}}/signup?plan=starter" }'),
    ('            Try free, no card\n', '            Start 3-day free trial\n'),
    ('<span class="seg">12 tool calls free</span><span class="dot" aria-hidden="true">&middot;</span><span class="seg">no card needed</span>',
     '<span class="seg">3 days free</span><span class="dot" aria-hidden="true">&middot;</span><span class="seg">card required at checkout</span>'),
    ('20% off <span>&middot;</span> <a href="signup.html?plan=free">or try free, no card</a>',
     '20% off <span>&middot;</span> <a href="signup.html?plan=starter">or start the 3-day free trial</a>'),
    ('<a class="btn btn--light btn--lg" href="/signup?plan=free">Try free, no card</a>',
     '<a class="btn btn--light btn--lg" href="/signup?plan=starter">Start 3-day free trial</a>'),
    ('12 free calls, no card. Starter from $7.99/mo.',
     '3-day free trial, card required. Then $7.99/mo.'),
    ('{{>plan_free}}\n', ''),
])

# ---------------------------------------------------------------- pricing
edit("pricing.html", [
    ('Try ThinkUI with 12 free tool calls, no card. Paid plans with unlimited calls: Starter $7.99/mo, Pro $15.99/mo, Lifetime $152 once.',
     'Start a 3-day free trial of ThinkUI, card required at checkout. Unlimited tool calls: Starter $7.99/mo, Pro $15.99/mo, Lifetime $152 once.'),
    ('<p class="lede">12 free tool calls, no card. All four plans use the same five tools and library.</p>',
     '<p class="lede">Every monthly plan starts with a 3-day free trial, card required at checkout. All plans use the same five tools and library.</p>'),
    (' {{>plan_free}}\n', ''),
    ('Scroll sideways to compare all four plans.', 'Scroll sideways to compare all three plans.'),
    ('<div class="answer"><p>Not to try it. A free account gets 12 tool calls in total, on every tool, with no card. After that, Starter is $7.99 a month and Pro is $15.99 — both 20% off, both cancel in one click. Monthly plans open with a 3-day card-required trial: the card is saved and the first charge lands on day 3 &mdash; cancel before then and nothing is charged. Lifetime is $152 once.</p></div>',
     '<div class="answer"><p>Not quite. Starter and Pro open with a 3-day free trial: the card is saved at checkout and the first charge lands on day 3, so you can cancel before then and pay nothing. Starter is $7.99 a month and Pro $15.99, both 20% off and both cancel in one click; Lifetime is $152 once.</p></div>'),
    ('<a class="btn btn--light btn--lg" href="/signup?plan=free">Try free, no card</a>',
     '<a class="btn btn--light btn--lg" href="/signup?plan=starter">Start 3-day free trial</a>'),
    ('Starter and Pro begin with a 3-day free trial: the card is saved at checkout and the first charge lands on day 3 &mdash; cancel before then and nothing is charged. The free allowance is once per person and does not reset. Your key stays the same when you upgrade.',
     'Starter and Pro begin with a 3-day free trial: the card is saved at checkout and the first charge lands on day 3 &mdash; cancel before then and nothing is charged. Your key stays the same when you upgrade.'),
])

# pricing comparison table: drop the Free column (header + first cell of every row)
p = SRC + "pricing.html"
s = open(p, encoding="utf-8").read()
start = s.index('<table class="cmp cmp--record">')
end = s.index("</table>", start)
table = s[start:end]
assert '<th scope="col">Free</th>' in table, "free column header missing"
table = table.replace('<th scope="col">Free</th>', "", 1)
table = re.sub(r'(<tr><th scope="row">[^<]*</th>)<td[^>]*>.*?</td>', r"\1", table)
s = s[:start] + table + s[end:]
open(p, "w", encoding="utf-8", newline="").write(s)
print("pricing table: Free column removed")

# ---------------------------------------------------------------- signup
edit("signup.html", [
    ('Create a ThinkUI account: start free with 12 tool calls and no card, or pick a plan. Starter is $7.99 a month and Pro is $15.99, both 20% off. Lifetime is $152 once.',
     'Create a ThinkUI account and start a 3-day free trial of Starter or Pro, card required at checkout. Starter is $7.99 a month and Pro is $15.99, both 20% off. Lifetime is $152 once.'),
    ('<p>Start free with no card, or pick a paid plan &mdash; Starter and Pro open with a 3-day free trial, card saved at checkout, first charge on day 3.</p>',
     '<p>Pick a plan and start a 3-day free trial &mdash; the card is saved at checkout and the first charge lands on day 3. Cancel before then and nothing is charged.</p>'),
    ('<label class="planpick__opt"><input type="radio" name="plan" value="free" checked> <span class="planpick__name">Free</span> <span class="planpick__meta"><b>12 tool calls</b>no card</span></label>\n          ',
     ''),
    ('<label class="planpick__opt"><input type="radio" name="plan" value="starter"> <span class="planpick__name">Starter</span>',
     '<label class="planpick__opt"><input type="radio" name="plan" value="starter" checked> <span class="planpick__name">Starter</span>'),
    ('Free gets 12 tool calls and needs no card. Starter and Pro open with a 3-day free trial &mdash; card at checkout, first charge on day 3 &mdash; then $7.99 and $15.99 a month, both 20% off. Lifetime is $152 once.',
     'Starter and Pro open with a 3-day free trial &mdash; card at checkout, first charge on day 3, cancel antes then and pay nothing &mdash; then $7.99 and $15.99 a month, both 20% off. Lifetime is $152 once.'),
    ('Free needs no card. Starter and Pro start with a 3-day trial and bill on day 3; cancel any time from your account.',
     'Card required at checkout. The first charge lands on day 3; cancel any time before then and you are not charged.'),
])

# ---------------------------------------------------------------- docs
edit("docs.html", [
    ('Create an account &mdash; start free with 12 tool calls and no card, or pick a plan &mdash; then copy the key',
     'Create an account and start the 3-day free trial (card required at checkout, first charge on day 3) &mdash; then copy the key'),
    ('A free account gets 12 tool calls in total, and they do not reset.',
     'Starter and Pro open with a 3-day free trial; the card is saved at checkout and the first charge lands on day 3.'),
])

print("done")
