# Nutrition reference

Use for setting targets, checking a draft, and explaining choices. Ranges, not single "right"
numbers; pick within a range from the interview and say why in one line. Values reflect consensus
statements and reference tables as of mid-2026; if a value matters for a decision and you are
unsure it is current, check the source (dge.de, efsa.europa.eu) with a quick search.

## Contents
1. Energy
2. Macros
3. Micronutrient targets (floor / aim / UL)
4. Timing and the training-day chain
5. Pre-workout components — evidence and doses
6. Plant-based specifics
7. Amino-acid scoring
8. Sources

## 1 · Energy

- BMR: Mifflin-St Jeor (all); Katch-McArdle `370 + 21.6 × FFM` or Cunningham `500 + 22 × FFM`
  when body fat is reasonably known — Cunningham runs high for very muscular athletes; targets.py
  averages Mifflin and Katch.
- Maintenance = BMR × base factor (desk 1.25, on feet 1.4, physical job 1.6 — includes thermic
  effect of food) + steps above ~3 000 (≈ 0.00042 kcal × kg × step, net) + sessions:
  `(MET − 1) × kg × hours` (Compendium METs; resistance training 3.5–6 depending on effort).
- Training day vs rest day: same protein and fat, carbs absorb the difference.
- Goal adjustment:
  - Cut: 0.5–1.0 % body weight per week (≈ 7 700 kcal per kg); slower the leaner they are.
    Keep energy availability ≥ 30 kcal/kg FFM/day (≥ 45 ideal); below 30 is RED-S territory.
  - Lean gain (trained): ≈ 0.25–0.5 % body weight per month → usually +5–10 % kcal.
    Novices can gain faster.
  - Recomposition: maintenance, high protein.
- Always: starting estimate → adjust from the 7-day average weight after 2–3 weeks in ~150 kcal
  steps. A "free" allowance (e.g. +200 kcal for coffees, gum, tastings) avoids false precision.

## 2 · Macros

Protein
- 1.6–2.2 g/kg/day for strength/hypertrophy (Morton 2018 meta-analysis: benefit plateaus ≈ 1.6,
  upper CI 2.2); 1.2–1.7 for endurance; in a deficit 2.3–3.1 g/kg FFM (Helms 2014).
- Plant-dominant diets: aim ~5–10 % higher, or improve quality (soy, blends, leucine).
- 0.3–0.4 g/kg per feeding, 4–6 feedings, ≥ 2.5 g leucine where practical; 30–40 g casein
  (or slow plant blend) before sleep is a reasonable option.
- Kidney disease → do not prescribe high protein without their physician.

Carbohydrate (IOC/ACSM 2016, g/kg/day)
- Light/skill: 3–5 · moderate (~1 h/day): 5–7 · endurance 1–3 h/day: 6–10 · extreme: 8–12.
- Lifting-focused athletes do well at ~3–6; the rest of the energy can come from carbs or fat.
- Fibre ≥ 30 g/day overall but keep the pre-workout meal and drink low-fibre/low-fat if GI-sensitive.

Fat
- 20–35 % of energy, not below ~0.8 g/kg for long periods. Cover omega-3 (ALA for plant-based,
  EPA+DHA from fish or algae oil ~250–500 mg/day, more only for a reason).

## 3 · Micronutrient targets

Three levels per nutrient, per day:
- **Floor** = D-A-CH reference intake (DGE/ÖGE/SGE) for the athlete's sex and age. For other
  countries the national reference is usually within a few % — use D-A-CH unless the athlete asks.
- **Aim** = floor adjusted for the athlete (below). This is what the plan is built to hit.
- **UL** = EFSA tolerable upper level (or safe level) for total intake, food + supplements, unless
  the UL is defined for supplements only (magnesium, folic acid, niacin forms).

