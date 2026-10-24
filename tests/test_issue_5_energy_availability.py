"""Issue #5: energy availability subtracts exercise expenditure and is checked on the actual plan."""
import copy, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import energy, mealplan as M, targets

ISSUE_PROFILE = {"sex": "female", "age": 30, "height_cm": 165, "weight_kg": 60, "bodyfat_pct": 20, "goal": "cut",
                 "rate_pct_bw_per_week": 1.0, "sessions": [{"type": "running_tempo", "minutes": 90, "per_week": 6}]}


class TargetsEA(unittest.TestCase):
    def test_issue_example_is_low_and_flagged(self):
        r = targets.compute(ISSUE_PROFILE)
        ea = r["energy_availability"]["training"]
        self.assertEqual(r["targets"]["training"]["kcal"], 2000)
        self.assertEqual(ea["exercise_kcal"], 855)
        self.assertEqual(ea["ffm_kg"], 48.0)
        self.assertAlmostEqual(ea["value"], (2000 - 855.0) / 48, delta=0.1)   # 23.85, not 41.67
        self.assertEqual(ea["band"], "low")
        self.assertTrue(any("energy availability" in n and "LOW" in n for n in r["notes"]))

    def test_rest_day_has_no_exercise(self):
        r = targets.compute(ISSUE_PROFILE)
        self.assertEqual(r["energy_availability"]["rest"]["exercise_kcal"], 0)

    def test_missing_body_fat_is_explicit(self):
        p = dict(ISSUE_PROFILE)
        p.pop("bodyfat_pct")
        r = targets.compute(p)
        self.assertIsNone(r["energy_availability"]["training"]["value"])
        self.assertEqual(r["energy_availability"]["training"]["band"], "not computed")
        self.assertTrue(any("not computed" in n for n in r["notes"]))

    def test_describe_is_not_a_diagnosis(self):
        text = energy.describe(energy.assess(2000, 855, 48))
        self.assertIn("not a diagnosis", text)


class PlanCheckEA(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
            self.plan = json.load(f)

    def test_plan_check_uses_actual_intake(self):
        res = M.compute(self.plan)
        mon = next(r for r in res["checks"]["energy_availability"] if r["day"] == "Mon")
        kcal = res["days"]["Mon"]["total"]["n"]["kcal"]
        self.assertAlmostEqual(mon["value"], (kcal - 435) / 75.7, delta=0.1)

    def test_low_ea_day_is_flagged(self):
        p = copy.deepcopy(self.plan)
        p["days"]["Tue"]["exercise_kcal"] = 1500
        res = M.compute(p)
        self.assertTrue(any(f.startswith("Tue: energy availability") and "LOW" in f for f in res["checks"]["flags"]))

    def test_missing_inputs_flagged_in_a_cut(self):
        p = copy.deepcopy(self.plan)
        p["meta"].pop("ffm_kg")
        p["meta"]["goal"] = "cut"
        res = M.compute(p)
        self.assertTrue(any("energy availability not checked" in f for f in res["checks"]["flags"]))
        self.assertIn("energy availability not checked", M.report(p, res))

    def test_partial_mapping_is_reported(self):
        """Review on PR #29: known FFM but no training-day entry — the training days were not checked."""
        p = copy.deepcopy(self.plan)
        p["meta"]["exercise_kcal"] = {"rest": 0}
        p["meta"]["goal"] = "cut"
        res = M.compute(p)
        note = res["checks"].get("ea_note", "")
        train = [d for d in M.WEEKDAYS if p["days"][d]["type"] == "training"]
        self.assertTrue(note and all(d in note for d in train), note)
        self.assertTrue(any("energy availability not checked" in f for f in res["checks"]["flags"]))

    def test_day_level_exercise_without_meta_mapping_is_complete(self):
        """Review on PR #29: every day has exercise_kcal — no missing-input note, and every day is reported."""
        p = copy.deepcopy(self.plan)
        p["meta"].pop("exercise_kcal", None)
        for d in M.WEEKDAYS:
            p["days"][d]["exercise_kcal"] = 400 if p["days"][d]["type"] == "training" else 0
        res = M.compute(p)
        self.assertNotIn("ea_note", res["checks"])
        rep = M.report(p, res)
        for d in M.WEEKDAYS:
            self.assertIn(f"- {d}: ", rep)


class ToolkitManifest(unittest.TestCase):
    def test_every_script_is_in_the_restore_list(self):
        """Review on PR #29: a standalone install restores only the listed scripts."""
        with open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8") as f:
            skill = f.read()
        block = skill.split("**Toolkit setup", 1)[1].split("```", 2)[1]
        for name in sorted(os.listdir(os.path.join(ROOT, "scripts"))):
            if name.endswith(".py"):
                self.assertIn("scripts/" + name, block, name)


if __name__ == "__main__":
    unittest.main()
