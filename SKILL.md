---
name: athlete-meal-plan
description: Build a complete athlete meal plan from an interview the athlete controls the depth of, then calories, macros and micronutrient targets, a draft plan to approve, and the finished set - a formula-driven Excel workbook, a dated shopping list, batch-cooking recipes and recipe handouts. Use this whenever someone wants a meal plan, diet plan, meal prep or batch-cooking plan, macro or calorie targets with meals attached, a pre-workout / pump protocol with food, or a shopping list built from a training plan - for themselves or an athlete they coach - even if they only say "plan my food for training", "bulk/cut plan", or "meal prep for the gym".
---

# Athlete meal plan

You are building a plan an athlete will actually live with for weeks: they cook from it, shop from
it, and edit it. That shapes everything below. Numbers have to add up across files (the workbook,
the shopping list and the recipe pages are generated from one `plan.json`, never typed separately),
quantities follow real pack sizes, and the athlete approves a draft before anything is built.

The work runs in seven phases. Track them with the task list.

1. Gather what is already known
2. Depth picker + interview
3. Targets (energy, macros, micros)
4. Scratchpad plan → approval loop
5. Harden the data (labels, prices, packs)
6. Build the artifacts
7. Verify and hand over

Scripts live in `scripts/`, templates in `assets/`, deeper guidance in `references/`.
`assets/example_plan.json` is a complete worked plan — read it once before writing your own
`plan.json`; it is the fastest way to see the shape.

**This skill is a folder, not just this file.** It needs `scripts/`, `assets/` and `references/`
next to SKILL.md (see README.md for installation). If `scripts/mealplan.py` is missing, the install is
incomplete: tell the user, point them to the repository README to reinstall the full folder, and
don't try to rebuild the scripts from memory. The interview (phase 2) can start meanwhile.

Python 3.10+ with `openpyxl` is required (`pip install -r requirements.txt`). LibreOffice is
optional (workbook recalculation and error check); Playwright is optional (page screenshots).

## Host capabilities

Hosts differ. Before phase 2, check which tools this session actually has and use the first
available option in each row — never stall because a preferred tool is missing.

| Need | Preferred | Fallback |
|---|---|---|
| Structured questions | `AskUserQuestion` (≤ 4 questions per call) | numbered options in a normal message, one topic per message; the user answers with numbers or text |
| Workbook recalculation | `python3 scripts/recalc.py` (LibreOffice) | exit code 3 = no LibreOffice: deliver the workbook anyway (Excel, LibreOffice and Google Sheets compute formulas on open), say it was not error-checked here, and rely on `mealplan.py check` for the numbers |
| Delivering files | a file-delivery tool (`SendUserFile`, `present_files`, …) | write to an `outputs/` folder in the working directory and give the paths |
| HTML pages | an artifact/publishing tool, if the host has one | deliver the `.html` files; they are self-contained and open in any browser (tick state stays in that browser) |
| Parallel research | a subagent tool | research products one shop at a time |
| Memory, project docs, Drive | whatever connectors exist | ask the user; none of them is required |

Name the fallbacks you use once, in a line, so the user knows what they get.

---

## 1 · Gather what is already known

Before asking anything, look for answers the athlete already gave, in whatever this host offers:
memory (body stats, diet, training, an existing nutrition plan), attached project docs, earlier
outputs (cooking pages, shopping lists, a previous `plan.json`) and an existing meal-plan workbook
(uploaded, or in a connected drive).
Anything found becomes a pre-filled default the athlete only confirms. If a full plan already
exists, ask one question first: build a new plan, or revise the existing one (then skip to the
phase the change touches — most revisions are phase 4 → 6).

When the athlete says "the research was already done" or points at earlier outputs, retrieve
those values (read the earlier page or file) rather than recomputing them from databases.

## 2 · Depth picker + interview

The athlete chooses how deep each topic goes. Ask with `AskUserQuestion` when available — it takes
at most four questions per call, so the seven topics go in two calls (4 + 3); otherwise list the
seven topics with the four options in one message. Every topic gets the same four
options, in this order:

