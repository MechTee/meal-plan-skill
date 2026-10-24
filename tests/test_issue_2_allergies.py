"""Issue #2: allergy status is mandatory, never defaulted to none, and binding in checks."""
import copy, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M

with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
    BASE = json.load(f)


def plan_with(allergies=None, drop=False):
    p = copy.deepcopy(BASE)
    if drop:
        p["meta"].pop("allergies", None)
    else:
        p["meta"]["allergies"] = allergies
    return p


class AllergyStatus(unittest.TestCase):
    def test_missing_status_is_a_plan_error(self):
        with self.assertRaises(M.PlanError):
            M.validate(plan_with(drop=True))

    def test_known_requires_items_and_none_rejects_items(self):
        with self.assertRaises(M.PlanError):
            M.validate(plan_with({"status": "known", "items": []}))
        with self.assertRaises(M.PlanError):
            M.validate(plan_with({"status": "none", "items": ["soy"]}))

    def test_unknown_is_flagged_not_treated_as_none(self):
        p = plan_with({"status": "unknown"})
        M.validate(p)
        res = M.compute(p)
        self.assertEqual(res["checks"]["allergies"]["status"], "unknown")
        self.assertTrue(any("ALLERGY STATUS UNKNOWN" in f for f in res["checks"]["flags"]))
        self.assertIn("UNKNOWN", M.report(p, res))

    def test_confirmed_none_has_no_allergy_flags(self):
        res = M.compute(plan_with({"status": "none", "items": []}))
        self.assertFalse([f for f in res["checks"]["flags"] if "ALLERG" in f])


class AllergyBinding(unittest.TestCase):
    def test_known_allergen_conflict_is_flagged(self):
        res = M.compute(plan_with({"status": "known", "items": ["soy"]}))
        conflicts = {c["ingredient"] for c in res["checks"]["allergies"]["conflicts"]}
        self.assertIn("Soy chunks, dry", conflicts)
        self.assertIn("Soy protein isolate", conflicts)
        self.assertTrue(any(f.startswith("ALLERGEN CONFLICT") for f in res["checks"]["flags"]))

    def test_traces_respect_traces_matter(self):
        p = plan_with({"status": "known", "items": ["crustaceans"], "traces_matter": True})
        self.assertTrue(M.compute(p)["checks"]["allergies"]["traces"])
        p["meta"]["allergies"]["traces_matter"] = False
        self.assertFalse(M.compute(p)["checks"]["allergies"]["traces"])

    def test_untagged_ingredient_is_reported_as_unchecked(self):
        p = plan_with({"status": "known", "items": ["sesame"]})
        del p["ingredients"]["oats"]["allergens"]
        res = M.compute(p)
        self.assertIn("Oats, fine", res["checks"]["allergies"]["unchecked"])

    def test_substitution_clears_conflict(self):
        """A known-allergy swap: replacing the soy chunks in the dal removes that conflict."""
        p = plan_with({"status": "known", "items": ["soy"]})
        p["recipes"]["dal"]["items"] = [it for it in p["recipes"]["dal"]["items"] if it[0] != "chunks"] + [["lentils", 200]]
        conflicts_before = {c["ingredient"] for c in M.compute(plan_with({"status": "known", "items": ["soy"]}))["checks"]["allergies"]["conflicts"]}
        conflicts_after = {c["ingredient"] for c in M.compute(p)["checks"]["allergies"]["conflicts"]}
        self.assertIn("Soy chunks, dry", conflicts_before)
        self.assertIn("Soy chunks, dry", conflicts_after)  # still used by chili/curry/bolo
        for rk in ("chili", "curry", "bolo"):
            p["recipes"][rk]["items"] = [it for it in p["recipes"][rk]["items"] if it[0] != "chunks"]
        self.assertNotIn("Soy chunks, dry", {c["ingredient"] for c in M.compute(p)["checks"]["allergies"]["conflicts"]})


class InterviewInstructions(unittest.TestCase):
    def test_safety_screen_asks_allergies_regardless_of_depth(self):
        with open(os.path.join(ROOT, "references", "interview.md"), encoding="utf-8") as f:
            text = f.read()
        screen = text[text.index("## Safety screen"):text.index("## 1 · Goal")]
        self.assertIn("allergies", screen.lower())
        self.assertIn("never as `none`", screen)


if __name__ == "__main__":
    unittest.main()