Athlete adjustments ("a bit higher, depending on nutrient")
| Nutrient | Aim rule | Why |
|---|---|---|
| B1, B2, B3, B6 | floor × (kcal / reference kcal 2 400 ♂ / 1 900 ♀), not below floor | requirements scale with energy turnover |
| Magnesium | floor × 1.2 | sweat losses, high turnover; supplement UL 250 mg applies to supplements only |
| Zinc | phytate tier (♂ 11/14/16, ♀ 7/8/10 mg low/medium/high phytate) × 1.1 | plant-heavy diets are high-phytate; sweat losses |
| Iron | plant-based: floor × 1.8 | non-haem iron bioavailability (IOM); menstruating athletes: screen ferritin |
| Sodium | 1 500 mg + sweat L × sodium mg/L per session (default 1 000 mg/L) averaged over the week | salty/heavy sweaters lose 1–3 g sodium per hour |
| Vitamin C | 150 mg | heavy training; megadoses can blunt adaptation |
| Vitamin D | 20 µg; supplement Oct–Mar above ~40° N | no skin synthesis in winter; test 25(OH)D |
| Calcium | 1 000 mg; 1 300–1 500 mg with low energy availability/amenorrhoea | bone health in RED-S |
| Iodine | 200 µg | plant drinks are rarely iodised; iodised salt and supplements usually needed when dairy is dropped |
| B12 | 4 µg; vegans/near-vegans: supplement always | food sources unreliable |
| Nitrate | 400–500 mg on training days (performance) | 6–8 mmol 2–3 h pre |

Reference values used by `targets.py` (adults 25–50, ♂ / ♀, UL):
B1 1.2/1.0 · B2 1.4/1.1 · B3 15/12 mg NE · B5 5 · B6 1.6/1.4 (UL 12) · biotin 40 µg · folate 300 µg
DFE (UL 1 000 µg folic acid) · B12 4.0 µg · K 4 000 · P 700 (EFSA AI 550) · Mg 350/300 · Ca 1 000
(UL 2 500) · Zn see tiers (UL 25) · Fe 11/16 (EFSA safe level 40) · Se 70/60 (UL 255) · I 200 (UL 600)
· vit A 850/700 µg RAE (UL 3 000 retinol) · C 110/95 · D 20 µg (UL 100) · E 14/12 (UL 300) ·
K 70/60 µg · Na 1 500 mg.

Supplements and ULs: add regular supplements as a daily average (`supplement` in plan.json);
the check compares food + supplement against UL. Multivitamins on top of a fortified diet often
push zinc, vitamin A, iodine or selenium toward ULs — check before recommending.

## 4 · Timing and the training-day chain

| When | What | Notes |
|---|---|---|
| T −3 to −2 h | pre-workout meal: 1–2 g/kg carbs, 0.3 g/kg protein, low fat/fibre if sensitive; nitrate source (rucola, beetroot) here | nitrate peaks 2–3 h after |
| T −60 min | pre-workout drink (caffeine, citrulline, sodium, fluid) | caffeine peaks 30–60 min |
| During | water; carbs 30–60 g/h if > 60–75 min or high volume; sodium if heavy sweater | diluted juice works |
| T +0–2 h | protein 0.3–0.4 g/kg (+ carbs if another session within 24 h or high volume) | creatine fits here |
| Evening | last meal; pre-sleep casein if wanted | caffeine cut-off ~8 h before bed |

Offer both session-time variants if the athlete trains at different times (e.g. an 18:00 and a
12:30 schedule) — same foods, shifted times. Watch evening fluid volume (a 1.3 L pre-drink + intra
+ shakes late in the day can wake them at night).

## 5 · Pre-workout components — evidence and doses