- **Skip** — use what you already know or sensible defaults (say which defaults afterwards)
- **Quick** — one or two questions
- **Standard** — the usual set
- **Deep dive** — everything that could change the plan

Topics, in order:

1. Goal (and timeline, rate of change, competition dates)
2. Current body composition
3. Training and lifestyle (sessions, timing, steps, job, sleep, sweat)
4. Preferences and dietary restrictions (vegan etc., allergies, dislikes, religious rules)
5. Cooking (batch cooking or not, freezer and fridge space, time, kitchen kit)
6. The whole pre-workout process (pre-workout meal, drink/shake, intra, post)
7. Sourcing and shopping (country, supermarkets, online, budget, rhythm)

Then interview topic by topic at the chosen depth. The question bank, per topic and depth, is in
`references/interview.md` — read it now. Rules that keep the interview pleasant:

- Use concrete options (≤ 4 questions per `AskUserQuestion` call, or a short numbered list); the
  athlete can always answer in their own words.
  Pre-fill known answers as the first option, marked "(current)".
- Never ask what you can calculate or already know. Group related questions in one call.
- Safety screens are asked whatever depth was chosen (food allergies and intolerances, age band,
  health conditions or medication that change protein/caffeine/salt advice, drug-tested sport,
  history of disordered eating — asked gently and once). See "Safety" below for what each answer
  changes.
- **Allergy status is never assumed.** Record it in `plan.json` as `meta.allergies.status`:
  `none` (the athlete said so), `known` (with the list), or `unknown` (skipped, unsure, or no answer).
  Skipping the Preferences topic or running unattended does not make it `none`.
- If the athlete is not there to answer (scheduled run), take the defaults, say which, and continue
  — with allergy status `unknown`, stated at the top of the hand-over as something to confirm before
  cooking or shopping.

Write the answers into `profile.json` (fields in `scripts/targets.py` docstring) as you go.

## 3 · Targets

```bash
python3 scripts/targets.py profile.json targets.json
```

This gives BMR (Mifflin-St Jeor, averaged with Katch-McArdle when body fat is known), maintenance
for training and rest days, goal adjustment, protein/fat/carbs per day type and a micronutrient
table with three levels per nutrient: **floor** (D-A-CH reference), **aim** (athlete-adjusted —
energy-scaled B vitamins, +20 % magnesium, phytate-tier zinc, ×1.8 iron for plant-based diets,
sweat sodium, etc.) and **UL** (EFSA). The rationale for every adjustment, plus protein/carb ranges
by sport and the evidence behind the pre-workout protocol, is in `references/nutrition.md`.

