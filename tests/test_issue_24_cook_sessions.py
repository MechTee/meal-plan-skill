"""Issue #24: cook sessions are not identified by their display label."""
import copy, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M
import render_pages as R

with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
    BASE = json.load(f)


def labelled(*labels):
    p = copy.deepcopy(BASE)
    for s, lab in zip(p["cycle"]["sessions"], labels):
        s["label"] = lab
    return p


class SessionPages(unittest.TestCase):
    def test_issue_reproduction_same_label_keeps_both_sessions(self):
        pages = R.cookday_pages(labelled("Sunday", "Sunday"))
        self.assertEqual(len(pages), 2)
        a, b = pages
        self.assertIn("Red Lentil Dal", a["desc"])
        self.assertNotIn("Red Lentil Dal", b["desc"])
        self.assertEqual((a["when"], b["when"]), ("Sun · weeks 1, 3", "Sun · weeks 2, 4"))
        self.assertNotEqual(a["id"], b["id"])
        self.assertIn("weeks 1, 3", a["title"])

    def test_identical_definitions_are_grouped(self):
        p = copy.deepcopy(BASE)
        a = p["cycle"]["sessions"][0]
        a["weeks"] = [1]
        p["cycle"]["sessions"].append(dict(copy.deepcopy(a), weeks=[3]))
        pages = R.cookday_pages(p)
        a_pages = [x for x in pages if "Sunday A" in x["title"]]
        self.assertEqual(len(a_pages), 1)
        self.assertEqual(a_pages[0]["when"], "Sun · weeks 1, 3")
        self.assertEqual(len(a_pages[0]["session_ids"]), 2)

    def test_slug_collision_gets_distinct_files(self):
        pages = R.cookday_pages(labelled("Sunday A", "sunday-a"))
        self.assertEqual(len({p["id"] for p in pages}), 2)

    def test_example_names_unchanged(self):
        self.assertEqual([p["id"] for p in R.cookday_pages(BASE)], ["cook-sunday-a", "cook-sunday-b"])

    def test_duplicate_session_ids_are_rejected(self):
        p = copy.deepcopy(BASE)
        for s in p["cycle"]["sessions"]:
            s["id"] = "sunday"
        with self.assertRaises(M.PlanError):
            M.validate(p)

    def test_renderer_writes_both_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = os.path.join(tmp, "plan.json")
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(labelled("Sunday", "Sunday"), f)
            out = os.path.join(tmp, "pages")
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "render_pages.py"), plan_path, out],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(os.path.exists(os.path.join(out, "cook-sunday-wk1-3.html")))
            self.assertTrue(os.path.exists(os.path.join(out, "cook-sunday-wk2-4.html")))


if __name__ == "__main__":
    unittest.main()
