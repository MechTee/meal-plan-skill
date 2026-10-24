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

**Toolkit setup (do this first).** If `scripts/mealplan.py` is not next to this file, the toolkit
lives in the "Meal Plan" claude.ai Project under `claude/athlete-meal-plan-kit/`. Restore it into a
working folder `amp/` with the same layout — `Projects project_read` each path below and write the
content (or copy the local file the read returns for large files) to `amp/<path>`:

```
scripts/mealplan.py  scripts/targets.py  scripts/build_workbook.py  scripts/render_pages.py
assets/recipe_page.html  assets/shopping_list.html  assets/example_plan.json
references/interview.md  references/nutrition.md  references/plan-format.md
references/sourcing.md  references/artifacts.md
```

Then treat `amp/` as this skill's directory for every path below. If the session has no access to
that Project, say the toolkit isn't reachable from here and ask the athlete to run this in the
Meal Plan project (the interview and targets can still start meanwhile).

---

## 1 · Gather what is already known

Before asking anything, look for answers the athlete already gave: memory files (body stats,
diet, training, an existing nutrition plan), the attached Project's docs, earlier artifacts
(cooking pages, shopping lists) and a meal-plan workbook in Drive if a Drive connector is present.
Anything found becomes a pre-filled default the athlete only confirms. If a full plan already
exists, ask one question first: build a new plan, or revise the existing one (then skip to the
phase the change touches — most revisions are phase 4 → 6).

When the athlete says "the research was already done" or points at earlier artifacts, retrieve
those values (Artifact `read`, Drive download) rather than recomputing them from databases.

## 2 · Depth picker + interview

The athlete chooses how deep each topic goes. Ask with `AskUserQuestion` — it takes at most four
questions per call, so the seven topics go in two calls (4 + 3). Every topic gets the same four
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

- Use `AskUserQuestion` with concrete options (≤ 4 questions per call); the athlete can always type.
  Pre-fill known answers as the first option, marked "(current)".
- Never ask what you can calculate or already know. Group related questions in one call.
- Safety screens are asked whatever depth was chosen (age band, health conditions or medication
  that change protein/caffeine/salt advice, drug-tested sport, history of disordered eating —
  asked gently and once). See "Safety" below for what each answer changes.
- If the athlete is not there to answer (scheduled run), take the defaults, say which, and continue.

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
- **Energy availability is part of the draft.** Copy `bmr.ffm_kg` and the per-day-type exercise
  kcal from `targets.py` into `meta.ffm_kg` / `meta.exercise_kcal` so the check covers the actual
  plan; a day with extra or no training can set its own `exercise_kcal`.
- **Supplements count toward totals.** Put food in `days`, and list supplements as
  `targets.micros.<key>.supplement` (daily average — a 400 µg tablet every third day is 133 µg).
- **Metric units**, local product names, and the athlete's own words for meals.

Run the check after every change:

```bash
python3 scripts/mealplan.py check plan.json
```

Present the scratchpad **inline in the chat** (not as an artifact yet) using the template in
`references/artifacts.md` → "Scratchpad": targets, a day-type table per meal (time, what, kcal/P/C/F),
the weekly rotation, the batch rhythm (eaten / cooked / spare per dish), the pre-workout chain,
supplements, micro status (only rows that are not "ok", plus the ones the athlete cares about),
estimated weekly cost, and open questions. Keep it scannable.

Then ask for approval with `AskUserQuestion`: **Approve and build** / **Change something** /
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
- Pack size, price, store and link per ingredient (`shop`), shelf life for fresh items.
- Research in parallel with subagents when there are many products; tell them not to invent prices
  or URLs and to return "not found" instead.

Re-run the check. If anything moves materially (a day's kcal by > 5 %, a micro crosses a floor or
UL, weekly cost by > 15 %), tell the athlete what moved and why before building.

## 6 · Build the artifacts

Generate everything from the same `plan.json`:

```bash
python3 scripts/build_workbook.py plan.json Meal_Plan_Macros.xlsx
python3 <xlsx skill dir>/scripts/recalc.py Meal_Plan_Macros.xlsx 90   # e.g. /mnt/skills/public/xlsx — must report 0 errors
python3 scripts/render_pages.py plan.json pages/
```

