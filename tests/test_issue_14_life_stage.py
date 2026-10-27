"""Issue #14: life stages the adult table does not cover must not silently get adult targets."""
import json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import targets

ADULT = {"sex": "female", "age": 30, "height_cm": 165, "weight_kg": 60}


class Routing(unittest.TestCase):
    def test_adolescent_is_routed_away(self):
        r = targets.compute(dict(ADULT, age=17))
        self.assertFalse(r["supported"])
        self.assertNotIn("targets", r)                    # no 1,000 mg adult calcium etc.
        self.assertIn("1,200 mg", r["reason"])

    def test_pregnancy_is_routed_away(self):
        r = targets.compute(dict(ADULT, pregnant=True))
        self.assertFalse(r["supported"])
        self.assertNotIn("targets", r)
        self.assertIn("550", r["reason"])

    def test_breastfeeding_is_routed_away(self):
        r = targets.compute(dict(ADULT, breastfeeding=True))
        self.assertFalse(r["supported"])
        self.assertIn("450", r["reason"])

    def test_older_adult_is_marked_approximate(self):
        r = targets.compute(dict(ADULT, age=70))
        self.assertTrue(r["supported"])
        self.assertEqual(r["population"], "approximate")
        self.assertTrue(any("65+" in n for n in r["notes"]))

    def test_eighteen_year_old_is_in_the_adolescent_band(self):
        """Review on PR #37: age 18 belongs to D-A-CH 15–<19, not 19–<25, and calcium is 1,200 mg there."""
        r = targets.compute(dict(ADULT, age=18))
        self.assertTrue(r["supported"])
        self.assertEqual(r["population"], "approximate")
        notes = " ".join(r["notes"])
        self.assertIn("15–<19", notes)
        self.assertNotIn("19–<25", notes)
        ca = r["targets"]["micros"]["calcium_mg"]
        self.assertEqual((ca["floor"], ca["aim"]), (1200, 1200))
        r = targets.compute(dict(ADULT, age=19))
        self.assertIn("19–<25", " ".join(r["notes"]))
        self.assertEqual(r["targets"]["micros"]["calcium_mg"]["floor"], 1000)

    def test_core_adult_is_exact(self):
        r = targets.compute(ADULT)
        self.assertEqual(r["population"], "exact")
        self.assertIn("25–<51", r["reference_population"])

    def test_missing_age_or_sex_is_an_error(self):
        with self.assertRaises(ValueError):
            targets.compute({k: v for k, v in ADULT.items() if k != "age"})
        with self.assertRaises(ValueError):
            targets.compute({k: v for k, v in ADULT.items() if k != "sex"})

    def test_cli_exit_code_for_unsupported(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(dict(ADULT, age=16), f)
        p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "targets.py"), f.name], capture_output=True, text=True)
        os.unlink(f.name)
        self.assertEqual(p.returncode, 2)
        self.assertIn("Not supported", p.stdout)


if __name__ == "__main__":
    unittest.main()
