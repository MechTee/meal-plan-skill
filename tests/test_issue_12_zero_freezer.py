"""Issue #12: freezer_portions = 0 is a real limit (no freezer), not 'unspecified'."""
import copy, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M

with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
    BASE = json.load(f)


def with_freezer(value, drop=False):
    p = copy.deepcopy(BASE)
    if drop:
        p["meta"].pop("freezer_portions", None)
    else:
        p["meta"]["freezer_portions"] = value
    return p


def freezer_flags(p):
    return [f for f in M.compute(p)["checks"]["flags"] if f.startswith("freezer:")]


class FreezerCapacity(unittest.TestCase):
    def test_zero_capacity_flags_frozen_stock(self):
        flags = freezer_flags(with_freezer(0))
        self.assertEqual(len(flags), 1)
        self.assertIn("vs capacity 0", flags[0])

    def test_missing_capacity_is_not_checked(self):
        self.assertEqual(freezer_flags(with_freezer(None, drop=True)), [])

    def test_large_capacity_passes(self):
        self.assertEqual(freezer_flags(with_freezer(1000)), [])

    def test_invalid_values_are_rejected(self):
        for bad in (-1, "twenty", True):
            with self.assertRaises(M.PlanError, msg=repr(bad)):
                M.validate(with_freezer(bad))
        M.validate(with_freezer(0))
        M.validate(with_freezer(12.5))


if __name__ == "__main__":
    unittest.main()
