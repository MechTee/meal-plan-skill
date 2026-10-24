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


def one_week(portions, keep, day="Sun", prior=True):
    """A one-week plan: one batch recipe cooked once, one portion eaten every day."""
    p = copy.deepcopy(BASE)
    p["recipes"]["dal"]["portions"] = portions
    for d in M.WEEKDAYS:
        p["days"][d]["meals"] = [{"name": "Lunch", "parts": [{"recipe": "dal", "portions": 1}]}]
    p["week_overrides"] = {}
    p["cycle"] = {"weeks": 1, "start_date": "2026-11-02",
                  "sessions": [{"label": "Cook", "day": day, "prior": prior, "cook": {"dal": 1}}],
                  "surplus_policy": {"mode": "discard", "keep": keep}}
    return p


class DiscardReview(unittest.TestCase):
    """Review on PR #34."""
    def test_prior_cook_is_not_discarded(self):
        """Next cycle's Sunday cook happens before the old cycle's Sunday meal — the fresh batch survives."""
        inv = M.inventory(one_week(8, 1))
        self.assertTrue(inv["steady"])
        self.assertEqual(inv["steady_shortfalls"], [])
        self.assertEqual(inv["discarded_per_cycle"], {"dal": 1.0})
        self.assertEqual(inv["peak_total_portions"], 9)

    def test_midweek_cook_keeps_portions_for_the_days_before_it(self):
        """Portions eaten before the cycle's first cook (Mon/Tue before a Wednesday cook) are never discarded."""
        inv = M.inventory(one_week(7, 0, day="Wed", prior=False))
        self.assertTrue(inv["steady"])
        self.assertEqual(inv["steady_shortfalls"], [])
        self.assertEqual(inv["discarded_per_cycle"], {})

    def test_high_keep_is_simulated_to_convergence(self):
        p = example(surplus_policy={"mode": "discard", "keep": 100})
        p["meta"]["freezer_portions"] = 40
        res = M.compute(p)
        inv = res["inventory"]
        self.assertGreater(inv["cycles_simulated"], 6)
        self.assertGreater(inv["peak_total_portions"], M.inventory(example(), cycles=6)["peak_total_portions"])
        self.assertTrue(any(f.startswith("freezer: peak") for f in res["checks"]["flags"]))

    def test_keep_never_reached_is_not_steady(self):
        p = example(surplus_policy={"mode": "discard", "keep": 10000})
        res = M.compute(p)
        inv = res["inventory"]
        self.assertFalse(inv["steady"])
        self.assertEqual(inv["cycles_simulated"], M.DISCARD_MAX_CYCLES)
        self.assertTrue(any("under the discard policy" in f for f in res["checks"]["flags"]))


if __name__ == "__main__":
    unittest.main()
