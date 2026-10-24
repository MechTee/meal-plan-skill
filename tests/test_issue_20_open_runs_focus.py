"""Issue #20: ticking an item keeps the run open and keeps keyboard focus on that item."""
import datetime as dt, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import render_pages as R

try:
    from playwright.sync_api import sync_playwright
    HAVE = True
except Exception:
    HAVE = False


@unittest.skipUnless(HAVE, "Playwright not installed")
class OpenRunsAndFocus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        sys.argv = ["render_pages.py", os.path.join(ROOT, "assets", "example_plan.json"), self.tmp.name]
        R.main()
        self.pw = sync_playwright().start()
        try:
            self.browser = self.pw.chromium.launch()
        except Exception as e:
            self.pw.stop()
            self.skipTest(f"Chromium not available: {e}")

    def tearDown(self):
        if hasattr(self, "browser"):
            self.browser.close()
            self.pw.stop()
        self.tmp.cleanup()

    def page(self, view):
        page = self.browser.new_page()
        page.clock.set_fixed_time(dt.datetime(2026, 10, 1, 12, tzinfo=dt.timezone.utc))   # before the first run
        page.goto("file://" + os.path.join(self.tmp.name, "shopping-list.html"))
        page.click(f"text={view}")
        return page

    def check_view(self, view):
        page = self.page(view)
        runs = page.locator("details.run")
        target = runs.nth(2)                                   # not the automatically opened next run
        self.assertNotIn("next", target.get_attribute("class"))
        target.locator("summary").click()
        self.assertTrue(target.evaluate("d => d.open"))
        boxes = target.locator("input[type=checkbox]:not(:disabled)")
        first = boxes.nth(0)
        first.focus()
        page.keyboard.press("Space")
        self.assertTrue(first.is_checked())
        self.assertTrue(target.evaluate("d => d.open"), f"{view}: run collapsed after ticking")
        self.assertTrue(first.evaluate("el => el === document.activeElement"), f"{view}: focus lost")
        # consecutive checking with the keyboard
        page.keyboard.press("Tab")
        page.keyboard.press("Space")
        self.assertTrue(boxes.nth(1).is_checked())
        self.assertTrue(target.evaluate("d => d.open"))
        self.assertEqual(target.locator(".prog").inner_text().split("/")[0], "2")
        # the manual open state survives a filter change and back
        page.click("text=Stock-up")
        page.click(f"text={view}")
        self.assertTrue(page.locator("details.run").nth(2).evaluate("d => d.open"))

    def test_all_runs_view(self):
        self.check_view("All runs")

    def test_upcoming_view(self):
        self.check_view("Upcoming")

    def test_clear_ticks_updates_in_place(self):
        page = self.page("All runs")
        run = page.locator("details.run").nth(0)
        box = run.locator("input[type=checkbox]:not(:disabled)").nth(0)
        box.check()
        run.locator("[data-clear]").click()
        self.assertFalse(box.is_checked())
        self.assertTrue(run.evaluate("d => d.open"))
        self.assertTrue(run.locator(".prog").inner_text().startswith("0/"))


if __name__ == "__main__":
    unittest.main()
