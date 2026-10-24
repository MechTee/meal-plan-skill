"""Issue #4: totals with missing nutrient values are lower bounds and must not be reported as ok."""
import copy, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M


def plan(unknown_g=100, known_g=1, known_per100=2000, unknown_value=None, ul=100):
    def ing(name, vitd):
        p = {"kcal": 100, "protein_g": 5, "fat_g": 1, "satfat_g": 0, "carb_g": 15, "sugar_g": 1, "fiber_g": 2, "salt_g": 0}
        if vitd is not None:
            p["vitD_ug"] = vitd
        return {"name": name, "unit": "g", "per100": p, "allergens": [], "may_contain": [],
                "shop": {"buy": "stock", "pack_size": 1000, "price": 1}}
    day = {"type": "training", "meals": [{"name": "Meal", "parts": [{"ingredient": "unknown", "amount": unknown_g},
                                                                     {"ingredient": "known", "amount": known_g}]}]}
    return {"meta": {"name": "t", "bw_kg": 70, "allergies": {"status": "none"}},
            "targets": {"training": {"kcal": 100}, "rest": {"kcal": 100},
                        "micros": {"vitD_ug": {"floor": 20, "aim": 20, "ul": ul}}},
            "ingredients": {"unknown": ing("Food without vitamin D value", unknown_value), "known": ing("Vitamin D source", known_per100)},
            "recipes": {}, "days": {d: copy.deepcopy(day) for d in M.WEEKDAYS},
            "cycle": {"weeks": 1, "start_date": "2026-11-02", "sessions": []}, "shopping": {}}


def vitd_row(p):
    res = M.compute(p)
    return res, next(r for r in res["checks"]["micros"] if r["key"] == "vitD_ug")


class LowerBounds(unittest.TestCase):
    def test_issue_reproduction_is_not_ok(self):
        res, row = vitd_row(plan())
        self.assertAlmostEqual(row["avg"], 20)
        self.assertGreater(row["missing_share"], 0.9)
        self.assertNotEqual(row["status"], "ok")
        self.assertTrue(row["lower_bound"])
        self.assertEqual(row["min_status"], "met (known part alone)")
        self.assertEqual(row["ul_status"], "UL unverified")
        self.assertTrue(any("vitD_ug" in f and "UL unverified" in f for f in res["checks"]["flags"]))
        self.assertIn("≥ 20.0", M.report(p := plan(), M.compute(p)))

    def test_complete_data_is_ok(self):
        _, row = vitd_row(plan(unknown_value=0))
        self.assertEqual(row["status"], "ok")
        self.assertFalse(row["lower_bound"])

    def test_known_part_above_ul_is_reported_above_ul(self):
        _, row = vitd_row(plan(known_g=6))  # 120 µg known
        self.assertTrue(row["status"].startswith("ABOVE UL"))

    def test_known_part_below_floor_is_unverified_not_below(self):
        _, row = vitd_row(plan(known_g=0.5))  # 10 µg known
        self.assertEqual(row["min_status"], "unverified — known part below floor")
        self.assertNotEqual(row["status"], "below floor")

    def test_without_ul_a_met_lower_bound_is_not_flagged_but_not_ok(self):
        res, row = vitd_row(plan(ul=None))
        self.assertNotEqual(row["status"], "ok")
        self.assertFalse(any("vitD_ug" in f for f in res["checks"]["flags"]))


@unittest.skipUnless(shutil.which("soffice") or shutil.which("libreoffice"), "LibreOffice not installed")
class WorkbookShowsGaps(unittest.TestCase):
    def test_status_row_says_ul_unverified(self):
        from openpyxl import load_workbook
        import build_workbook as B
        office = shutil.which("soffice") or shutil.which("libreoffice")
        with tempfile.TemporaryDirectory() as tmp:
            xl = os.path.join(tmp, "w.xlsx")
            B.build(plan(), xl)
            prof = os.path.join(tmp, "p", "user")
            os.makedirs(prof)
            with open(os.path.join(prof, "registrymodifications.xcu"), "w") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry" '
                        'xmlns:xs="http://www.w3.org/2001/XMLSchema"><item oor:path="/org.openoffice.Office.Calc/Formula/Load">'
                        '<prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop></item></oor:items>')
            subprocess.run([office, f"-env:UserInstallation=file://{os.path.join(tmp, 'p')}", "--headless", "--convert-to",
                            "xlsx", "--outdir", os.path.join(tmp, "o"), xl], check=True, capture_output=True, timeout=300)
            wb = load_workbook(os.path.join(tmp, "o", "w.xlsx"), data_only=True)
            ws = wb["Week summary"]
            col = 2 + list(M.MICRO_LABELS).index("vitD_ug")
            rows = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1)}
            self.assertGreater(ws.cell(rows["Food without a value (max share of a day)"], col).value, 0.9)
            self.assertEqual(ws.cell(rows["Status"], col).value, "≥ aim · UL unverified")


if __name__ == "__main__":
    unittest.main()
