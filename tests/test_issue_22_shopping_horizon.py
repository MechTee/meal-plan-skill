"""Issue #22: later cycles get their own computed quantities; beyond the horizon nothing is invented."""
import datetime as dt, json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M
import render_pages as R

PLAN = M.load(os.path.join(ROOT, "assets", "example_plan.json"))


def stock_item(sh, name):
    run = next(r for r in sh["runs"] if r["kind"] == "stock")
    return next(i for i in run["items"] if i["name"] == name)


class EngineHorizon(unittest.TestCase):
    def test_default_horizon_is_about_a_year(self):
        sh = M.shopping(PLAN)
        self.assertEqual(sh["horizon_cycles"], 13)
        self.assertEqual(len(stock_item(sh, "Oats, fine")["packs_by_cycle"]), 13)
        self.assertEqual(sh["horizon_end"], "2027-10-31")

    def test_issue_sequences(self):
        sh = M.shopping(PLAN)
        self.assertEqual(stock_item(sh, "Oats, fine")["packs_by_cycle"][:6], [5, 4, 5, 4, 5, 4])
        self.assertEqual(stock_item(sh, "Creatine monohydrate")["packs_by_cycle"][:6], [1, 0, 0, 0, 1, 0])

    def test_sequences_are_simulated_not_extrapolated(self):
        long_seq = stock_item(M.shopping(PLAN), "Creatine monohydrate")["packs_by_cycle"]
        short_seq = stock_item(M.shopping(PLAN, cycles=6), "Creatine monohydrate")["packs_by_cycle"]
        self.assertEqual(long_seq[:6], short_seq)

    def test_horizon_is_configurable(self):
        p = json.loads(json.dumps(PLAN))
        p["shopping"]["horizon_cycles"] = 8
        self.assertEqual(M.shopping(p)["horizon_cycles"], 8)


try:
    from playwright.sync_api import sync_playwright
    HAVE = True
except Exception:
    HAVE = False


@unittest.skipUnless(HAVE, "Playwright not installed")
class PageHorizon(unittest.TestCase):
    def page_at(self, when):
        tmp = tempfile.mkdtemp()
        sys.argv = ["render_pages.py", os.path.join(ROOT, "assets", "example_plan.json"), tmp]
        R.main()
        self.pw = sync_playwright().start()
        try:
            self.browser = self.pw.chromium.launch()
        except Exception as e:
            self.pw.stop()
            self.skipTest(f"Chromium not available: {e}")
        page = self.browser.new_page()
        page.clock.set_fixed_time(when)
        page.goto("file://" + os.path.join(tmp, "shopping-list.html"))
        return page

    def tearDown(self):
        if hasattr(self, "browser"):
            self.browser.close()
            self.pw.stop()

    def qty(self, page, name):
        page.click("text=Stock-up")
        return page.locator("label.row", has_text=name).first.locator(".qty").inner_text().split("\n")[0]

    def test_cycle_five_uses_its_own_quantities(self):
        # cycle 5 starts 4 × 28 days after the first run (31 Oct 2026) → 20 Feb 2027
        page = self.page_at(dt.datetime(2027, 2, 21, 12, tzinfo=dt.timezone.utc))
        self.assertEqual(page.evaluate("state.cycle"), 5)
        self.assertEqual(self.qty(page, "Oats, fine"), "5 ×")
        self.assertEqual(self.qty(page, "Creatine monohydrate"), "1 ×")     # cycle 4 would have said skip

    def test_beyond_the_horizon_shows_no_quantities(self):
        page = self.page_at(dt.datetime(2028, 3, 1, 12, tzinfo=dt.timezone.utc))
        self.assertGreater(page.evaluate("state.cycle"), 13)
        self.assertIn("covers 13 cycles", page.inner_text("#runs"))
        self.assertEqual(page.locator("input[type=checkbox]").count(), 0)
        self.assertEqual(page.locator("#cycles button").count(), 13)


if __name__ == "__main__":
    unittest.main()
