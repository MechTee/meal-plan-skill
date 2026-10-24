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


if __name__ == "__main__":
    unittest.main()
