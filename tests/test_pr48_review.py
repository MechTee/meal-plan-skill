"""Regression tests for the review on PR #48 (combined fixes).

[P1] folate UL covers methylfolate      → tests/test_issue_6_nutrient_forms.py (SupplementalFolateIncludesMethylfolate)
[P1] total UL unverified with ANY unknown value (engine + workbook)
[P2] workbook Status is never "ok" while a form-specific limit is skipped
[P3] expired shopping list names the setting that extends it
"""
import copy, datetime as dt, os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mealplan as M
import test_issue_3_week_overrides as T3
import test_issue_4_incomplete_totals as T4

HAVE_OFFICE = bool(shutil.which("soffice") or shutil.which("libreoffice"))


def micro(p, key):
    res = M.compute(p)
    return res, next(r for r in res["checks"]["micros"] if r["key"] == key)


class TotalUpperLimitNeedsEveryValue(unittest.TestCase):
    """A small mass can carry a concentrated source: 5 g of 1,005 g (0.5 %) without a vitamin D value used to
    pass as complete, "within UL" and "ok" — and filling in 2,000 µg/100 g puts the day at 120 µg (UL 100)."""

    def test_reviewer_reproduction_is_unverified_not_ok(self):
        res, r = micro(T4.plan(unknown_g=5, known_g=1000, known_per100=2, ul=100), "vitD_ug")
        self.assertAlmostEqual(r["avg"], 20)
        self.assertEqual(r["ul_status"], "UL unverified")
        self.assertNotEqual(r["status"], "ok")
        self.assertIn("UL unverified", r["status"])
        flag = next(f for f in res["checks"]["flags"] if f.startswith("micro vitD_ug"))
        self.assertIn("5 g of food per day has no vitD_ug value", flag)

    def test_filling_the_gap_shows_why(self):
        _, r = micro(T4.plan(unknown_g=5, known_g=1000, known_per100=2, ul=100, unknown_value=2000), "vitD_ug")
        self.assertEqual(r["avg"], 120)
        self.assertTrue(r["status"].startswith("ABOVE UL"))

    def test_share_below_display_rounding_still_unverified(self):
        # 0.5 g of 1,000.5 g = 0.05 %: mshare drops it (≤ 0.1 %), the limit check must not
        res, r = micro(T4.plan(unknown_g=0.5, known_g=1000, known_per100=2, ul=100), "vitD_ug")
        self.assertEqual(r["missing_share"], 0)
        self.assertEqual(r["ul_status"], "UL unverified")
        self.assertNotEqual(r["status"], "ok")

    def test_complete_data_is_still_ok(self):
        _, r = micro(T4.plan(unknown_g=5, known_g=1000, known_per100=2, ul=100, unknown_value=0), "vitD_ug")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["ul_status"], "within UL")

    def test_minimum_side_without_ul_keeps_its_tolerance(self):
        # no upper limit → nothing to verify; a 0.5 % gap is still worded as complete on the minimum side
        res, r = micro(T4.plan(unknown_g=5, known_g=1000, known_per100=2, ul=None), "vitD_ug")
        self.assertEqual(r["status"], "ok")
        self.assertFalse(any(f.startswith("micro vitD_ug") for f in res["checks"]["flags"]))


def magnesium_plan(supplement=1000):
    """Reviewer's P2 reproduction: complete food magnesium 100 mg/day, a form-specific limit only."""
    p = T3.minimal_plan()
    p["ingredients"]["food"]["per100"]["magnesium_mg"] = 100
    p["targets"]["micros"]["magnesium_mg"] = {"floor": 350, "aim": 420, "supplement": supplement,
                                              "limits": [{"basis": "magnesium_added_mg", "ul": 250}]}
    return p


def status_row(path, key):
    from openpyxl import load_workbook
    ws = load_workbook(path, data_only=True)["Week summary"]
    col = 2 + list(M.MICRO_LABELS).index(key)
    rows = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1)}
    return ws, rows, col


