"""Issue #16: targets that cannot be met (negative carbohydrate) are an infeasible result, not a plan."""
import json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import targets

ISSUE = {"sex": "female", "age": 70, "height_cm": 150, "weight_kg": 50, "goal": "cut", "rate_pct_bw_per_week": 1.0}


class Feasibility(unittest.TestCase):
    def test_issue_reproduction_is_infeasible(self):
        r = targets.compute(ISSUE)
        self.assertFalse(r["feasible"])
        self.assertNotIn("targets", r)
        self.assertTrue(any("carbohydrate would be -35 g" in p for p in r["problems"]))
        self.assertIn("slower rate", r["advice"])

    def test_no_negative_targets_anywhere(self):
        for rate in (0.25, 0.5, 0.75, 1.0):
            for w in (50, 60, 80, 100):
                r = targets.compute({"sex": "female", "age": 30, "height_cm": 165, "weight_kg": w, "goal": "cut",
                                     "rate_pct_bw_per_week": rate})
                if r["feasible"]:
                    for day in ("training", "rest"):
                        for k, v in r["targets"][day].items():
                            self.assertGreaterEqual(v, 0, (rate, w, day, k))

    def test_slower_rate_becomes_feasible(self):
        r = targets.compute(dict(ISSUE, goal="maintain"))
        self.assertTrue(r["feasible"])
        self.assertGreater(r["targets"]["rest"]["carb_g"], 0)

    def test_below_bmr_is_noted(self):
        r = targets.compute({"sex": "male", "age": 32, "height_cm": 187, "weight_kg": 87, "bodyfat_pct": 13,
                             "goal": "cut", "rate_pct_bw_per_week": 1.0})
        self.assertTrue(r["feasible"])
        self.assertTrue(any("below the estimated BMR" in n for n in r["notes"]))

    def test_cli_exit_code(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(ISSUE, f)
        p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "targets.py"), f.name], capture_output=True, text=True)
        os.unlink(f.name)
        self.assertEqual(p.returncode, 3)
        self.assertIn("Infeasible targets", p.stdout)


if __name__ == "__main__":
    unittest.main()
