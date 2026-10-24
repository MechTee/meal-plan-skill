"""Issue #10: the recurring budget is what is actually paid, including packs that are thrown away."""
import copy, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M


def plan(per_day_g=100, pack=1000, price=10.0, carry=True, shelf=None, buy="stock"):
    shop = {"buy": buy, "pack_size": pack, "pack_unit": "g", "price": price, "carry": carry}
    if shelf:
        shop["shelf_days"] = shelf
    food = {"name": "Food", "unit": "g", "per100": {"kcal": 100, "protein_g": 5, "fat_g": 1, "satfat_g": 0, "carb_g": 15,
            "sugar_g": 1, "fiber_g": 2, "salt_g": 0}, "allergens": [], "may_contain": [], "shop": shop}
    day = {"type": "training", "meals": [{"name": "M", "parts": [{"ingredient": "food", "amount": per_day_g}]}]}
    return {"meta": {"name": "t", "bw_kg": 70, "allergies": {"status": "none"}}, "targets": {},
            "ingredients": {"food": food}, "recipes": {}, "days": {d: copy.deepcopy(day) for d in M.WEEKDAYS},
            "cycle": {"weeks": 1, "start_date": "2026-11-02", "sessions": []},
            "shopping": {"stock_run": {"day": "Mon"}, "fresh_runs": [{"day": "Mon", "covers": M.WEEKDAYS}]}}


class Budget(unittest.TestCase):
    def test_issue_reproduction_no_carry_costs_a_full_pack_every_week(self):
        sh = M.shopping(plan(carry=False))            # 700 g a week from 1 000 g packs at €10, leftovers discarded
        item = sh["runs"][0]["items"][0]
        self.assertEqual(item["packs_by_cycle"], [1, 1, 1, 1])
        self.assertEqual(sh["weekly_cost"], 10.0)
        self.assertEqual(sh["cycle_cost"], 10.0)
        self.assertEqual(sh["consumed_value_per_cycle"], 7.0)
        self.assertEqual(sh["waste_per_cycle"], 3.0)

    def test_with_carry_over_the_budget_approaches_consumption(self):
        sh = M.shopping(plan(carry=True))
        # 7 packs every 10 weeks; a finite simulation can end with up to one pack in stock (≤ €10 / 12 cycles)
        self.assertAlmostEqual(sh["weekly_cost"], 7.0, delta=1.0)
        self.assertLess(sh["waste_per_cycle"], 1.0)

    def test_expiry_waste_is_in_the_budget(self):
        sh = M.shopping(plan(carry=True, shelf=6, buy="fresh"))      # leftovers expire before next week's run
        self.assertEqual(sh["weekly_cost"], 10.0)

    def test_report_names_cost_and_waste(self):
        p = plan(carry=False)
        text = M.report(p, M.compute(p))
        self.assertIn("Recurring cost ≈ 10.00 per cycle", text)
        self.assertIn("thrown away ≈ 3.00", text)


class ReviewFollowUp(unittest.TestCase):
    """Review on PR #33."""
    def test_slow_mover_keeps_its_share(self):
        sh = M.shopping(plan(per_day_g=10, pack=1000, price=10.0))   # one pack lasts ~14 weeks
        self.assertEqual(sh["weekly_cost"], 0.7)
        self.assertEqual(sh["waste_per_cycle"], 0.0)

    def test_carried_stock_is_not_waste(self):
        sh = M.shopping(plan(per_day_g=90, pack=1000, price=100.0))   # never discarded, only carried
        self.assertEqual(sh["waste_per_cycle"], 0.0)
        self.assertEqual(sh["cycle_cost"], 63.0)

    def test_slow_mover_with_shelf_life_counts_expiry(self):
        # 70 g a week (drawn at each weekly run), 1 000 g pack usable until day 28: five weekly draws
        # (days 0–28) use 350 g, the other 650 g is thrown away — one €10 pack every five weeks
        sh = M.shopping(plan(per_day_g=10, pack=1000, price=10.0, shelf=28))
        self.assertGreater(sh["budget_cycles_simulated"], 13)
        self.assertAlmostEqual(sh["waste_per_cycle"], 1.3, delta=0.05)
        self.assertAlmostEqual(sh["weekly_cost"], 2.0, delta=0.05)


if __name__ == "__main__":
    unittest.main()
