# Interview question bank

How to use: after the depth picker, go topic by topic. For each topic ask the **Quick** questions
at Quick depth, Quick + **Standard** at Standard, all three tiers at Deep dive. **Skip** = use what
memory/project already says, else the listed default, and say which defaults you took.

Ask with `AskUserQuestion` when the host has it (≤ 4 questions per call, 2–4 options each; the
athlete can always type "Other"). Without it, write the same questions as short numbered lists in a
normal message. Put a known answer first as "(current)". Turn free numbers (weight, height) into a short
plain-text question in your message instead of forcing options.

## Depth picker (two calls)

Call 1 — header chips "Goal", "Body", "Training", "Diet". Call 2 — "Cooking", "Pre-workout",
"Shopping". Each question: "How deep should we go on <topic>?" with options:
`Skip — use what you know` · `Quick (1–2 questions)` · `Standard` · `Deep dive`.

Example call:
```json
{"questions":[
 {"question":"How deep should we go on your goal?","header":"Goal","multiSelect":false,
  "options":[{"label":"Skip — use what you know","description":"I'll use what's on file or a sensible default"},
             {"label":"Quick (1–2 questions)"},{"label":"Standard"},{"label":"Deep dive"}]},
 {"question":"How deep should we go on your current body composition?","header":"Body", "...":"same options"},
 {"question":"How deep should we go on training and lifestyle?","header":"Training", "...":"same options"},
 {"question":"How deep should we go on food preferences and restrictions?","header":"Diet", "...":"same options"}]}
```

## Safety screen (always, whatever depth)

One call, phrased lightly. These are asked even when every topic is skipped and even when the plan
is otherwise built from defaults:
- Food allergies or intolerances: none / yes — I'll list them / not sure. "Not sure" or no answer is
  recorded as `unknown`, never as `none`.
- Age band: under 18 / 18–39 / 40–59 / 60+
- Anything a plan must respect: none / a health condition or medication / pregnant or breastfeeding / prefer to tell in text
- Do you compete in a drug-tested sport? yes / no
- Ask about eating-disorder history only if something in the conversation hints at it, and gently.

## 1 · Goal  → profile.goal, rate_pct_bw_per_week, sport_focus

Quick
- Main goal: lose fat / maintain / slow lean gain / gain size-strength / performance for an event
- Sport focus: strength · hypertrophy · endurance · team/intermittent · mixed

Standard
- Pace: gentle / moderate / fast (cut: 0.5 / 0.75 / 1.0 % body weight per week; lean gain:
  ~0.25 / 0.5 / 1 % per month)
- Time frame or date (competition, holiday, season start)

Deep
- Weight class / making weight? (then: no water-cutting advice beyond general principles; refer to a
  dietitian for acute weight-making)
- Performance markers that matter (1RM, 5 k time, match fitness) — sets carb priority
- Previous diets: what worked, what broke (hunger, social life, cost)
- Diet breaks / refeeds wanted? Flexible weekend?

Defaults: maintain, hypertrophy.

## 2 · Current body composition  → sex, age, height_cm, weight_kg, bodyfat_pct

Quick
- Height, weight (text), sex for the equations

Standard
- Body-fat estimate and how measured (DEXA / BIA scale / calipers / mirror guess)
- Weight trend last 4 weeks: stable / up / down

Deep
- Waist, recent DEXA or InBody numbers (FFM is better than any equation)
- Recent blood tests (ferritin, vitamin D, B12, haemoglobin, lipids) — values become the targets'
  context; plan re-tests rather than treating them
- Menstrual cycle regular? (energy availability screen, iron)

Defaults: no body fat → Mifflin-St Jeor only.

## 3 · Training and lifestyle  → sessions[], steps_per_day, occupation, sweat

Quick
- Sessions per week and type (lifting / running / cycling / team sport / mixed)
- Usual session time: morning / midday / evening / varies

Standard
- Session length and intensity per type (map to `MET` keys in targets.py)
- Rest days: which weekdays
- Daily steps (phone/watch average) and job: desk / on feet / physical
- Sleep: usual bed and wake time (sets the night feeding and caffeine cut-off)

