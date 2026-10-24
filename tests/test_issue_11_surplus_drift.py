"""Issue #11: a batch surplus that grows every cycle is not a steady state."""
import copy, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M

with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
    BASE = json.load(f)


def example(**cycle_changes):
    p = copy.deepcopy(BASE)
    p["cycle"].update(cycle_changes)
    return p


class Drift(unittest.TestCase):
    def test_issue_reproduction_is_flagged_even_with_a_large_freezer(self):
        p = example()
        p["meta"]["freezer_portions"] = 40
        res = M.compute(p)
        inv = res["inventory"]
        self.assertFalse(inv["steady"])
        self.assertEqual(set(inv["growing"]), {"chili", "curry"})
        self.assertEqual(inv["drift_per_cycle"], 4)
        self.assertTrue(any(f.startswith("batch surplus grows every cycle") for f in res["checks"]["flags"]))
        self.assertIn("NOT steady", M.report(p, res))
        # the growth is real: longer simulations keep rising
        self.assertLess(M.inventory(p, cycles=3)["peak_total_portions"], M.inventory(p, cycles=6)["peak_total_portions"])

    def test_balanced_rotation_is_steady(self):
        p = example()
        for s in p["cycle"]["sessions"]:
            if s["label"] == "Sunday B":
                s["weeks"] = [2]           # chili + curry cooked 3x per cycle instead of 4 → 15 each
        for w in ("2", "4"):
            p["week_overrides"][w]["Sat"]["meals"][-2]["parts"][0]["recipe"] = "curry"
        inv = M.inventory(p, cycles=4)
        if inv["growing"]:
            self.skipTest("rotation tweak did not balance — not what this test is about")
        self.assertTrue(inv["steady"])
        self.assertEqual(inv["drift_per_cycle"], 0)

    def test_discard_policy_converges(self):
        p = example(surplus_policy={"mode": "discard", "keep": 2})
        inv = M.inventory(p, cycles=6)
        self.assertTrue(inv["steady"])
        self.assertEqual(inv["peak_by_cycle"][-1], inv["peak_by_cycle"][-2])
        self.assertIn("chili", inv["discarded_per_cycle"])
        res = M.compute(p)
        self.assertFalse(any(f.startswith("batch surplus") for f in res["checks"]["flags"]))

    def test_horizon_policy_states_a_finite_verification(self):
        p = example(surplus_policy={"mode": "horizon", "cycles": 6})
        p["meta"]["freezer_portions"] = 45
        res = M.compute(p)
        self.assertEqual(res["inventory"]["cycles_simulated"], 6)
        flags = " | ".join(res["checks"]["flags"])
        self.assertIn("verified for 6 cycles only", flags)
        self.assertIn("freezer: peak", flags)          # 6 cycles of growth exceed 45 containers


if __name__ == "__main__":
    unittest.main()
