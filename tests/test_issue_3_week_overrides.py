"""Issue #3: checks and the workbook must cover every week override, not just the template week."""
import copy, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M

DAYS = M.WEEKDAYS


def minimal_plan():
    """Two-week plan: 100 g of a vitamin-D food (20 µg/100 g, 500 kcal/100 g) every day."""
    food = {"name": "Vit D food", "unit": "g", "category": "Test",
            "per100": {"kcal": 500, "protein_g": 30, "fat_g": 10, "satfat_g": 2, "carb_g": 60, "sugar_g": 5,
                       "fiber_g": 5, "salt_g": 0.5, "vitD_ug": 20},
            "allergens": [], "may_contain": [], "shop": {"buy": "stock", "pack_size": 1000, "price": 1}}
    day = {"type": "training", "meals": [{"name": "Meal", "parts": [{"ingredient": "food", "amount": 100}]}]}
    plan = {"meta": {"name": "t", "bw_kg": 70, "allergies": {"status": "none"}},
            "targets": {"training": {"kcal": 500, "protein_g": 30}, "rest": {"kcal": 400, "protein_g": 30},
                        "micros": {"vitD_ug": {"floor": 20, "aim": 20, "ul": 100}}},
            "ingredients": {"food": food}, "recipes": {},
            "days": {d: copy.deepcopy(day) for d in DAYS},
            "cycle": {"weeks": 2, "start_date": "2026-11-02", "sessions": []},
            "shopping": {}}
    return plan


def with_override(amount=1000, typ="training"):
    p = minimal_plan()
    d = copy.deepcopy(p["days"]["Mon"])
    d["type"] = typ
    d["meals"][0]["parts"][0]["amount"] = amount
    p["week_overrides"] = {"2": {"Mon": d}}
    return p


class OverrideChecks(unittest.TestCase):
    def test_overridden_micro_exceeding_ul_is_flagged_with_week(self):
        res = M.compute(with_override(1000))
        self.assertAlmostEqual(res["weeks"][2]["Mon"]["vitD_ug"], 200)
        row = next(r for r in res["checks"]["micros"] if r["key"] == "vitD_ug")
        self.assertEqual(row["max"], 200)
        self.assertTrue(row["status"].startswith("ABOVE UL"))
        self.assertEqual(row["max_day"], "Mon (wk 2)")
        self.assertTrue(any("vitD_ug" in f and "Mon (wk 2)" in f for f in res["checks"]["flags"]))

    def test_overridden_energy_is_flagged_with_week(self):
        res = M.compute(with_override(1000))
        days = {r["day"]: r for r in res["checks"]["days"]}
        self.assertIn("Mon (wk 1)", days)
        self.assertIn("Mon (wk 2)", days)
        self.assertEqual(days["Mon (wk 2)"]["kcal"], 5000)
        self.assertTrue(any(f.startswith("Mon (wk 2): kcal 5000") for f in res["checks"]["flags"]))
        self.assertFalse(any(f.startswith("Mon (wk 1): kcal") for f in res["checks"]["flags"]))

    def test_override_day_type_uses_its_own_targets(self):
        res = M.compute(with_override(80, typ="rest"))
        row = next(r for r in res["checks"]["days"] if r["day"] == "Mon (wk 2)")
        self.assertEqual(row["type"], "rest")
        self.assertEqual(row["kcal_target"], 400)

    def test_cycle_average_covers_every_actual_day(self):
        res = M.compute(with_override(1000))
        row = next(r for r in res["checks"]["micros"] if r["key"] == "vitD_ug")
        self.assertAlmostEqual(row["avg"], (13 * 20 + 200) / 14, places=2)

    def test_no_overrides_keeps_plain_day_labels(self):
        res = M.compute(minimal_plan())
        self.assertEqual([r["day"] for r in res["checks"]["days"]], DAYS)


def recalc(path):
    office = shutil.which("soffice") or shutil.which("libreoffice")
    with tempfile.TemporaryDirectory() as tmp:
        prof = os.path.join(tmp, "p", "user")
        os.makedirs(prof)
        with open(os.path.join(prof, "registrymodifications.xcu"), "w") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry" '
                    'xmlns:xs="http://www.w3.org/2001/XMLSchema"><item oor:path="/org.openoffice.Office.Calc/Formula/Load">'
                    '<prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop></item></oor:items>')
        out = os.path.join(tmp, "o")
        subprocess.run([office, f"-env:UserInstallation=file://{os.path.join(tmp, 'p')}", "--headless", "--convert-to", "xlsx",
                        "--outdir", out, path], check=True, capture_output=True, timeout=300)
        shutil.copyfile(os.path.join(out, os.path.basename(path)), path)


@unittest.skipUnless(shutil.which("soffice") or shutil.which("libreoffice"), "LibreOffice not installed")
class OverrideWorkbook(unittest.TestCase):
    def test_workbook_has_override_sheet_and_cycle_calendar(self):
        from openpyxl import load_workbook
        import build_workbook as B
        p = with_override(1000)
        res = M.compute(p)
        with tempfile.TemporaryDirectory() as tmp:
            xl = os.path.join(tmp, "w.xlsx")
            B.build(p, xl)
            recalc(xl)
            wb = load_workbook(xl, data_only=True)
            self.assertIn("Mon wk2", wb.sheetnames)
            ws = wb["Week summary"]
            cal = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Cycle calendar — kcal per day")
            for w in (1, 2):
                for i, d in enumerate(DAYS):
                    self.assertAlmostEqual(ws.cell(cal + 1 + w, 2 + i).value, res["weeks"][w][d]["kcal"], places=1)
            avg_row = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Cycle average (per day)")
            self.assertAlmostEqual(ws.cell(avg_row, 3).value, (13 * 500 + 5000) / 14, places=1)
            food = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Food average (cycle)")
            vitd_col = 2 + list(M.MICRO_LABELS).index("vitD_ug")
            self.assertAlmostEqual(ws.cell(food, vitd_col).value, (13 * 20 + 200) / 14, places=2)

    def test_example_plan_workbook_matches_engine_for_override_saturday(self):
        from openpyxl import load_workbook
        import build_workbook as B
        p = M.load(os.path.join(ROOT, "assets", "example_plan.json"))
        res = M.compute(p)
        with tempfile.TemporaryDirectory() as tmp:
            xl = os.path.join(tmp, "w.xlsx")
            B.build(p, xl)
            recalc(xl)
            wb = load_workbook(xl, data_only=True)
            self.assertIn("Sat wk2+4", wb.sheetnames)
            ws = wb["Week summary"]
            row = next(r for r in range(5, 20) if ws.cell(r, 1).value == "Saturday · weeks 2, 4")
            self.assertAlmostEqual(ws.cell(row, 3).value, res["weeks"][2]["Sat"]["kcal"], places=1)


if __name__ == "__main__":
    unittest.main()