1. **Meal-plan workbook** (`Meal_Plan_Macros.xlsx`) — sheets *Week summary · Micros · EAA ·
   Ingredients · Mon … Sun*, blue inputs, green cross-sheet links, all nutrients live formulas back
   to the Ingredients sheet. Read the xlsx skill's SKILL.md before the first build in a session.
   Deliver with `SendUserFile`. If the athlete keeps the plan in Google Sheets and a Drive connector
   is present, offer to upload/replace it there.
2. **Shopping list** (`pages/shopping-list.html`) — dated runs for the coming cycle (stock-up,
   batch shops on cook days, fresh runs), whole packs after leftovers, alternating buys, per-run and
   weekly cost, tick boxes per run and cycle. Publish as an artifact. If a Project is attached, also
   write the markdown version to the Project (format in `references/artifacts.md`) so it sits next
   to the other plan docs; keep a dated changelog line in its header on later edits.
3. **Batch recipes** — one cooking page per batch recipe plus a cook-day page per session
   (`cook-*.html`): everything to buy and cook that day, in order.
4. **Recipe handouts** — one cooking page per non-batch recipe (breakfast, shakes, salad,
   pre-workout drink, plates). Each page: macro readout, tickable ingredients, prep, steps with
   timers, amino-acid score, micro footer.

Before the first publish, load the `artifact-design` skill (required by the Artifact tool). The
templates already follow it, so this is a check, not a redesign. Publish one artifact per page
(icons: `recipe` for cooking pages, `cart` for the shopping list), in one batch at the end, then
give one line per artifact group. If the athlete wants ticks synced across phone and laptop, load
`artifact-capabilities` and add the shared-state capability to the shopping list.

## 7 · Verify and hand over

Before the final message:

- `recalc.py` reported 0 errors, and three workbook cells match `mealplan.py` output (a day's kcal,
  a micro total, a leucine total).
- Every recipe page and the shopping list opened without console errors (render a screenshot with
  Playwright if available) and their numbers match the workbook for the same recipe/day.
- Shopping totals cover the cycle: check report has no "shopping:" warnings and no batch
  shortfalls.
- For high-stakes plans (competition prep, minors, medical conditions) have a fresh subagent
  review plan.json against `references/nutrition.md` without seeing your reasoning.

Hand over briefly: what was built, the starting targets with the 2–3-week adjustment rule, the
two or three things the athlete must do (e.g. buy an iodine supplement, book a ferritin test),
and the files/links. Keep `plan.json` with the deliverables (Project doc or file) — every later
change starts from it.

## Later changes

The athlete will tweak the plan for weeks (swap a protein source, resize a batch, move a session).
Edit `plan.json`, re-run `check`, show what moved, then regenerate only what is affected and
republish to the same artifact URLs. Never patch numbers by hand in one output — the outputs would
drift apart.

## Safety

- Not a substitute for a dietitian or doctor; say so once, plainly, when health conditions,
  medication, pregnancy or competition weight-making come up, and keep helping within that.
- **Under 18:** no aggressive deficits or weight-class cutting, no stimulant pre-workouts
  (caffeine, high-dose anything), food-first; involve a parent/coach. Ask age as a band.
- **Signs of disordered eating** (fear of foods, compensatory exercise, rapid loss, a stated
  history): stop giving calorie numbers, targets or deficit plans; offer structure without numbers
  and point to professional support.
- **Low energy availability:** energy availability is intake **minus planned exercise expenditure**,
  per kg fat-free mass — not total intake per kg. `targets.py` and `mealplan.py check` compute it when
  a body-fat estimate exists (`meta.ffm_kg`, `meta.exercise_kcal`); without one, say it could not be
  checked and ask for a rough estimate before setting a deficit for a heavily training athlete. Below
  ~30 kcal/kg FFM: revise the plan (smaller deficit, more on training days) and screen for REDs
  signs (menstrual changes, low libido, recurrent injury or illness, fatigue, stalled performance).
  These are screening reference points, not diagnostic cut-offs — symptoms outrank the number.
- **Drug-tested athletes:** only batch-tested supplements (Kölner Liste, Informed Sport, NSF
  Certified for Sport); flag anything else.
- **Conditions:** kidney disease → no high-protein plan without their doctor; hypertension →
  caffeine and salt protocols need sign-off; on blood-pressure or nitrate medication → no citrulline/
  nitrate/PDE-5 stacking advice. Respect upper limits including supplements.