@unittest.skipUnless(HAVE_OFFICE, "LibreOffice not installed")
class WorkbookStatus(unittest.TestCase):
    def build(self, plan):
        import build_workbook as B
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        xl = os.path.join(tmp, "w.xlsx")
        B.build(plan, xl)
        return xl

    def test_form_limit_exceeded_by_supplement_is_not_ok(self):
        p = magnesium_plan(1000)
        _, eng = micro(p, "magnesium_mg")
        self.assertEqual(eng["status"], "ABOVE UL (added/supplemental magnesium)")
        xl = self.build(p)
        T3.recalc(xl)
        ws, rows, col = status_row(xl, "magnesium_mg")
        self.assertAlmostEqual(ws.cell(rows["Average incl. supplements"], col).value, 1100)
        self.assertEqual(ws.cell(rows["Food without a value (max share of a day)"], col).value, 0)
        self.assertEqual(ws.cell(rows["Status"], col).value, "ABOVE UL (added/supplemental magnesium)")

    def test_editing_the_supplement_input_stays_live(self):
        from openpyxl import load_workbook
        xl = self.build(magnesium_plan(100))   # 100 mg: below the form limit at build
        wb = load_workbook(xl)
        ws = wb["Week summary"]
        col = 2 + list(M.MICRO_LABELS).index("magnesium_mg")
        srow = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Supplements / day")
        ws.cell(srow, col).value = 1000            # the user edits the blue input
        wb.save(xl)
        T3.recalc(xl)
        ws, rows, col = status_row(xl, "magnesium_mg")
        self.assertEqual(ws.cell(rows["Status"], col).value, "ABOVE UL (added/supplemental magnesium)")

    def test_form_limit_not_exceeded_is_marked_unchecked_not_ok(self):
        p = magnesium_plan(100)
        p["targets"]["micros"]["magnesium_mg"]["floor"] = 100
        p["targets"]["micros"]["magnesium_mg"]["aim"] = 150
        xl = self.build(p)
        T3.recalc(xl)
        ws, rows, col = status_row(xl, "magnesium_mg")
        self.assertEqual(ws.cell(rows["Status"], col).value, "form UL unchecked")

    def test_folate_form_limit_counts_methylfolate_supplement(self):
        p = T3.minimal_plan()
        p["ingredients"]["food"]["per100"]["folate_ug"] = 300
        p["targets"]["micros"]["folate_ug"] = {"floor": 300, "aim": 300, "supplement": 2000,
                                               "supplement_forms": {"folic_acid_ug": 0},
                                               "limits": [{"basis": "folate_added_ug", "ul": 1000}]}
        xl = self.build(p)
        T3.recalc(xl)
        ws, rows, col = status_row(xl, "folate_ug")
        self.assertTrue(str(ws.cell(rows["Status"], col).value).startswith("ABOVE UL (added/supplemental folate"))

    def test_tiny_unknown_mass_leaves_total_ul_unverified(self):
        xl = self.build(T4.plan(unknown_g=5, known_g=1000, known_per100=2, ul=100))
        T3.recalc(xl)
        ws, rows, col = status_row(xl, "vitD_ug")
        self.assertLess(ws.cell(rows["Food without a value (max share of a day)"], col).value, 0.01)
        self.assertEqual(ws.cell(rows["Status"], col).value, "UL unverified")

    def test_complete_data_still_reads_ok(self):
        xl = self.build(T4.plan(unknown_g=5, known_g=1000, known_per100=2, ul=100, unknown_value=0))
        T3.recalc(xl)
        ws, rows, col = status_row(xl, "vitD_ug")
        self.assertEqual(ws.cell(rows["Status"], col).value, "ok")


try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except Exception:
    HAVE_PW = False


@unittest.skipUnless(HAVE_PW, "Playwright not installed")
class ExpiredShoppingList(unittest.TestCase):
    def test_message_names_the_setting_that_extends_the_list(self):
        import render_pages as R
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        argv = sys.argv
        sys.argv = ["render_pages.py", os.path.join(ROOT, "assets", "example_plan.json"), tmp]
        try:
            R.main()
        finally:
            sys.argv = argv
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception as e:
                self.skipTest(f"Chromium not available: {e}")
            page = browser.new_page()
            page.clock.set_fixed_time(dt.datetime(2028, 3, 1, 12, tzinfo=dt.timezone.utc))
            page.goto("file://" + os.path.join(tmp, "shopping-list.html"))
            cycle = page.evaluate("state.cycle")
            text = page.inner_text("#runs")
            browser.close()
        self.assertIn("covers 13 cycles", text)
        self.assertIn("shopping.horizon_cycles", text)
        self.assertIn(f"at least {cycle}", text)
        self.assertNotIn("Re-run the plan scripts to extend it", text)


if __name__ == "__main__":
    unittest.main()
