"""Regressions found while combining the fix branches: places where two fixes meet."""
import copy, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M
import targets

with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
    BASE = json.load(f)


class OverrideDaysInDayChecks(unittest.TestCase):
    def test_fibre_check_on_a_week_override_day(self):
        """#3 x #4: the fibre gap is read from the cycle day itself, so override days don't crash checks()."""
        p = copy.deepcopy(BASE)
        p["targets"]["fiber_min"] = 200          # every day is under it, override days included
        res = M.compute(p)
        labels = {cd["label"] for cd in res["cycle_days"] if cd["override"] or len(cd["weeks"]) < M.cycle_weeks(p)}
        self.assertTrue(labels)
        for lab in labels:
            self.assertTrue(any(f.startswith(f"{lab}: fibre") for f in res["checks"]["flags"]), lab)


class FormLimitFlags(unittest.TestCase):
    def test_form_limit_flag_names_the_form_amount(self):
        """#3 x #6: a form limit flag quotes the form's peak, not the day with the highest total."""
        std = targets.compute({"sex": "male", "age": 35, "height_cm": 180, "weight_kg": 80, "goal": "maintain",
                               "sessions": [{"type": "resistance_vigorous", "minutes": 60, "per_week": 4}]})["targets"]["micros"]
        p = copy.deepcopy(BASE)
        p["targets"]["micros"] = copy.deepcopy(std)
        p["targets"]["micros"]["magnesium_mg"]["supplement"] = 300
        res = M.compute(p)
        row = next(r for r in res["checks"]["micros"] if r["key"] == "magnesium_mg")
        self.assertEqual(row["status"], "ABOVE UL (added/supplemental magnesium)")   # no "(known part alone)"
        flag = next(f for f in res["checks"]["flags"] if f.startswith("micro magnesium_mg"))
        self.assertIn("added/supplemental magnesium peak 300 vs UL 250", flag)
        self.assertNotIn("highest day", flag)


class LongHorizon(unittest.TestCase):
    def test_budget_simulation_never_shorter_than_shopping_horizon(self):
        """#10 x #22: packs_by_cycle covers every cycle the page offers, even beyond the slow-mover cap."""
        p = copy.deepcopy(BASE)
        p["cycle"]["weeks"] = 1
        p["cycle"]["sessions"] = [dict(s, weeks=[1]) for s in p["cycle"]["sessions"][:1]]
        p["week_overrides"] = {}
        p["shopping"]["horizon_cycles"] = M.BUDGET_MAX_CYCLES + 40
        sh = M.shopping(p)
        self.assertEqual(sh["horizon_cycles"], M.BUDGET_MAX_CYCLES + 40)
        self.assertGreaterEqual(sh["budget_cycles_simulated"], sh["horizon_cycles"])
        for r in sh["runs"]:
            for it in r["items"]:
                self.assertEqual(len(it["packs_by_cycle"]), sh["horizon_cycles"], it["name"])


if __name__ == "__main__":
    unittest.main()
