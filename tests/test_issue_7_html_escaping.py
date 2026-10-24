"""Issue #7: plan strings are data — they must never become markup or script in generated pages."""
import copy, json, os, re, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M
import render_pages as R

PROBE = 'Oats "><img src=x onerror="window.__ingredientInjection=1">'
QUOTES = "Mum's \"special\" <b>oats</b> & co"
SCRIPT_CLOSE = "</script><script>window.__scriptInjection=1</script>"

# Interpolations in template literals that are internal values (constants, loop indices, numbers
# computed in the page, or HTML already built from esc()). Anything else must go through
# esc()/num()/fmt()/money(). Adding a new entry here needs a reason.
INTERNAL = {
    "recipe_page.html": {"Math.floor(left/60)", "Math.min(n.nitrate_mg/800*100,100)", "Math.min(pct,100)", "NAMES[sc.limiting]",
                         'String(left%60).padStart(2,"0")', "ce/t*100", "dCls", "fe/t*100", "i+1", "inner", "lCls", "label", "m", "pCls",
                         "pe/t*100", "rows", "s", "shown", "w", "n===state.variant", 'on?" done":""', 'on?"checked":""',
                         'k===sc.limiting && s<100 ?"lim":""', 'shown==="–"?"no data":fmt(pct)+" %"', "i",
                         'D.aaNote ? " " + esc(D.aaNote) : ""'},   # escaped inside the conditional
    "shopping_list.html": {"W", "b.dataset.clear", "bits.join(\" · \")", "body", "c", "c===state.cycle", "cb.dataset.run", "done",
                           "fmtDate(r.d)", 'isDone?" done":""', 'isNext?" next":""', "items.length", "items.length?done/items.length*100:0",
                           "k", "k===state.filter", "l", 'on?" done":""', 'on?"checked":""', "open", "qty", "r.id", 'skip?"disabled":""',
                           'skip?"skip":""', "state.cycle", "sub",
                           # dates formatted by the browser from Date objects; numbers coerced with num()
                           'a.toLocaleDateString(S.locale||"en-GB",{day:"numeric",month:"short"})',
                           'b.toLocaleDateString(S.locale||"en-GB",{day:"numeric",month:"short"})',
                           "Math.round(num(it.need))", "Math.round(num(it.need)).toLocaleString()",
                           'r.store?" · "+esc(r.store):""', "isNext?'<span class=\"tag next\">next</span>':''"},
}


def interpolations(text):
    text = text[text.index("<script>"):]
    out, i = [], 0
    while (j := text.find("${", i)) >= 0:
        depth, k = 0, j + 2
        while not (text[k] == "}" and depth == 0):
            depth += {"{": 1, "}": -1}.get(text[k], 0)
            k += 1
        out.append(text[j + 2:k])
        i = k
    return out


class TemplateAudit(unittest.TestCase):
    def test_every_interpolation_is_escaped_or_internal(self):
        safe = re.compile(r"\s*(esc|num|fmt|money)\(")
        for name, allowed in INTERNAL.items():
            with open(os.path.join(ROOT, "assets", name), encoding="utf-8") as f:
                exprs = interpolations(f.read())
            for e in exprs:
                if safe.match(e) or e in allowed:
                    continue
                # nested templates: their own ${} are checked separately; the outer conditional is fine if it only
                # chooses between "" and a template literal
                if re.fullmatch(r"[\w.\s>]+\?\s*`.*`\s*:\s*\"\"", e, re.S) or "esc(" in e and "`" in e:
                    continue
                self.fail(f"{name}: unescaped interpolation ${{{e}}}")

    def test_esc_covers_quotes_and_links_are_restricted(self):
        for name in INTERNAL:
            with open(os.path.join(ROOT, "assets", name), encoding="utf-8") as f:
                t = f.read()
            self.assertIn('"\'":"&#39;"', t)
            self.assertIn("safeUrl", t)
            self.assertNotRegex(t, r'href="\$\{esc\((?!safeUrl)')


def hostile_plan():
    with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
        p = json.load(f)
    p["ingredients"]["oats"]["name"] = PROBE
    p["ingredients"]["pumpkin"]["name"] = QUOTES
    p["ingredients"]["oats"]["unit"] = "g"
    p["ingredients"]["chia"]["shop"]["link"] = "javascript:window.__linkInjection=1"
    p["ingredients"]["hemp"]["shop"]["pack_label"] = SCRIPT_CLOSE
    r = p["recipes"]["oat_bowl"]
    r["title"] = 'Bowl </title><img src=x onerror="window.__titleInjection=1">'
    r["steps"].append([PROBE, '5"><img src=x onerror="window.__stepInjection=1">'])
    r["notes"].append(SCRIPT_CLOSE)
    p["meta"]["sources"] = [["evil", "javascript:window.__srcInjection=1"], ["ok", "https://fdc.nal.usda.gov/"]]
    return p


class RenderedData(unittest.TestCase):
    def test_script_data_cannot_close_the_script_element(self):
        p = hostile_plan()
        comp = json.loads(json.dumps(M.compute(p), default=M._json_default))
        html = R.fill("recipe_page.html", p["recipes"]["oat_bowl"]["title"], R.recipe_data(p, comp, "oat_bowl"), R.ACCENTS[0])
        script = html[html.index("const D = "):]
        script = script[:script.index("\n")]
        self.assertNotIn("<", script)
        self.assertNotIn(">", script)
        self.assertNotIn("<img", html[:html.index("<body>")])


try:
    from playwright.sync_api import sync_playwright
    HAVE_BROWSER = True
except Exception:
    HAVE_BROWSER = False


@unittest.skipUnless(HAVE_BROWSER, "Playwright not installed")
class BrowserProbe(unittest.TestCase):
    def test_no_executable_element_is_created(self):
        p = hostile_plan()
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = os.path.join(tmp, "plan.json")
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(p, f)
            sys.argv = ["render_pages.py", plan_path, tmp]
            R.main()
            with sync_playwright() as pw:
                try:
                    browser = pw.chromium.launch()
                except Exception as e:  # no browser binary
                    self.skipTest(f"Chromium not available: {e}")
                for page_name in ("oat_bowl.html", "shopping-list.html"):
                    page = browser.new_page()
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto("file://" + os.path.join(tmp, page_name))
                    if page_name == "shopping-list.html":
                        page.click("text=All runs")
                        page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
                    page.wait_for_timeout(300)
                    flags = page.evaluate("['__ingredientInjection','__titleInjection','__stepInjection','__scriptInjection',"
                                          "'__linkInjection','__srcInjection'].filter(k => window[k])")
                    self.assertEqual(flags, [], page_name)
                    self.assertEqual(page.evaluate("document.querySelectorAll('img, script:not(:first-of-type)').length"), 0, page_name)
                    self.assertEqual(page.evaluate("[...document.querySelectorAll('a[href]')].filter(a => !/^https?:/.test(a.href)).length"), 0)
                    self.assertEqual(errors, [], page_name)
                    if page_name == "oat_bowl.html":
                        text = page.inner_text("#ing")
                        self.assertIn('onerror="window.__ingredientInjection=1"', text)   # shown literally
                        self.assertIn(QUOTES, text)
                        self.assertIn(SCRIPT_CLOSE, page.inner_text("#notes"))
                browser.close()


if __name__ == "__main__":
    unittest.main()
