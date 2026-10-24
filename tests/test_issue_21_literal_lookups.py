"""Issue #21: workbook lookups match ingredients literally by a stable ID, never by display name."""
import copy, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M
import build_workbook as B

NAMES = ["Milk", "milk", "Milk plain", "Milk*", "Milk?", "~Milk", "M?lk"]


def plan(use="milk2"):
    ings = {}
    for i, name in enumerate(NAMES, 1):
        ings[f"milk{i}"] = {"name": name, "unit": "g", "allergens": [], "may_contain": [],
                            "per100": {"kcal": 100 * i, "protein_g": i, "fat_g": i, "satfat_g": 0, "carb_g": i, "sugar_g": 0,
                                       "fiber_g": 0, "salt_g": 0, "calcium_mg": 100 * i},
                            "aa": {"leu": 0.1 * i}}
    day = {"type": "training", "meals": [{"name": "Glass", "parts": [{"ingredient": use, "amount": 100}]}]}
    return {"meta": {"name": "t", "bw_kg": 70, "allergies": {"status": "none"}}, "targets": {},
            "ingredients": ings, "recipes": {}, "days": {d: copy.deepcopy(day) for d in M.WEEKDAYS},
            "cycle": {"weeks": 1, "start_date": "2026-11-02", "sessions": []}, "shopping": {}}


class Ids(unittest.TestCase):
    def test_ids_are_unique_literal_and_stable(self):
        ids = B.ingredient_ids(plan())
        self.assertEqual(len(set(ids.values())), len(NAMES))
        self.assertEqual(len({v.lower() for v in ids.values()}), len(NAMES))   # also unique ignoring case
        for v in ids.values():
            self.assertRegex(v, r"^[A-Z0-9_]+$")                                 # no * ? ~
        self.assertEqual(ids, B.ingredient_ids(plan()))

    def test_case_variant_keys_get_distinct_ids(self):
        p = plan()
        p["ingredients"]["MILK1"] = copy.deepcopy(p["ingredients"]["milk1"])
        ids = B.ingredient_ids(p)
        self.assertNotEqual(ids["milk1"], ids["MILK1"])


def recalc(path):
    office = shutil.which("soffice") or shutil.which("libreoffice")
    with tempfile.TemporaryDirectory() as tmp:
        prof = os.path.join(tmp, "p", "user")
        os.makedirs(prof)
        with open(os.path.join(prof, "registrymodifications.xcu"), "w") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry" '
                    'xmlns:xs="http://www.w3.org/2001/XMLSchema"><item oor:path="/org.openoffice.Office.Calc/Formula/Load">'
                    '<prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop></item></oor:items>')
        subprocess.run([office, f"-env:UserInstallation=file://{os.path.join(tmp, 'p')}", "--headless", "--convert-to",
                        "xlsx", "--outdir", os.path.join(tmp, "o"), path], check=True, capture_output=True, timeout=300)
        shutil.copyfile(os.path.join(tmp, "o", os.path.basename(path)), path)


@unittest.skipUnless(shutil.which("soffice") or shutil.which("libreoffice"), "LibreOffice not installed")
class WorkbookMatchesEngine(unittest.TestCase):
    def test_every_adversarial_name_resolves_to_its_own_row(self):
        from openpyxl import load_workbook
        calcium_col = 2 + list(M.MICRO_LABELS).index("calcium_mg")
        for key in [f"milk{i}" for i in range(1, len(NAMES) + 1)]:
            p = plan(key)
            n = M.compute(p)["days"]["Mon"]["total"]
            with tempfile.TemporaryDirectory() as tmp:
                xl = os.path.join(tmp, "w.xlsx")
                B.build(p, xl)
                recalc(xl)
                wb = load_workbook(xl, data_only=True)
                mon, mic, eaa = wb["Mon"], wb["Micros"], wb["EAA"]
                name = p["ingredients"][key]["name"]
                self.assertAlmostEqual(mon["E6"].value, n["n"]["kcal"], places=3, msg=f"kcal for {name!r}")
                tot = next(r for r in range(1, mic.max_row + 1) if mic.cell(r, 1).value == "Day total")
                self.assertAlmostEqual(mic.cell(tot, calcium_col).value, n["n"]["calcium_mg"], places=3, msg=f"calcium for {name!r}")
                tot = next(r for r in range(1, eaa.max_row + 1) if eaa.cell(r, 1).value == "Day total")
                self.assertAlmostEqual(eaa.cell(tot, 5).value, n["aa"]["leu"], places=3, msg=f"leucine for {name!r}")


if __name__ == "__main__":
    unittest.main()
