"""Issue #23: item and run costs follow the selected cycle's quantities."""
import datetime as dt, json, os, re, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M
import render_pages as R

try:
    from playwright.sync_api import sync_playwright
    HAVE = True
except Exception:
    HAVE = False


def expected(run, cycle):
    total, unpriced = 0.0, 0
    for it in run["items"]:
        seq = it.get("packs_by_cycle") or [it["packs"]]
        p = seq[min(cycle, len(seq)) - 1]
        if p == 0:
            continue
        if p is None or it["price_each"] is None:
            unpriced += 1
        else:
            total += p * it["price_each"]
    return round(total, 2), unpriced


@unittest.skipUnless(HAVE, "Playwright not installed")
class CycleCosts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        sys.argv = ["render_pages.py", os.path.join(ROOT, "assets", "example_plan.json"), self.tmp.name]
        R.main()
        self.sh = M.shopping(M.load(os.path.join(ROOT, "assets", "example_plan.json")))
        self.pw = sync_playwright().start()
        try:
            self.browser = self.pw.chromium.launch()
        except Exception as e:
            self.pw.stop()
            self.skipTest(f"Chromium not available: {e}")
        self.page = self.browser.new_page()
        self.page.clock.set_fixed_time(dt.datetime(2026, 10, 1, 12, tzinfo=dt.timezone.utc))
        self.page.goto("file://" + os.path.join(self.tmp.name, "shopping-list.html"))
        self.page.click("text=All runs")

    def tearDown(self):
        if hasattr(self, "browser"):
            self.browser.close()
            self.pw.stop()
        self.tmp.cleanup()

    def select_cycle(self, c):
        self.page.locator("#cycles button", has_text=re.compile(rf"^{c} ·")).click()

    def run_total(self, idx):
        text = self.page.locator("details.run").nth(idx).locator(".when").inner_text()
        return float(re.search(r"€([\d,]+\.\d\d)", text).group(1).replace(",", ""))

    def test_issue_reproduction_oats_in_cycle_two(self):
        self.select_cycle(2)
        oats = self.page.locator("details.run").nth(0).locator("label.row", has_text="Oats, fine")
        self.assertIn("4 ×", oats.inner_text())
        self.assertIn("€2.76", oats.inner_text())          # 4 × €0.69, not the cycle-1 €3.45

    def test_run_totals_match_engine_for_cycles_one_to_four(self):
        stock_idx = next(i for i, r in enumerate(self.sh["runs"]) if r["kind"] == "stock")
        for c in (1, 2, 3, 4):
            self.select_cycle(c)
            for idx, run in enumerate(self.sh["runs"]):
                total, unpriced = expected(run, c)
                self.assertAlmostEqual(self.run_total(idx), total, places=2, msg=f"cycle {c} run {run['label']}")
        self.select_cycle(2)
        self.assertAlmostEqual(self.run_total(stock_idx), 208.39, places=2)  # the issue's figure

    def test_zero_purchase_items_cost_nothing(self):
        self.select_cycle(2)
        row = self.page.locator("details.run").nth(0).locator("li.skip").first
        self.assertIn("skip", row.inner_text())
        self.assertNotIn("€", row.locator(".note").inner_text())


class MissingPrice(unittest.TestCase):
    def test_template_reports_missing_prices(self):
        with open(os.path.join(ROOT, "assets", "shopping_list.html"), encoding="utf-8") as f:
            t = f.read()
        self.assertIn("price missing", t)
        self.assertIn("without price", t)


if __name__ == "__main__":
    unittest.main()
