"""Issue #6: upper limits apply to the right nutrient form and source; unknown forms are unresolved."""
import copy, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M, targets

with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
    BASE = json.load(f)
STANDARD = targets.compute({"sex": "male", "age": 35, "height_cm": 180, "weight_kg": 80, "goal": "maintain",
                            "sessions": [{"type": "resistance_vigorous", "minutes": 60, "per_week": 4}]})["targets"]["micros"]


def with_targets(**changes):
    p = copy.deepcopy(BASE)
    p["targets"]["micros"] = copy.deepcopy(STANDARD)
    for k, v in changes.items():
        p["targets"]["micros"][k].update(v)
    return p


def row(p, key):
    res = M.compute(p)
    return res, next(r for r in res["checks"]["micros"] if r["key"] == key)


def with_test_food(per100, origin=None, grams=100):
    p = with_targets()
    ing = {"name": "Test food", "unit": "g", "category": "Test",
           "per100": {"kcal": 50, "protein_g": 1, "fat_g": 0, "satfat_g": 0, "carb_g": 10, "sugar_g": 5,
                      "fiber_g": 2, "salt_g": 0, **per100}, "allergens": [], "may_contain": []}
    if origin:
        ing["origin"] = origin
    p["ingredients"]["testfood"] = ing
    p["ingredients"]["casein"]["per100"]["retinol_ug"] = 0   # isolate the test food: casein's vitamin A is unknown in the example
    for d in p["days"].values():
        d["meals"][0]["parts"].append({"ingredient": "testfood", "amount": grams})
    return p


class TargetsModelForms(unittest.TestCase):
    def test_form_limits_are_structured_not_notes(self):
        self.assertEqual(STANDARD["magnesium_mg"]["limits"], [{"basis": "magnesium_added_mg", "ul": 250}])
        self.assertEqual(STANDARD["folate_ug"]["limits"], [{"basis": "folic_acid_ug", "ul": 1000}])
        self.assertEqual(STANDARD["vitA_rae_ug"]["limits"], [{"basis": "retinol_ug", "ul": 3000}])
        self.assertIsNone(STANDARD["vitA_rae_ug"]["ul"])
        self.assertEqual({x["basis"] for x in STANDARD["niacin_mg"]["limits"]}, {"nicotinamide_mg", "nicotinic_acid_mg"})


class SupplementalLimits(unittest.TestCase):
    def test_magnesium_supplement_above_limit_is_flagged(self):
        res, r = row(with_targets(magnesium_mg={"supplement": 1000}), "magnesium_mg")
        self.assertTrue(r["status"].startswith("ABOVE UL"), r["status"])
        self.assertTrue(any(f.startswith("micro magnesium_mg: ABOVE UL") for f in res["checks"]["flags"]))

    def test_food_magnesium_alone_does_not_trigger_supplement_limit(self):
        _, r = row(with_targets(), "magnesium_mg")   # ~500 mg from food, no supplement
        self.assertFalse(r["status"].startswith("ABOVE UL"))

    def test_folate_supplement_of_unknown_form_is_unresolved(self):
        res, r = row(with_targets(folate_ug={"supplement": 2000}), "folate_ug")
        self.assertIn("UL unresolved", r["status"])
        self.assertNotEqual(r["status"], "ok")

    def test_folic_acid_supplement_above_limit_is_flagged(self):
        _, r = row(with_targets(folate_ug={"supplement": 2000, "supplement_forms": {"folic_acid_ug": 2000}}), "folate_ug")
        self.assertTrue(r["status"].startswith("ABOVE UL"))

    def test_methylfolate_supplement_is_not_folic_acid(self):
        _, r = row(with_targets(folate_ug={"supplement": 2000, "supplement_forms": {"folic_acid_ug": 0}}), "folate_ug")
        self.assertFalse(r["status"].startswith("ABOVE UL"))
        self.assertNotIn("unresolved", r["status"])


class PreformedVitaminA(unittest.TestCase):
    def test_carotenoid_only_plant_food_is_not_above_ul(self):
        _, r = row(with_test_food({"vitA_rae_ug": 4000}, origin="plant"), "vitA_rae_ug")
        self.assertFalse(r["status"].startswith("ABOVE UL"))
        self.assertNotIn("unresolved", r["status"])

    def test_unknown_origin_leaves_limit_unresolved(self):
        _, r = row(with_test_food({"vitA_rae_ug": 4000}), "vitA_rae_ug")
        self.assertIn("UL unresolved", r["status"])

    def test_tiny_amount_of_unknown_food_still_unresolved(self):
        """Review on PR #30: 0.1 g of food with unknown retinol is ≤ 0.1 % of the day's mass, which mshare drops."""
        p = with_test_food({"vitA_rae_ug": 4000}, grams=0.1)
        res, r = row(p, "vitA_rae_ug")
        share = max(res["days"][d]["total"]["mshare"].get("retinol_ug", 0) for d in M.WEEKDAYS)
        self.assertEqual(share, 0)                         # the display share hides it …
        self.assertIn("UL unresolved", r["status"])        # … the limit check does not

    def test_preformed_retinol_above_limit_is_flagged(self):
        _, r = row(with_test_food({"vitA_rae_ug": 4000, "retinol_ug": 4000}, origin="animal"), "vitA_rae_ug")
        self.assertTrue(r["status"].startswith("ABOVE UL"))


class UnknownAnimalSource(unittest.TestCase):
    def test_animal_food_without_retinol_value_is_unresolved_when_limit_exists(self):
        p = with_targets()   # example casein: animal origin, no vitamin A value
        _, r = row(p, "vitA_rae_ug")
        self.assertIn("UL unresolved", r["status"])


class LegacyTotalLimit(unittest.TestCase):
    def test_total_ul_still_applies(self):
        _, r = row(with_targets(vitD_ug={"supplement": 150}), "vitD_ug")
        self.assertTrue(r["status"].startswith("ABOVE UL"))


if __name__ == "__main__":
    unittest.main()
