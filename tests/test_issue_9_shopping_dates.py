"""Issue #9: purchases must happen before use, and food must be used within its shelf life."""
import copy, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M


def plan(fresh_runs, shelf=1, pack=100, carry=True, weeks=1, sessions=None, recipes=None, extra_days=None):
    leaf = {"name": "Leaves", "unit": "g", "per100": {"kcal": 20, "protein_g": 2, "fat_g": 0, "satfat_g": 0, "carb_g": 2,
            "sugar_g": 1, "fiber_g": 1, "salt_g": 0}, "allergens": [], "may_contain": [],
            "shop": {"buy": "fresh", "pack_size": pack, "pack_unit": "g", "price": 1, "shelf_days": shelf, "carry": carry}}
    day = {"type": "training", "meals": [{"name": "Salad", "parts": [{"ingredient": "leaf", "amount": 100}]}]}
    p = {"meta": {"name": "t", "bw_kg": 70, "allergies": {"status": "none"}}, "targets": {},
         "ingredients": {"leaf": leaf}, "recipes": recipes or {},
         "days": {d: copy.deepcopy(day) for d in M.WEEKDAYS},
         "cycle": {"weeks": weeks, "start_date": "2026-11-02", "sessions": sessions or []},
         "shopping": {"fresh_runs": fresh_runs}}
    for d, meals in (extra_days or {}).items():
        p["days"][d]["meals"] += meals
    return p


ALL = M.WEEKDAYS


class PurchaseTiming(unittest.TestCase):
    def test_issue_reproduction_is_flagged(self):
        sh = M.shopping(plan([{"day": "Fri", "covers": ALL}]))
        w = " | ".join(sh["warnings"])
        self.assertIn("Leaves: needed on 2026-11-02, 2026-11-03, 2026-11-04, 2026-11-05 but only bought on 2026-11-06", w)
        self.assertIn("Leaves: used on 2026-11-08, past its 1-day shelf life", w)

    def test_prior_week_run_within_shelf_life_is_clean(self):
        sh = M.shopping(plan([{"day": "Sat", "prior": True, "covers": ["Mon"]},
                              {"day": "Mon", "covers": ["Tue"]}, {"day": "Tue", "covers": ["Wed"]},
                              {"day": "Wed", "covers": ["Thu"]}, {"day": "Thu", "covers": ["Fri"]},
                              {"day": "Fri", "covers": ["Sat"]}, {"day": "Sat", "covers": ["Sun"]}], shelf=2))
        self.assertEqual(sh["warnings"], [])

    def test_prior_week_run_past_shelf_life_is_flagged(self):
        sh = M.shopping(plan([{"day": "Sat", "prior": True, "covers": ALL}], shelf=3))
        self.assertTrue(any("past its 3-day shelf life" in w for w in sh["warnings"]))

    def test_two_fresh_runs_cover_a_short_shelf_life(self):
        sh = M.shopping(plan([{"day": "Sat", "prior": True, "covers": ["Mon", "Tue", "Wed"]},
                              {"day": "Wed", "covers": ["Thu", "Fri", "Sat", "Sun"]}], shelf=4))
        self.assertEqual(sh["warnings"], [])

    def test_example_plan_has_no_shopping_warnings(self):
        sh = M.shopping(M.load(os.path.join(ROOT, "assets", "example_plan.json")))
        self.assertEqual(sh["warnings"], [])


class Leftovers(unittest.TestCase):
    def test_expired_leftovers_are_not_reused(self):
        # 500 g packs, 100 g a day, 3-day shelf life. Monday's pack (expires Thursday) covers Mon–Thu, so the
        # Wednesday run buys nothing; its last 100 g has expired by Friday, so Friday needs a new pack.
        runs = [{"day": "Mon", "covers": ["Mon", "Tue"]}, {"day": "Wed", "covers": ["Wed", "Thu"]},
                {"day": "Fri", "covers": ["Fri", "Sat", "Sun"]}]
        sh = M.shopping(plan(runs, shelf=3, pack=500), cycles=2)
        packs = [i["packs"] for r in sh["runs"] if r["kind"] == "fresh" for i in r["items"]]
        self.assertEqual(packs, [1, 0, 1])
        self.assertEqual(sh["warnings"], [])

    def test_usable_leftovers_are_reused(self):
        runs = [{"day": "Mon", "covers": ["Mon", "Tue"]}, {"day": "Wed", "covers": ["Wed", "Thu"]}]
        sh = M.shopping(plan(runs, shelf=10, pack=500), cycles=1)
        packs = [i["packs"] for r in sh["runs"] if r["kind"] == "fresh" for i in r["items"]]
        self.assertEqual(packs, [1, 0])        # Wednesday uses Monday's leftover 300 g (still fresh)


class BatchIngredients(unittest.TestCase):
    def test_batch_ingredient_bought_on_cook_day_is_clean(self):
        onion = {"name": "Onion", "unit": "g", "per100": {"kcal": 40, "protein_g": 1, "fat_g": 0, "satfat_g": 0, "carb_g": 8,
                 "sugar_g": 4, "fiber_g": 2, "salt_g": 0}, "allergens": [], "may_contain": [],
                 "shop": {"buy": "batch", "pack_size": 1000, "price": 1, "shelf_days": 30}}
        recipes = {"stew": {"title": "Stew", "kind": "batch", "portions": 7, "items": [["onion", 700]]}}
        p = plan([{"day": "Sat", "prior": True, "covers": ALL}], shelf=10, recipes=recipes,
                 sessions=[{"label": "Sun", "day": "Sun", "prior": True, "cook": {"stew": 1}}],
                 extra_days={d: [{"name": "Stew", "parts": [{"recipe": "stew"}]}] for d in ALL})
        p["ingredients"]["onion"] = onion
        sh = M.shopping(p)
        self.assertEqual(sh["warnings"], [])
        batch = next(r for r in sh["runs"] if r["kind"] == "batch")
        self.assertEqual(batch["date"], "2026-11-01")


class EarlierLotsServeEarlierDays(unittest.TestCase):
    def test_lot_expiring_before_the_next_purchase_still_serves_covered_earlier_days(self):
        """Review on PR #32: Monday's 500 g (3-day shelf life) supplies Tue–Thu even though the run that
        covers those days is only on Friday — only Fri–Sun need the new purchase."""
        sh = M.shopping(plan([{"day": "Mon", "covers": ["Mon"]},
                              {"day": "Fri", "covers": ["Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}], shelf=3, pack=500))
        self.assertEqual(sh["warnings"], [])
        fri = next(r for r in sh["runs"] if r["day"] == "Fri")
        self.assertEqual(fri["items"][0]["packs"], 1)      # 300 g for Fri–Sun

    def test_days_past_the_old_lot_are_still_flagged(self):
        sh = M.shopping(plan([{"day": "Mon", "covers": ["Mon"]},
                              {"day": "Sat", "covers": ["Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}], shelf=3, pack=500))
        w = " | ".join(sh["warnings"])
        self.assertIn("needed on 2026-11-06 but only bought on 2026-11-07", w)   # Friday: old lot expired Thursday
        self.assertNotIn("2026-11-05", w)


if __name__ == "__main__":
    unittest.main()
