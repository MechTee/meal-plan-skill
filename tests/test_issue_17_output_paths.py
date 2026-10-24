"""Issue #17: page file names come from plan keys but must stay inside the output directory."""
import copy, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import render_pages as R

with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
    BASE = json.load(f)


def rename_recipe(plan, old, new):
    p = copy.deepcopy(plan)
    p["recipes"] = {(new if k == old else k): v for k, v in p["recipes"].items()}
    for d in list(p["days"].values()) + [d for w in p.get("week_overrides", {}).values() for d in w.values()]:
        for m in d["meals"]:
            for part in m["parts"]:
                if part.get("recipe") == old:
                    part["recipe"] = new
    for s in p["cycle"]["sessions"]:
        if old in s["cook"]:
            s["cook"][new] = s["cook"].pop(old)
    return p


def render(plan, tmp):
    plan_path = os.path.join(tmp, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f)
    out = os.path.join(tmp, "pages")
    return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "render_pages.py"), plan_path, out],
                          capture_output=True, text=True), out


class Containment(unittest.TestCase):
    def test_traversal_key_is_written_inside(self):
        with tempfile.TemporaryDirectory() as tmp:
            victim = os.path.join(tmp, "escaped.html")
            with open(victim, "w") as f:
                f.write("original")
            p, out = render(rename_recipe(BASE, "salad", "../escaped"), tmp)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            with open(victim) as f:
                self.assertEqual(f.read(), "original")        # not overwritten
            self.assertTrue(os.path.exists(os.path.join(out, "escaped.html")))
            for line in p.stdout.split():
                self.assertTrue(os.path.realpath(line).startswith(os.path.realpath(out) + os.sep), line)

    def test_absolute_key_is_written_inside(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, out = render(rename_recipe(BASE, "salad", os.path.join(tmp, "abs")), tmp)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertFalse(os.path.exists(os.path.join(tmp, "abs.html")))

    def test_case_collision_is_rejected(self):
        plan = rename_recipe(BASE, "salad", "Dal")              # "Dal" and "dal" → same file
        with self.assertRaises(R.OutputError):
            R.plan_pages(plan)

    def test_reserved_and_cookday_collisions_are_rejected(self):
        with self.assertRaises(R.OutputError):
            R.plan_pages(rename_recipe(BASE, "salad", "shopping-list"))
        with self.assertRaises(R.OutputError):
            R.plan_pages(rename_recipe(BASE, "salad", "cook-sunday-a"))

    def test_safe_path_refuses_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(R.OutputError):
                R.safe_path(tmp, "../x", ".html")

    def test_example_names_unchanged(self):
        names = [n for _, _, n in R.plan_pages(BASE)]
        self.assertIn("oat_bowl", names)
        self.assertIn("cook-sunday-a", names)
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
