# athlete-meal-plan

A Claude skill that turns a conversation into a complete, cookable meal plan for an athlete:
an interview where the athlete picks the depth of each topic, evidence-based calorie, macro and
micronutrient targets, a draft plan to approve, and then a coordinated set of outputs that are all
generated from one data file:

- a formula-driven **Excel workbook** (week summary, micronutrients, essential amino acids,
  ingredient database, one sheet per day)
- a **dated shopping list** with stock-up, batch-shop and fresh runs, bought in whole packs after
  using up leftovers
- **batch-cooking recipe pages** plus a cook-day page for each cooking session
- **recipe handout pages** for everything made fresh (breakfast, shakes, salad, pre-workout drink)

It grew out of a real vegetarian lean-gain plan built over several weeks with Claude, and encodes
the lessons from that: per-dish batch balancing, freezer limits, supplements counted toward
nutrient totals, label values over generic database values, and one source of truth so the
spreadsheet, shopping list and recipes never drift apart.

## How it works

| Phase | What happens |
|---|---|
| 1 · Gather | Reads what is already known (memory, project docs, earlier artifacts, an existing workbook) and turns it into defaults to confirm. |
| 2 · Interview | A depth picker for seven topics: goal, body composition, training and lifestyle, preferences and restrictions, cooking, the pre-workout process, sourcing and shopping. Each can be skipped or answered quick, standard or in depth. A short safety screen always runs. |
| 3 · Targets | `targets.py` computes BMR, maintenance for training and rest days, goal adjustment, protein/carbs/fat per day type, and three levels per micronutrient: floor (D-A-CH reference), athlete aim, and EFSA upper limit. |
| 4 · Scratchpad | A draft plan is checked by `mealplan.py` (targets, micros, batch inventory, cost) and shown in the chat for approval. Changes are simulated and shown as before → after. |
| 5 · Harden | Generic values are replaced with label values, pack sizes and prices for the products the athlete actually buys. |
| 6 · Build | The workbook and HTML pages are generated from `plan.json`. |
| 7 · Verify | Formula recalculation with zero errors, workbook numbers cross-checked against the engine, pages rendered without errors. |

## Repository layout

```
SKILL.md                      instructions Claude follows (phases, rules, safety)
scripts/
  targets.py                  energy, macro and micronutrient targets from interview answers
  mealplan.py                 core engine: nutrients, amino-acid scores, batch inventory, shopping, checks
  build_workbook.py           Excel workbook with live formulas (openpyxl)
  render_pages.py             recipe pages, cook-day pages, shopping list (HTML + markdown)
  recalc.py                   recalculate the workbook with headless LibreOffice and list formula errors
  check_workbook.py           cross-check a recalculated workbook against the engine
assets/
  recipe_page.html            cooking-page template (timers, tick boxes, amino acids, micro footer)
  shopping_list.html          shopping-list template (dated runs, cycles, per-run ticks, costs)
  example_plan.json           complete worked example plan
references/
  interview.md                question bank per topic and depth
  nutrition.md                formulas, reference values, pre-workout evidence and doses, sources
  plan-format.md              plan.json schema
  sourcing.md                 finding label values, packs and prices (with notes for Germany)
  artifacts.md                output specs and the scratchpad template
evals/                        model-level test cases in the `claude plugin eval` layout
tests/                        script regression tests (python3 -m unittest discover tests)
requirements.txt              Python dependencies
```

## Running the scripts directly

Requires Python 3.10+ and `openpyxl` (`pip install -r requirements.txt`). Optional:
LibreOffice for recalculating and error-checking the workbook, Playwright for page screenshots.

```bash
# targets from an interview profile (fields are listed in the script's docstring)
python3 scripts/targets.py profile.json targets.json

# check a plan: day totals vs targets, micronutrients, batch balance, cost, flags
python3 scripts/mealplan.py check assets/example_plan.json

# build the workbook and the pages
python3 scripts/build_workbook.py assets/example_plan.json Meal_Plan_Macros.xlsx
python3 scripts/recalc.py Meal_Plan_Macros.xlsx
python3 scripts/check_workbook.py assets/example_plan.json Meal_Plan_Macros.xlsx
python3 scripts/render_pages.py assets/example_plan.json pages/
```

The engine simulates several cooking cycles, so it reports per-dish shortfalls and spares, peak
freezer use, alternating pack purchases ("2 bags one cycle, 1 the next"), and both the first-cycle
cost at the till and the pro-rated weekly cost.

## Installing as a skill

The skill is the whole folder — `SKILL.md` alone is not enough, because the instructions call the
scripts, templates and references next to it. Everything it needs is in this repository; it does not
depend on any private project, connector or other skill.

**Claude Code**

```bash
git clone https://github.com/MechTee/meal-plan-skill ~/.claude/skills/athlete-meal-plan
pip install -r ~/.claude/skills/athlete-meal-plan/requirements.txt
```

(or clone into `.claude/skills/athlete-meal-plan` inside a project to scope it to that project).

**Claude apps (upload a skill)**

```bash
git clone https://github.com/MechTee/meal-plan-skill athlete-meal-plan
cd athlete-meal-plan && git archive --format=zip --prefix=athlete-meal-plan/ -o ../athlete-meal-plan.zip HEAD
```

Upload `athlete-meal-plan.zip` in the app's skill settings.

**Host differences.** The skill checks what the session can do and falls back when a tool is
missing: structured questions → numbered questions in chat; LibreOffice recalculation → workbook
delivered unrecalculated (it computes on open) with the numbers verified by the engine instead;
file or page publishing tools → files written to an `outputs/` folder; subagents → sequential
research.

**Check an install:** `python3 -m unittest discover tests` runs the script regression tests.

## Notes and limits

- Targets are starting estimates. The plan tells the athlete to adjust calories from the 7-day
  average weight after 2–3 weeks.
- `example_plan.json` uses generic composition values for illustration; it is not a verified plan.
- Reference values reflect D-A-CH and EFSA tables as known in 2026. The skill is told to confirm
  values it is unsure of against the current tables.
- Not a substitute for a dietitian or doctor. The skill has explicit rules for minors, signs of
  disordered eating, low energy availability, drug-tested athletes and medical conditions.