Deep
- Second sessions / doubles, cardio on top, sport practice vs gym
- Sweat: light / normal / heavy / salty (white marks) → `sweat_l_per_session`, `sweat_sodium_mg_per_l`
- Training in heat? Fasted training preference?
- Commute and where meals are eaten (office fridge, microwave, gym bag)
- Travel days per month (then: a travel variant of the day)

Defaults: 4 × 60 min resistance, evening, 7 000 steps, desk job, normal sweat.

## 4 · Preferences and restrictions  → diet, ingredient choices, recipes

Quick
- Pattern: omnivore / pescatarian / vegetarian (dairy? eggs?) / vegan
- (Allergies are already covered by the safety screen; here, ask how strict: traces/"may contain"
  matter or not, and any intolerance that is dose-dependent, e.g. lactose)

Standard
- Foods they dislike or will not cook; foods they want daily
- Meals per day they like: 3 / 4–5 / 6+; shakes OK? how many
- Protein powders already owned or preferred (whey, casein, soy, pea, blends)
- Spice tolerance; cuisines they enjoy

Deep
- Religious or cultural rules (halal, kosher, fasting periods)
- Digestion: foods that bloat them before training (fibre, FODMAPs, dairy)
- Alcohol, caffeine habits (coffee count matters for the pre-workout caffeine dose)
- Willing to eat the same breakfast daily? Same lunch rotation?
- Supplements already taken (dose, frequency) — they count toward micro totals and ULs

Defaults: omnivore, 5 feedings, shakes OK. Allergy status is never defaulted — it comes from the
safety screen (`none`, the listed allergens, or `unknown`).

## 5 · Cooking  → recipe kinds, cycle.sessions, meta.freezer_portions

Quick
- Batch cook or cook daily? / both (batch mains, fresh breakfast)
- Time available on a cook day: < 1 h / 1–2 h / 2–4 h

Standard
- Freezer space: containers that fit (count) or drawer count; fridge space
- Cook day(s) and how often: weekly / every 2 weeks / mixed (e.g. big day + small day)
- Containers owned (size, count) — portions are sized to them

Deep
- Kit: scale (1 g?), pressure cooker, rice cooker, blender, oven, air fryer
- Reheating at work: microwave yes/no → cold-friendly meals if no
- Variety tolerance: how many different mains per week (2 / 3–4 / 5+)
- Leftover rules: max days in fridge they accept

Defaults: batch mains weekly, 20 freezer portions, microwave available.

## 6 · Pre-workout process  → recipes pump/pre-meal/intra/post, day meal timing

Quick
- Pre-workout: a meal only / meal + drink or shake / a commercial pre-workout / nothing
- Caffeine pre-workout: yes / no / only for day sessions

Standard
- What they use now (product or ingredients and doses) — evaluate against the evidence table in
  nutrition.md and keep what works; flag doses outside ranges
- Pre-workout meal timing they tolerate (2–3 h / 1–2 h / < 1 h before)
- Intra-workout: water / carbs / electrolytes; session length decides if carbs help
- Post-workout: shake / meal / both

Deep
- Goals of the pre-workout: pump, endurance-in-set, focus, hydration in heat
- Components they're curious about (citrulline, nitrate/beetroot, beta-alanine, creatine, glycerol,
  sodium, taurine, bicarbonate) — explain evidence tier and dose briefly, let them choose
- Sensitivities: tingling (beta-alanine), GI (bicarbonate, glycerol volume), sleep (caffeine)
- Mouthwash use (antibacterial mouthwash blunts nitrate conversion)

Defaults: pre-meal T−2.5 h, no stimulant unless asked, creatine 3–5 g daily, water intra.

## 7 · Sourcing and shopping  → meta.country, currency, shop fields, shopping runs

Quick
- Country/city (sets shops, currency, product names)
- Main supermarket(s)

Standard
- Discounters / organic preference / online bulk (powders, legumes, soy chunks)?
- Budget per week: tight / moderate / not a concern (or a number)
- Shopping rhythm: one big shop + weekly fresh / twice a week / delivery

Deep
- Shop days and times that fit; car or on foot (weight per run matters)
- Brands they trust or avoid; organic for which items
- Bulk storage space (pantry) — decides stock-up cycle length (2 / 4 weeks)
- Receipts or product photos available? (label values beat database values)

Defaults: the country from memory; one stock-up per cycle, one fresh run per week on Saturday,
batch shop on cook day.