| Component | Evidence | Dose | Cautions |
|---|---|---|---|
| Caffeine | strong (ISSN 2021) | 3–6 mg/kg ~60 min pre; 2 mg/kg often enough | sleep, anxiety, hypertension, minors: avoid |
| Creatine monohydrate | strong (ISSN 2017) | 3–5 g/day (≈ 0.1 g/kg), timing flexible; loading optional | weight gain from water; fine for most |
| Beta-alanine | good for 1–4 min efforts (ISSN 2015) | 3.2–6.4 g/day split doses, ≥ 2–4 weeks | paraesthesia (tingling) — split or sustained-release |
| Dietary nitrate (beetroot, rucola) | moderate; smaller in highly trained endurance athletes | ~6–8 mmol (370–500 mg) 2–3 h pre | antibacterial mouthwash blunts it; nitrate medication/PDE-5 inhibitors: avoid stacking |
| Citrulline (malate) | mixed–moderate for reps/fatigue | 6–8 g citrulline malate (3–6 g L-citrulline) ~60 min pre | GI at high doses; blood-pressure medication |
| Sodium | situational | 300–600 mg/h in heat/heavy sweat; a few g pre-drink for "pump" is common practice | hypertension |
| Glycerol | hyperhydration in heat/endurance | 1–1.2 g/kg with 25–35 ml/kg fluid 60–120 min pre; lower doses for "pump" are anecdotal | GI, headache; WADA removed it from the prohibited list in 2018 — still check current rules |
| Sodium bicarbonate | good for 1–7 min high-intensity | 0.2–0.3 g/kg 60–180 min pre | GI distress — trial in training |
| Taurine | weak | 1–3 g | — |
| AAKG, BCAA (with adequate protein), glutamine, HMB, ZMA | weak/none for trained, well-fed athletes | — | usually drop them |

Drug-tested athletes: only batch-tested products (Kölner Liste in Germany, Informed Sport, NSF
Certified for Sport). Caffeine is monitored but not prohibited (WADA), glycerol not prohibited since
2018 — confirm the current list for their federation.

## 6 · Plant-based specifics

- Protein quality: combine legumes with grains/soy; soy isolate and textured soy score well; lentils
  are low in methionine + cysteine, cereals low in lysine.
- Micros to watch: B12 (supplement), iodine (plant drinks rarely iodised → iodised salt, supplement),
  iron (×1.8, vitamin C with meals, tea/coffee away from meals), zinc (high-phytate tier), calcium
  (fortified drinks, tofu with calcium sulfate), vitamin D, omega-3 (algae oil), selenium (one
  Brazil nut a few times per week ≈ 50–90 µg each — mind the UL).
- Switching milk ↔ plant drink changes calcium, iodine, B2, B12 and vitamin D at once — re-check all
  five, not just protein and kcal.

## 7 · Amino-acid scoring (what the pages and EAA sheet show)

FAO 2013 scoring pattern (adults, mg per g protein): His 16 · Ile 30 · Leu 61 · Lys 48 ·
Met+Cys 23 · Phe+Tyr 41 · Thr 25 · Trp 6.6 · Val 40.
Score per amino acid = (digestible amino acid mg ÷ protein g) ÷ pattern. The lowest score is the
limiting amino acid; with ingredient digestibility factors applied it approximates DIAAS.
Typical digestibility factors: soy isolate 0.95, casein/whey 0.97–0.98, textured soy 0.90,
pulses 0.75–0.80, cereals 0.85–0.90, nuts/seeds 0.80, vegetables 0.75.
Amino acid content per 100 g: USDA FoodData Central (Foundation / SR Legacy) profiles; scale by the
label protein when the label differs from the database food.

## 8 · Sources

- Thomas, Erdman, Burke 2016 — ACSM/AND/DC position: nutrition and athletic performance
- Jäger et al. 2017 — ISSN position stand: protein and exercise
- Morton et al. 2018 — protein supplementation meta-analysis (Br J Sports Med)
- Helms et al. 2014 — protein in energy-restricted resistance-trained athletes
- Guest et al. 2021 — ISSN position stand: caffeine and exercise performance
- Kreider et al. 2017 — ISSN position stand: creatine
- Trexler et al. 2015 — ISSN position stand: beta-alanine
- Maughan et al. 2018 — IOC consensus statement: dietary supplements and the high-performance athlete
- Mountjoy et al. 2023 — IOC consensus statement on REDs
- D-A-CH Referenzwerte für die Nährstoffzufuhr (DGE, current edition); EFSA Dietary Reference
  Values and tolerable upper intake levels
- FAO 2013 — Dietary protein quality evaluation in human nutrition
- Ainsworth et al. 2011 / Herrmann et al. 2024 — Compendium of Physical Activities
