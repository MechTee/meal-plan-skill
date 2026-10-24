"""Issue #15: reference floors match the current DGE edition, carry their sources, and the version is visible."""
import json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M, targets

MALE = {"sex": "male", "age": 32, "height_cm": 187, "weight_kg": 87}
FEMALE = {"sex": "female", "age": 30, "height_cm": 165, "weight_kg": 60}


class CurrentValues(unittest.TestCase):
    def test_revised_entries(self):
        R = targets.REF
        self.assertEqual(R["phosphorus_mg"][:2], (550, 550))
        self.assertEqual(R["iodine_ug"][:2], (150, 150))
        self.assertEqual(R["vitE_mg"][:2], (8, 8))
        self.assertEqual(R["iron_mg"][:2], (11, 16))

    def test_representative_unchanged_entries(self):
        R = targets.REF
        self.assertEqual(R["calcium_mg"][:2], (1000, 1000))
        self.assertEqual(R["magnesium_mg"][:2], (350, 300))
        self.assertEqual(R["vitD_ug"][:2], (20, 20))
        self.assertEqual(R["b12_ug"][:2], (4.0, 4.0))

    def test_every_reference_has_a_dated_source(self):
        for k, v in targets.REF_DATA.items():
            if k == "nitrate_mg":
                continue
            src = targets.ref_source(k)
            self.assertTrue(src["url"].startswith("https://www.dge.de/wissenschaft/referenzwerte/"), k)
            self.assertIsInstance(src["derived"], int, k)
            self.assertIn(src["type"], ("recommendation", "estimated value"), k)

    def test_postmenopausal_iron(self):
        m = targets.compute(dict(FEMALE, menstruating=False))["targets"]["micros"]["iron_mg"]
        self.assertEqual(m["floor"], 14)


class FloorVsAim(unittest.TestCase):
    def test_floor_is_the_reference_and_aim_is_separate(self):
        m = targets.compute(MALE)["targets"]["micros"]
        self.assertEqual(m["iodine_ug"]["floor"], 150)
        self.assertEqual(m["vitE_mg"]["floor"], 8)
        self.assertEqual(m["phosphorus_mg"]["floor"], 550)
        self.assertEqual(m["magnesium_mg"]["floor"], 350)
        self.assertEqual(m["magnesium_mg"]["aim"], 420)          # athlete adjustment stays distinct
        self.assertEqual(m["iodine_ug"]["source"]["derived"], 2025)


class VersionVisible(unittest.TestCase):
    def test_targets_output_names_the_edition(self):
        r = targets.compute(MALE)
        self.assertIn("3rd edition (2025)", r["targets"]["reference"]["name"])
        self.assertIn("3rd edition (2025)", targets.summary(MALE, r))
        self.assertIn("dge.de/wissenschaft/referenzwerte/jod/", targets.summary(MALE, r))

    def test_plan_report_names_the_edition(self):
        p = M.load(os.path.join(ROOT, "assets", "example_plan.json"))
        self.assertIn("3rd edition (2025)", M.report(p, M.compute(p)))
        del p["targets"]["reference"]
        self.assertIn("reference version not recorded", M.report(p, M.compute(p)))


if __name__ == "__main__":
    unittest.main()
