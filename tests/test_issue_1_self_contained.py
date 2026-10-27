"""Issue #1: the skill must be installable and runnable from this repository alone."""
import json, os, re, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")


class SelfContained(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return f.read()

    def test_no_private_bootstrap(self):
        for rel in ("SKILL.md", "README.md", "references/artifacts.md", "references/interview.md"):
            text = self.read(rel)
            self.assertNotIn("athlete-meal-plan-kit", text, rel)
            self.assertNotIn('"Meal Plan"', text, rel)
            self.assertNotIn("xlsx skill", text, rel)
            self.assertNotIn("/mnt/skills", text, rel)

    def test_every_referenced_file_exists(self):
        text = self.read("SKILL.md") + self.read("README.md")
        refs = set(re.findall(r"\b((?:scripts|assets|references)/[\w.\-]+\.(?:py|md|html|json))", text))
        self.assertTrue(refs)
        for rel in refs:
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "requirements.txt")))

    def test_capability_fallbacks_documented(self):
        text = self.read("SKILL.md")
        self.assertIn("## Host capabilities", text)
        for need in ("Structured questions", "Workbook recalculation", "Delivering files", "HTML pages"):
            self.assertIn(need, text)

    def test_recalc_reports_unavailable_without_libreoffice(self):
        with tempfile.TemporaryDirectory() as tmp:
            xl = os.path.join(tmp, "w.xlsx")
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_workbook.py"),
                            os.path.join(ROOT, "assets", "example_plan.json"), xl], check=True, capture_output=True)
            p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "recalc.py"), xl],
                               capture_output=True, text=True, env={"PATH": tmp})
            self.assertEqual(p.returncode, 3)
            self.assertEqual(json.loads(p.stdout)["status"], "unavailable")

    @unittest.skipUnless(shutil.which("soffice") or shutil.which("libreoffice"), "LibreOffice not installed")
    def test_recalc_and_engine_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            xl = os.path.join(tmp, "w.xlsx")
            plan = os.path.join(ROOT, "assets", "example_plan.json")
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_workbook.py"), plan, xl], check=True, capture_output=True)
            p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "recalc.py"), xl], capture_output=True, text=True, timeout=300)
            r = json.loads(p.stdout)
            self.assertEqual(r["status"], "success", r)
            p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_workbook.py"), plan, xl], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout)

    @unittest.skipUnless(shutil.which("soffice") or shutil.which("libreoffice"), "LibreOffice not installed")
    def test_check_survives_dashed_meal_names_and_catches_wrong_totals(self):
        """Review on PR #25: a meal named "Dinner — chili" must not end the day block early."""
        from openpyxl import load_workbook
        with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
            data = json.load(f)
        for d in data["days"].values():
            for m in d["meals"]:
                m["name"] = m["name"] + " — dashed"
        with tempfile.TemporaryDirectory() as tmp:
            plan, xl = os.path.join(tmp, "p.json"), os.path.join(tmp, "w.xlsx")
            with open(plan, "w", encoding="utf-8") as f:
                json.dump(data, f)
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_workbook.py"), plan, xl], check=True, capture_output=True)
            p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "recalc.py"), xl], capture_output=True, text=True, timeout=300)
            self.assertEqual(json.loads(p.stdout)["status"], "success")
            def check():   # openpyxl drops cached values on save — recalculate before every check
                subprocess.run([sys.executable, os.path.join(SCRIPTS, "recalc.py"), xl], capture_output=True, timeout=300)
                return subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_workbook.py"), plan, xl],
                                      capture_output=True, text=True)
            p = check()
            self.assertEqual(p.returncode, 0, p.stdout)
            # corrupt one cached Day total on Micros: the check must now see it
            wb = load_workbook(xl)
            wv = load_workbook(xl, data_only=True)
            ws, wsv = wb["Micros"], wv["Micros"]
            r = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Day total")
            ws.cell(r, 2).value = float(wsv.cell(r, 2).value or 0) * 3 + 50   # literal value replaces the formula
            wb.save(xl)
            p = check()
            self.assertEqual(p.returncode, 1, p.stdout)
            self.assertIn("Micros Monday", p.stdout)
            # remove a day heading: the check reports the unchecked day instead of passing
            wb = load_workbook(xl)
            ws = wb["EAA"]
            r = next(r for r in range(1, ws.max_row + 1) if str(ws.cell(r, 1).value).startswith("Tuesday — "))
            ws.cell(r, 1).value = "something else"
            wb.save(xl)
            p = check()
            self.assertEqual(p.returncode, 1)
            sys.path.insert(0, SCRIPTS)
            import mealplan as M
            n = len(M.day_groups(data))          # template days + week overrides
            self.assertIn(f"EAA: day totals checked for {n - 1} of {n} days — missing Tuesday", p.stdout)


if __name__ == "__main__":
    unittest.main()