Show the athlete one compact table (training day / rest day: kcal, P, C, F, g/kg) and the micro
targets that matter for *their* plan (the ones their diet makes risky — e.g. B12, iodine, iron,
zinc, calcium, vitamin D for plant-based eaters; sodium for heavy sweaters). Their own numbers win
if they have them (a coach's targets, a recent lab value): use them and note the source.

These are starting estimates. Say so once, and give the adjustment rule: 7-day weight average,
change kcal in ~150 kcal steps after 2–3 weeks if the trend misses the goal rate.

## 4 · Scratchpad plan → approval

Draft the plan as `plan.json` (schema: `references/plan-format.md`). At this stage ingredient
values can be generic (USDA / national database), but every row says where it came from.
Design rules that come from real use:

- **Whole packs.** Size batch recipes so tins, bags and nets are used up (2 tins of beans, not
  1.4). Shopping is computed in packs with carry-over, so odd amounts show up as waste.
- **Balance batches per dish, not in total.** Cooked portions of *each* batch dish must cover the
  days it is eaten across the whole cycle. `mealplan.py check` simulates the freezer over several
  cycles and reports per-dish shortfalls and spares; fix the rotation or the cook days until there
  are no steady-state shortfalls.
- **Freezer reality.** If the athlete gave freezer space, set `meta.freezer_portions` and keep the
  peak under it (alternate cook days, or fewer batches per session).
- **Protein per feeding:** ~0.3–0.4 g/kg with ≥ 2.5 g leucine where possible, spread over 4–6
  feedings; pre-sleep casein (or a slow plant blend) if they want it.
- **Pre-workout chain is timed from the session:** meal T−2.5–3 h, drink T−60, intra during,
  post-workout within ~2 h. Build a timing variant per session time the athlete uses.
- **Supplements count toward totals.** Put food in `days`, and list supplements as
  `targets.micros.<key>.supplement` (daily average — a 400 µg tablet every third day is 133 µg).
- **Allergens are binding.** Tag every ingredient with `allergens` (and `may_contain` for trace
  warnings). `mealplan.py check` flags any ingredient that contains a listed allergen, any ingredient
  without allergen data while the athlete has allergies, and an `unknown` status. Every later change
  (swaps, substitutions, product hardening) must pass this check again.
- **Metric units**, local product names, and the athlete's own words for meals.

Run the check after every change:

```bash
python3 scripts/mealplan.py check plan.json
```

Present the scratchpad **inline in the chat** (not as an artifact yet) using the template in
`references/artifacts.md` → "Scratchpad": targets, a day-type table per meal (time, what, kcal/P/C/F),
the weekly rotation, the batch rhythm (eaten / cooked / spare per dish), the pre-workout chain,
supplements, micro status (only rows that are not "ok", plus the ones the athlete cares about;
show lower bounds as "≥" and say plainly when an upper limit could not be verified because of
missing values — fill those values in phase 5 rather than calling them fine),
estimated weekly cost, and open questions. Keep it scannable.

Then ask for approval (structured question or plain text): **Approve and build** / **Change something** /
**Show a full day in detail**. Loop until approved. When the athlete proposes a change, simulate it
(edit a copy of plan.json, run check) and show the before → after on the numbers it moves before
applying it. Nothing in phase 6 is built before an explicit approval. The one exception: the
athlete said up front not to wait for review ("just build it", a scheduled run) — then build, and
put the scratchpad at the top of the hand-over so they can still redirect.

## 5 · Harden the data

After approval, replace generic values with what the athlete will really buy — this is where the
plan stops being approximate. Follow `references/sourcing.md`:

- Label values (per 100 g/ml) for the actual products at their shops; composition databases
  (USDA FDC, BLS, CoFID, CIQUAL, NEVO…) for micros and amino acids the label lacks. Put the product
  and database id in `source`. If the athlete has receipts, photos or label text, those win.
- Allergens from the actual product label, including "may contain" statements — a different brand
  of the same food can differ (curry pastes with shrimp, stock powders with celery, oats with gluten).
- Pack size, price, store and link per ingredient (`shop`), shelf life for fresh items.
- Research in parallel with subagents when the host has them and there are many products; tell them
  not to invent prices or URLs and to return "not found" instead.

Re-run the check. If anything moves materially (a day's kcal by > 5 %, a micro crosses a floor or
UL, weekly cost by > 15 %), tell the athlete what moved and why before building.

## 6 · Build the artifacts

Generate everything from the same `plan.json`:

```bash
python3 scripts/build_workbook.py plan.json Meal_Plan_Macros.xlsx
python3 scripts/recalc.py Meal_Plan_Macros.xlsx              # 0 errors required; exit 3 = no LibreOffice (see Host capabilities)
python3 scripts/check_workbook.py plan.json Meal_Plan_Macros.xlsx   # workbook numbers vs engine (after recalc)
python3 scripts/render_pages.py plan.json pages/
```

1. **Meal-plan workbook** (`Meal_Plan_Macros.xlsx`) — sheets *Week summary · Micros · EAA ·
   Ingredients · Mon … Sun*, blue inputs, green cross-sheet links, all nutrients live formulas back
   to the Ingredients sheet. Deliver it as a file (see Host capabilities). If the athlete keeps the
   plan in Google Sheets and a drive connector is present, offer to upload/replace it there.
2. **Shopping list** (`pages/shopping-list.html`) — dated runs for the coming cycle (stock-up,
   batch shops on cook days, fresh runs), whole packs after leftovers, alternating buys, per-run and
   weekly cost, tick boxes per run and cycle. `pages/shopping-list.md` is the same list as markdown:
   if the host has project docs, save it there next to the other plan docs; keep a dated changelog
   line in its header on later edits.
3. **Batch recipes** — one cooking page per batch recipe plus a cook-day page per session
   (`cook-*.html`): everything to buy and cook that day, in order.
4. **Recipe handouts** — one cooking page per non-batch recipe (breakfast, shakes, salad,
   pre-workout drink, plates). Each page: macro readout, tickable ingredients, prep, steps with
   timers, amino-acid score, micro footer.

If the host can publish pages (an artifact or hosting tool), publish one page per file in one batch
at the end, following any design or publishing guidance that host requires; the templates are
already responsive, theme-aware and self-contained. Otherwise deliver the HTML files. Ticks are
stored in the browser; cross-device sync needs a host feature for shared state, if one exists.

## 7 · Verify and hand over

Before the final message:

- `recalc.py` reported 0 errors and `check_workbook.py` reported no mismatches (or, without
  LibreOffice, say the workbook was not recalculated here).
- Every recipe page and the shopping list opened without console errors (render a screenshot with
  Playwright if available) and their numbers match the workbook for the same recipe/day.
- Shopping totals cover the cycle: check report has no "shopping:" warnings and no batch
  shortfalls.
- For high-stakes plans (competition prep, minors, medical conditions) have a fresh subagent, if the
  host has them, review plan.json against `references/nutrition.md` without seeing your reasoning;
  otherwise re-read plan.json against that reference yourself before handing over.

Hand over briefly: what was built, the starting targets with the 2–3-week adjustment rule, the
two or three things the athlete must do (e.g. buy an iodine supplement, book a ferritin test),
and the files/links. Keep `plan.json` with the deliverables (Project doc or file) — every later
change starts from it.

## Later changes

The athlete will tweak the plan for weeks (swap a protein source, resize a batch, move a session).
Edit `plan.json`, re-run `check`, show what moved, then regenerate only what is affected and
republish to the same page URLs if the host published them. Never patch numbers by hand in one output — the outputs would
drift apart.

## Safety

- **Allergies:** a listed allergen never appears in a recipe, product or substitution; when status is
  `unknown`, every output says so prominently and asks the athlete to confirm before use (the page
  renderers, the shopping markdown and the workbook add this banner from `meta.allergies` themselves). Labels
  change — tell the athlete to check the pack each time they buy.

- Not a substitute for a dietitian or doctor; say so once, plainly, when health conditions,
  medication, pregnancy or competition weight-making come up, and keep helping within that.
- **Under 18:** no aggressive deficits or weight-class cutting, no stimulant pre-workouts
  (caffeine, high-dose anything), food-first; involve a parent/coach. Ask age as a band.
- **Signs of disordered eating** (fear of foods, compensatory exercise, rapid loss, a stated
  history): stop giving calorie numbers, targets or deficit plans; offer structure without numbers
  and point to professional support.
- **Low energy availability:** in a cut, keep intake ≥ ~30 kcal per kg fat-free mass, ideally ≥ 45;
  flag RED-S signs (missed periods, frequent injury, fatigue).
- **Drug-tested athletes:** only batch-tested supplements (Kölner Liste, Informed Sport, NSF
  Certified for Sport); flag anything else.
- **Conditions:** kidney disease → no high-protein plan without their doctor; hypertension →
  caffeine and salt protocols need sign-off; on blood-pressure or nitrate medication → no citrulline/
  nitrate/PDE-5 stacking advice. Respect upper limits including supplements.
