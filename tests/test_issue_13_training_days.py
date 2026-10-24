"""Issue #13: sessions per week are not training days; day targets must rebuild the weekly budget."""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import targets

BASE = {"sex": "female", "age": 30, "height_cm": 165, "weight_kg": 60, "goal": "maintain"}
RUN = {"type": "running_easy", "minutes": 60}
LIFT = {"type": "resistance_vigorous", "minutes": 60}


def weekly(r):
    t = r["targets"]
    n = r["training_days"]
    return n * t["training"]["kcal"] + (7 - n) * t["rest"]["kcal"]


class TrainingDays(unittest.TestCase):
    def assertRebuildsWeek(self, r):
        # day targets are rounded to 50 kcal: allow 25 kcal per day
        self.assertAlmostEqual(weekly(r), 7 * (r["tdee"]["avg"] + r["goal_adjust_kcal"]), delta=7 * 25 + 1)

    def test_issue_reproduction_separate_days(self):
        p = dict(BASE, sessions=[dict(RUN, per_week=3, days=["Mon", "Wed", "Fri"]),
                                 dict(LIFT, per_week=3, days=["Tue", "Thu", "Sat"])])
        r = targets.compute(p)
        self.assertEqual(r["session_kcal"], [438, 240])
        self.assertEqual(r["training_days"], 6)
        self.assertRebuildsWeek(r)
        self.assertLess(r["targets"]["training"]["kcal"], 2450)      # the old 3-day assumption gave 2,450

    def test_doubles_on_the_same_days(self):
        p = dict(BASE, sessions=[dict(RUN, days=["Mon", "Wed", "Fri"]), dict(LIFT, days=["Mon", "Wed", "Fri"])])
        r = targets.compute(p)
        self.assertEqual(r["training_days"], 3)
        self.assertRebuildsWeek(r)

    def test_training_days_count_from_profile(self):
        r = targets.compute(dict(BASE, training_days=6, sessions=[dict(RUN, per_week=3), dict(LIFT, per_week=3)]))
        self.assertEqual(r["training_days"], 6)
        self.assertRebuildsWeek(r)

    def test_twice_daily_needs_training_days(self):
        with self.assertRaises(ValueError):
            targets.compute(dict(BASE, sessions=[dict(LIFT, per_week=10)]))
        r = targets.compute(dict(BASE, training_days=5, sessions=[dict(LIFT, per_week=10)]))
        self.assertEqual(r["training_days"], 5)
        self.assertRebuildsWeek(r)

    def test_invalid_training_days_are_rejected(self):
        for bad in (8, -1, 0):
            with self.assertRaises(ValueError, msg=bad):
                targets.compute(dict(BASE, training_days=bad, sessions=[dict(RUN, per_week=3), dict(LIFT, per_week=3)]))
        with self.assertRaises(ValueError):   # more training days than sessions to put on them
            targets.compute(dict(BASE, training_days=5, sessions=[dict(RUN, per_week=3), dict(LIFT, per_week=1)]))
        with self.assertRaises(ValueError):
            targets.compute(dict(BASE, sessions=[dict(RUN, days=["Mon", "Funday"])]))

    def test_ambiguous_mix_is_assumed_and_said(self):
        r = targets.compute(dict(BASE, sessions=[dict(RUN, per_week=3), dict(LIFT, per_week=3)]))
        self.assertEqual(r["training_days"], 6)
        self.assertTrue(any(n.startswith("assumed 6 training days") for n in r["notes"]))
        self.assertRebuildsWeek(r)

    def test_single_type_unchanged(self):
        r = targets.compute(dict(BASE, sessions=[dict(LIFT, per_week=4)]))
        self.assertEqual(r["training_days"], 4)
        self.assertRebuildsWeek(r)

    def test_explicit_count_allows_low_frequency_doubles(self):
        """Review on PR #36: four sessions of one type on two days (twice-daily) with an explicit count."""
        r = targets.compute(dict(BASE, training_days=2, sessions=[dict(LIFT, per_week=4)]))
        self.assertEqual(r["training_days"], 2)
        self.assertRebuildsWeek(r)
        r = targets.compute(dict(BASE, training_days=2, sessions=[dict(RUN, per_week=3), dict(LIFT, per_week=1)]))
        self.assertEqual(r["training_days"], 2)
        self.assertRebuildsWeek(r)

    def test_fractional_frequency_keeps_its_energy(self):
        """Review on PR #36: one 120-minute easy run every two weeks must not vanish from the day split."""
        r = targets.compute(dict(BASE, sessions=[dict(RUN, minutes=120, per_week=0.5)]))
        self.assertEqual(r["training_days"], 1)
        self.assertGreater(r["targets"]["training"]["kcal"], r["targets"]["rest"]["kcal"])
        self.assertRebuildsWeek(r)
        self.assertIn("fractional", r["training_day_basis"])
        r = targets.compute(dict(BASE, sessions=[dict(RUN, per_week=2.5), dict(LIFT, per_week=2)]))
        self.assertEqual(r["training_days"], 5)
        self.assertRebuildsWeek(r)


if __name__ == "__main__":
    unittest.main()
