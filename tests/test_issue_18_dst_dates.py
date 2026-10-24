"""Issue #18: repeating shop dates are calendar dates — stable across daylight-saving changes."""
import copy, datetime as dt, json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mealplan as M
import render_pages as R

try:
    from playwright.sync_api import sync_playwright
    HAVE = True
except Exception:
    HAVE = False


def shopping_page(tmp):
    with open(os.path.join(ROOT, "assets", "example_plan.json"), encoding="utf-8") as f:
        p = json.load(f)
    p["cycle"]["start_date"] = "2026-10-19"                       # Monday; DST ends in Europe on 2026-10-25
    p["shopping"]["stock_run"] = {"day": "Mon", "prior": False, "label": "Stock-up"}
    p["shopping"]["fresh_runs"] = [{"day": "Mon", "covers": M.WEEKDAYS, "label": "Fresh run"}]
    comp = json.loads(json.dumps(M.compute(p), default=M._json_default))
    sd = R.shopping_data(p, comp)
    path = os.path.join(tmp, "shopping-list.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(R.fill("shopping_list.html", sd["title"], sd, R.ACCENTS[3]))
    return path, sd


@unittest.skipUnless(HAVE, "Playwright not installed")
class CalendarDates(unittest.TestCase):
    ZONES = ("Europe/Berlin", "America/New_York", "Australia/Sydney", "UTC")

    def run_in(self, tz, path, expr, clock=None):
        with sync_playwright() as pw:
            try:
                b = pw.chromium.launch()
            except Exception as e:
                self.skipTest(f"Chromium not available: {e}")
            ctx = b.new_context(timezone_id=tz)
            page = ctx.new_page()
            if clock:
                page.clock.set_fixed_time(clock)
            page.goto("file://" + path)
            out = page.evaluate(expr)
            b.close()
            return out

    def test_first_run_is_the_sunday_cook_day_shop(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, sd = shopping_page(tmp)
            self.assertEqual(sd["runs"][0]["date"], "2026-10-18")   # batch shop on the Sunday before week 1

    def test_cycle_shift_keeps_the_calendar_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = shopping_page(tmp)
            for tz in self.ZONES:
                got = self.run_in(tz, path, """[
                    fromDayNum(dayNum('2026-10-19') + 28).toDateString(),          // the issue's example (autumn change)
                    shift(S.runs[0].date, 2).toDateString(),                       // first run of cycle 2
                    fromDayNum(dayNum('2027-03-22') + 28).toDateString(),          // spring change (Europe, US)
                    fromDayNum(dayNum('2026-09-28') + 28).toDateString(),          // spring change (Sydney)
                    fromDayNum(shiftNum(S.runs[0].date, 2) + 27).toDateString()    // last day of cycle 2
                ]""")
                self.assertEqual(got, ["Mon Nov 16 2026", "Sun Nov 15 2026", "Mon Apr 19 2027", "Mon Oct 26 2026",
                                       "Sat Dec 12 2026"], tz)

    def test_cycle_selection_at_a_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = shopping_page(tmp)
            # cycle 2 starts Sunday 15 Nov. 00:30 local time in Berlin is still 14 Nov in UTC: must be cycle 2 locally
            clock = dt.datetime(2026, 11, 14, 23, 30, tzinfo=dt.timezone.utc)
            got = self.run_in("Europe/Berlin", path, "[cycleOf(todayNum), state.cycle, document.querySelector('details.next .date').textContent]",
                              clock=clock)
            self.assertEqual(got[0], 2)
            self.assertEqual(got[1], 2)
            self.assertIn("15", got[2])
            self.assertIn("Sun", got[2])


if __name__ == "__main__":
    unittest.main()
