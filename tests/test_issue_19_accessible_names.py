"""Issue #19: every checkbox is named by its own visible text, not a generic "Done" / "Got it"."""
import json, os, re, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import render_pages as R

try:
    from playwright.sync_api import sync_playwright
    HAVE = True
except Exception:
    HAVE = False


def render(tmp):
    sys.argv = ["render_pages.py", os.path.join(ROOT, "assets", "example_plan.json"), tmp]
    R.main()


def checkbox_names(page):
    snap = page.locator("body").aria_snapshot()
    return re.findall(r'- checkbox "([^"]*)"', snap)


class Static(unittest.TestCase):
    def test_no_generic_override_labels(self):
        for name in ("recipe_page.html", "shopping_list.html"):
            with open(os.path.join(ROOT, "assets", name), encoding="utf-8") as f:
                t = f.read()
            self.assertNotIn('aria-label="Done"', t)
            self.assertNotIn('aria-label="Got it"', t)
            self.assertIn("aria-labelledby", t)


@unittest.skipUnless(HAVE, "Playwright not installed")
class Browser(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        render(self.tmp.name)
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

    def open(self, name):
        page = self.browser.new_page()
        page.goto("file://" + os.path.join(self.tmp.name, name))
        return page

    def test_recipe_checkboxes_have_unique_meaningful_names(self):
        page = self.open("dal.html")
        names = checkbox_names(page)
        self.assertGreater(len(names), 10)
        self.assertEqual(len(names), len(set(names)), names)
        self.assertIn("Red lentils, split 300 g", names)
        self.assertTrue(any(n.startswith("Step 1 ") for n in names), names)
        self.assertNotIn("Done", names)
        # native label activation still works: clicking the text toggles the box
        page.get_by_text("Red lentils, split", exact=True).click()
        self.assertTrue(page.get_by_role("checkbox", name="Red lentils, split 300 g").is_checked())

    def test_ticks_saved_before_the_change_still_load(self):
        """Review on PR #41: localStorage written by the previous page version keys ingredients as i<n>:<name>."""
        page = self.open("dal.html")
        page.evaluate("""() => localStorage.setItem('cook:dal',
                                 JSON.stringify({ticks: {'i0:Red lentils, split': true, 's0': true}}))""")
        page.reload()
        self.assertTrue(page.get_by_role("checkbox", name="Red lentils, split 300 g").is_checked())
        self.assertTrue(page.locator("#steps input[type=checkbox]").first.is_checked())
        page.get_by_role("checkbox", name="Red lentils, split 300 g").uncheck()
        saved = page.evaluate("() => JSON.parse(localStorage.getItem('cook:dal')).ticks")
        self.assertIs(saved["i0:Red lentils, split"], False)

    def test_keyboard_moves_through_items(self):
        page = self.open("dal.html")
        first = page.get_by_role("checkbox", name="Red lentils, split 300 g")
        first.focus()
        page.keyboard.press("Space")
        self.assertTrue(first.is_checked())
        page.keyboard.press("Tab")
        focused = page.evaluate("document.activeElement.getAttribute('aria-labelledby')")
        self.assertEqual(focused, "ing-n1 ing-a1")

    def test_shopping_checkboxes_have_unique_meaningful_names(self):
        page = self.open("shopping-list.html")
        page.click("text=All runs")
        page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
        names = checkbox_names(page)
        self.assertGreater(len(names), 20)
        self.assertNotIn("Got it", names)
        self.assertTrue(any(n.startswith("Almonds ") for n in names), names[:10])
        # names are unique within each run (the same item can appear in several runs)
        for details in page.locator("details").all():
            n = re.findall(r'- checkbox "([^"]*)"', details.aria_snapshot())
            self.assertEqual(len(n), len(set(n)), n)


if __name__ == "__main__":
    unittest.main()
