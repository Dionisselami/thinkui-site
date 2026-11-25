"""Check the built marketing pages. Run after `python src/build.py`."""
import json
from html import unescape
from pathlib import Path
import re
import unittest

SITE = Path(__file__).resolve().parents[1]
FREE = "/signup?plan=free"
PLANS = ("Free", "Starter", "Pro", "Lifetime")
PAID_PRICES = {"Starter": "7.99", "Pro": "15.99", "Lifetime": "152"}


def page(name):
    return (SITE / (name + ".html")).read_text(encoding="utf-8")


def text(markup):
    return " ".join(unescape(re.sub(r"<[^>]+>", "", markup)).split())


def actions(markup, group):
    block = markup.split(f'<div class="{group}">', 1)[1].split("</div>", 1)[0]
    return [(text(body), href) for href, body in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)]


class PlanPages(unittest.TestCase):
    def test_home_actions_lead_to_free_signup_and_pricing(self):
        home = page("index")
        expected = [("Try free, no card", FREE), ("See pricing", "/pricing")]
        self.assertEqual(actions(home, "hero__actions"), expected)
        self.assertIn(expected[0], actions(home, "nav__cta"))
        self.assertIn(("Sign in", "/login"), actions(home, "nav__cta"))
        self.assertEqual(actions(home, "closing__actions"), expected)
        self.assertIn("12 free calls, no card. Starter from $7.99/mo.", text(home))

    def test_both_plan_grids_start_with_free_and_keep_all_paid_plans(self):
        for name in ("index", "pricing"):
            with self.subTest(page=name):
                html = page(name)
                self.assertEqual(re.findall(r'<span class="plan__name">(.*?)</span>', html), list(PLANS))
                self.assertFalse("Every plan is 20% off" in html, "Free must not be advertised as discounted")
                card = re.search(r'<article class="plan plan--free"[^>]*>(.*?)</article>', html, re.S)
                if not card:
                    self.fail("Missing Free plan card")
                self.assertIn('href="' + FREE + '"', card[1])
                self.assertIn("12 tool calls in total", text(card[1]))
                for plan in PLANS[1:]:
                    self.assertIn('href="/signup?plan=' + plan.lower() + '"', html)

    def test_free_offer_matches_the_paid_offers_and_has_canonical_url(self):
        for name in ("index", "pricing"):
            with self.subTest(page=name):
                actual = {}
                for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page(name), re.S):
                    data = json.loads(block)
                    for entry in data.get("@graph", [data]):
                        for offer in entry.get("offers", []):
                            actual[offer["name"]] = (offer["price"], offer.get("url", ""))
                self.assertEqual({plan: value[0] for plan, value in actual.items()}, {"Free": "0", **PAID_PRICES})
                self.assertTrue(actual["Free"][1].endswith(FREE))

    def test_signup_places_free_first_and_selects_it_by_default(self):
        radios = re.findall(r'<input type="radio" name="plan" value="([a-z]+)"([^>]*)>', page("signup"))
        self.assertEqual([plan for plan, _ in radios], [plan.lower() for plan in PLANS])
        self.assertEqual([plan for plan, attrs in radios if "checked" in attrs.split()], ["free"])

    def test_pricing_comparison_has_a_free_column_and_one_support_row(self):
        pricing = page("pricing")
        heading = re.findall(r'<h1\b[^>]*>(.*?)</h1>', pricing, re.S)
        self.assertEqual([text(h) for h in heading], ["One server. Four plans."])
        table = re.search(r'<table\b[^>]*>(.*?)</table>', pricing, re.S)
        if not table:
            self.fail("Missing comparison table")
        rows = [[text(cell) for cell in re.findall(r'<t[hd]\b[^>]*>(.*?)</t[hd]>', row, re.S)]
                for row in re.findall(r'<tr>(.*?)</tr>', table[1], re.S)]
        self.assertEqual(rows[0], ["Feature", *PLANS])
        self.assertTrue(all(len(row) == len(rows[0]) for row in rows))
        self.assertEqual(sum(row[0] == "Support" for row in rows), 1)
        self.assertEqual(next(row[1] for row in rows if row[0] == "Tool calls"), "12 in total")
        self.assertEqual(next(row[1] for row in rows if row[0] == "Billing"), "None")


if __name__ == "__main__":
    unittest.main()
