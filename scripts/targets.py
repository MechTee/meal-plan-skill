#!/usr/bin/env python3
"""Energy, macro and micronutrient targets from interview answers.

  python targets.py profile.json [targets.json]

profile.json (anything missing falls back to a stated default):
{
  "sex": "male"|"female", "age": 32, "height_cm": 187, "weight_kg": 87, "bodyfat_pct": 13,
  "occupation": "desk"|"standing"|"manual", "steps_per_day": 10000,
  "sessions": [{"type": "resistance_vigorous", "minutes": 75, "per_week": 6, "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]}],
  "training_days": 6,                      (distinct days with any training, 0–7; or give "days" per session)
  "goal": "cut"|"maintain"|"recomp"|"lean_gain"|"gain", "rate_pct_bw_per_week": 0.5,
  "sport_focus": "strength"|"hypertrophy"|"endurance"|"team"|"mixed",
  "diet": "omnivore"|"pescatarian"|"vegetarian"|"vegan",
  "protein_g_per_kg": null, "fat_pct": null,
  "sweat_l_per_session": 1.0, "sweat_sodium_mg_per_l": 1000,
  "low_sun": true, "menstruating": true, "postmenopausal": false, "low_energy_availability_risk": false
}
Prints a markdown summary and writes targets.json in the plan.json "targets" shape.
Numbers are starting estimates: tell the athlete to adjust kcal from the 7-day weight
average after 2–3 weeks (~±150 kcal per step).
"""
import math, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import energy

MET = {  # Compendium of Physical Activities (Ainsworth 2011 / Herrmann 2024), gross METs
    "resistance_light": 3.5, "resistance_vigorous": 5.0, "powerlifting": 6.0, "hiit": 8.0,
    "running_easy": 8.3, "running_tempo": 10.5, "cycling_moderate": 6.8, "cycling_vigorous": 10.0,
    "swimming_moderate": 6.0, "rowing_moderate": 7.0, "team_sport": 7.0, "martial_arts": 10.3,
    "climbing": 7.5, "yoga": 2.5, "walking_brisk": 4.3, "hiking": 6.0,
}
BASE_PAL = {"desk": 1.25, "standing": 1.4, "manual": 1.6}  # incl. thermic effect of food, excl. extra steps/training

# Reference values (floor): DGE/ÖGE reference values for nutrient intake, adults 25–<51 years, not pregnant or
# breastfeeding. Each entry: male, female, UL, note, type, year of derivation ("Stand Ableitung") and source page.
# UL = EFSA tolerable upper level (or safe level). A number applies to TOTAL intake; a list of
# (form, limit) applies only to that form (see FORMS in mealplan.py) — e.g. the magnesium UL covers
# supplemental/added magnesium, the vitamin A UL preformed retinol, the folate UL synthetic folic acid.
# Checked against dge.de on 2026-10-24 (3rd edition, printed Sept 2025); re-check when the DGE publishes revisions.
REFERENCE = {
    "name": "DGE/ÖGE reference values for nutrient intake, 3rd edition (2025)",
    "population": "adults 25–<51 years, not pregnant or breastfeeding",
    "checked": "2026-10-24",
    "url": "https://www.dge.de/wissenschaft/referenzwerte/",
}
_DGE = "https://www.dge.de/wissenschaft/referenzwerte/"
REF_DATA = {  # key: (male, female, UL, note, type, derived, page)
    "thiamin_mg": (1.2, 1.0, None, "scales with energy intake", "recommendation", 2015, "thiamin/"),
    "riboflavin_mg": (1.4, 1.1, None, "scales with energy intake", "recommendation", 2015, "riboflavin/"),
    "niacin_mg": (15, 12, [("nicotinamide_mg", 900), ("nicotinic_acid_mg", 10)],
                  "ULs apply to nicotinamide and nicotinic acid from supplements/fortification only", "recommendation", 2015, "niacin/"),
    "pantothenic_mg": (5, 5, None, "estimated value", "estimated value", 2021, "pantothensaeure/"),
    "b6_mg": (1.6, 1.4, 12, "EFSA UL 12 mg (2023)", "recommendation", 2019, "vitamin-b6/"),
    "biotin_ug": (40, 40, None, "estimated value", "estimated value", 2020, "biotin/"),
    "folate_ug": (300, 300, [("folic_acid_ug", 1000)], "UL 1000 µg applies to synthetic folic acid only", "recommendation", 2015, "folat/"),
    "b12_ug": (4.0, 4.0, None, "vegan: must supplement; absorption saturates — dose per pack", "estimated value", 2018, "vitamin-b12/"),
    "potassium_mg": (4000, 4000, None, "estimated value", "estimated value", 2016, "kalium/"),
    "phosphorus_mg": (550, 550, None, "DGE lowered from 700 mg", "estimated value", 2024, "phosphor/"),
    "magnesium_mg": (350, 300, [("magnesium_added_mg", 250)], "UL 250 mg applies to supplemental/added magnesium only", "estimated value", 2021, "magnesium/"),
    "calcium_mg": (1000, 1000, 2500, "", "recommendation", 2013, "calcium/"),
    "zinc_mg": (14, 8, 25, "phytate-dependent (low/medium/high: ♂ 11/14/16, ♀ 7/8/10)", "recommendation", 2019, "zink/"),
    "iron_mg": (11, 16, 40, "women: 16 mg while menstruating, 11 mg premenopausal without menstruation, 14 mg after menopause; EFSA safe level 40 mg (2024)",
                "recommendation", 2023, "eisen/"),
    "selenium_ug": (70, 60, 255, "EFSA UL 255 µg (2023)", "estimated value", 2015, "selen/"),
    "iodine_ug": (150, 150, 600, "DGE lowered from 200 µg in 2025; plant drinks are rarely iodised", "recommendation", 2025, "jod/"),
    "vitA_rae_ug": (850, 700, [("retinol_ug", 3000)], "UL 3000 µg applies to preformed vitamin A (retinol) only", "recommendation", 2020, "vitamin-a/"),
    "vitC_mg": (110, 95, None, "smokers 155/135 mg; no UL; GI upset above ~1 g supplemental", "recommendation", 2015, "vitamin-c/"),
    "vitD_ug": (20, 20, 100, "assumes no sun synthesis", "estimated value", 2012, "vitamin-d/"),
    "vitE_mg": (8, 8, 300, "DGE revised to 8 mg (RRR-α-tocopherol) for all adults", "estimated value", 2024, "vitamin-e/"),
    "vitK_ug": (70, 60, None, "estimated value; 80/65 µg from 51 years", "estimated value", 2000, "vitamin-k/"),
    "sodium_mg": (1500, 1500, None, "general advice: ≤ 6 g salt; athletes add sweat losses", "estimated value", 2016, "natrium/"),
    "nitrate_mg": (None, None, None, "performance dose ~6–8 mmol (≈ 370–500 mg) 2–3 h pre-session", "performance target", None, None),
}
REF = {k: v[:4] for k, v in REF_DATA.items()}   # (male, female, UL, note) — kept for callers


def ref_source(k):
    m, f, ul, note, typ, year, page = REF_DATA[k]
    return {"type": typ, "derived": year, "url": (_DGE + page) if page else None}
REF_KCAL = {"male": 2400, "female": 1900}


def bmr(p):
    s, w, h, a = p["sex"], p["weight_kg"], p["height_cm"], p["age"]
    mif = 10 * w + 6.25 * h - 5 * a + (5 if s == "male" else -161)
    out = {"mifflin": round(mif)}
    if p.get("bodyfat_pct"):
        ffm = w * (1 - p["bodyfat_pct"] / 100)
        out["katch_mcardle"] = round(370 + 21.6 * ffm)
        out["cunningham"] = round(500 + 22 * ffm)
        out["ffm_kg"] = round(ffm, 1)
        out["used"] = round((mif + out["katch_mcardle"]) / 2)
        out["method"] = "mean of Mifflin-St Jeor and Katch-McArdle"
    else:
        out["used"] = round(mif)
        out["method"] = "Mifflin-St Jeor"
    return out


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def training_days(p):
    """Number of DISTINCT days with any training (0–7) and how it was determined.

    Sessions are not days: three runs plus three lifts can be six training days or three days with
    doubles. Priority: per-session "days" lists (their union) → profile "training_days" → a single
    session type (its per_week) → otherwise assume separate days and say so."""
    sessions = p.get("sessions", [])
    for s in sessions:
        if s.get("days"):
            bad = [d for d in s["days"] if d not in DAYS]
            if bad:
                raise ValueError(f"session {s.get('type')}: unknown days {bad} (use {DAYS})")
            if len(set(s["days"])) != len(s["days"]):
                raise ValueError(f"session {s.get('type')}: a day is listed twice — use per_week for two sessions a day")
            s.setdefault("per_week", len(s["days"]))
        if not isinstance(s.get("per_week"), (int, float)) or s["per_week"] < 0:
            raise ValueError(f"session {s.get('type')}: per_week must be a number ≥ 0")
    if not sessions:
        return 0, "no sessions"
    if all(s.get("days") for s in sessions):
        days = set().union(*(s["days"] for s in sessions))
        return len(days), "union of the sessions' days: " + ", ".join(d for d in DAYS if d in days)
    td = p.get("training_days")
    if td is not None:
        if isinstance(td, list):
            if not set(td) <= set(DAYS):
                raise ValueError(f"training_days: unknown days {sorted(set(td) - set(DAYS))}")
            td = len(set(td))
        if not isinstance(td, int) or not 0 <= td <= 7:
            raise ValueError("training_days must be 0–7 (distinct days with any training)")
        total = sum(s["per_week"] for s in sessions)
        # fewer days than sessions is fine (doubles); a day count with no sessions to fill it is not
        if total > 0 and td == 0:
            raise ValueError(f"training_days=0 but {total:g} sessions per week are listed")
        if td > math.ceil(total - 1e-9):
            raise ValueError(f"training_days={td} but only {total:g} sessions per week — every training day needs a session")
        return td, "training_days from the profile"
    total = sum(s["per_week"] for s in sessions)
    frac = abs(total - round(total)) > 1e-9
    if len(sessions) == 1:
        n = sessions[0]["per_week"]
        if n > 7:
            raise ValueError("more than 7 sessions of one type per week: give training_days (doubles)")
        days = math.ceil(n - 1e-9)
        return days, "single session type" + (FRACTION_NOTE if frac else "")
    n = min(7, math.ceil(total - 1e-9))
    return n, (f"assumed {n} training days (session types on separate days); if some sessions share a day, "
               "set training_days or each session's days — this changes the training-day vs rest-day split"
               + (FRACTION_NOTE if frac else ""))


# a session every other week cannot sit on a fixed weekday of a one-week template: the day count is
# rounded up and the weekly exercise energy is averaged over those days (nothing is dropped)
FRACTION_NOTE = ("; fractional sessions per week are rounded up to whole training days and their weekly "
                 "exercise energy is averaged over them")
REFERENCE_POPULATION = f"{REFERENCE['population']} ({REFERENCE['name']})"


def population(p):
    """Route the profile: which population the built-in reference table covers.

    Returns (status, reason): "exact" (adults 25–<51), "approximate" (other adult ages — the table is
    used but some D-A-CH values differ by age band; outputs say so), or "unsupported" (minors,
    pregnancy, breastfeeding — different requirements; this calculator must not produce targets)."""
    age = p.get("age")
    if not isinstance(age, (int, float)) or age <= 0:
        raise ValueError("age is required (years) — reference values depend on it")
    if p.get("sex") not in ("male", "female"):
        raise ValueError('sex must be "male" or "female": it selects the energy equation and the reference table '
                         "(pick the set that best matches the athlete's physiology, e.g. hormonal status, and say so)")
    if age < 18:
        return "unsupported", ("under 18: adolescents have growth-specific energy and nutrient needs (e.g. D-A-CH calcium "
                               "1,200 mg for 15–<19 years) that this adult calculator does not model")
    if p.get("pregnant"):
        return "unsupported", ("pregnancy: energy, protein and several nutrient needs change by trimester (e.g. folate "
                               "550 µg folate equivalents) and need individual medical/dietetic guidance")
    if p.get("breastfeeding"):
        return "unsupported", ("breastfeeding: energy and several nutrient needs are higher (e.g. folate 450 µg folate "
                               "equivalents) and need individual dietetic guidance")
    if 25 <= age < 51:
        return "exact", REFERENCE_POPULATION
    if age < 19:
        return "approximate", (f"age {age:g} is in the D-A-CH 15–<19 band — an adolescent band, not an adult one: "
                               "calcium is 1,200 mg there (applied below), and energy and several vitamins and "
                               "minerals also differ from the 25–<51 table — check every target against the 15–<19 "
                               "values before using them; still growing, so no aggressive deficits or weight cutting")
    band = "19–<25" if age < 25 else ("51–<65" if age < 65 else "65+")
    return "approximate", (f"age {age:g} is in the D-A-CH {band} band; the built-in table is for 25–<51, and some values "
                           "differ by age (e.g. energy, vitamin B1/B2/niacin, and for 65+ protein ≥ 1.0 g/kg and fluid) — "
                           "check the targets against that age band before using them")


def compute(p):
    status, reason = population(p)
    if status == "unsupported":
        return {"supported": False, "population": status, "reason": reason,
                "advice": "Do not use adult targets. Offer food-first structure without calorie or nutrient numbers "
                          "and recommend a sports dietitian (and the athlete's doctor) for targets."}
    p = dict(p)
    p.setdefault("sex", "male"); p.setdefault("occupation", "desk"); p.setdefault("steps_per_day", 7000)
    p.setdefault("sessions", []); p.setdefault("goal", "maintain"); p.setdefault("diet", "omnivore")
    p.setdefault("sport_focus", "hypertrophy")
    w = p["weight_kg"]
    b = bmr(p)
    base = b["used"] * BASE_PAL.get(p["occupation"], 1.25)
    steps = 0.00042 * w * max(0, p["steps_per_day"] - 3000)
    p["sessions"] = [dict(x) for x in p.get("sessions", [])]   # don't mutate the caller's profile
    n_train, day_basis = training_days(p)                     # validates and fills per_week from days
    sess_week = 0.0
    sess_day = []
    for s in p["sessions"]:
        met = s.get("met") or MET.get(s["type"], 5.0)
        kcal = (met - 1) * w * s["minutes"] / 60
        sess_week += kcal * s["per_week"]
        sess_day.append(kcal)
    notes = []
    if day_basis.startswith("assumed"):
        notes.append(day_basis)
    train_extra = sess_week / n_train if n_train else 0   # average exercise on a training day
    tdee_rest = base + steps
    tdee_train = tdee_rest + train_extra
    tdee_avg = tdee_rest + sess_week / 7

    goal = p["goal"]
    rate = p.get("rate_pct_bw_per_week")
    if goal == "cut":
        adj = -(rate or 0.5) / 100 * w * 7700 / 7
    elif goal == "lean_gain":
        adj = (rate or 0.1) / 100 * w * 7700 / 7 if rate else 0.06 * tdee_avg
    elif goal == "gain":
        adj = (rate or 0.25) / 100 * w * 7700 / 7
    else:
        adj = 0.0
    kcal_train = round((tdee_train + adj) / 50) * 50
    kcal_rest = round((tdee_rest + adj) / 50) * 50

    plant = {"vegan": 1.10, "vegetarian": 1.05}.get(p["diet"], 1.0)
    if p.get("protein_g_per_kg"):
        pkg = p["protein_g_per_kg"]
    elif goal == "cut":
        pkg = 2.4
    elif p["sport_focus"] in ("strength", "hypertrophy"):
        pkg = 2.0
    else:
        pkg = 1.7
    protein = round(pkg * w * plant / 5) * 5
    fat_pct = p.get("fat_pct") or 0.25
    fat = round(max(fat_pct * (kcal_train + kcal_rest) / 2 / 9, 0.8 * w))
    carb_guide = {"strength": (4, 7), "hypertrophy": (4, 7), "team": (5, 8), "endurance": (6, 10), "mixed": (4, 7)}[p["sport_focus"]]
    carb_t = round((kcal_train - protein * 4 - fat * 9) / 4)
    if carb_t / w < carb_guide[0] and not p.get("fat_pct"):
        # make room for carbs: drop fat toward 20 % of energy / 0.8 g/kg before anything else
        fat = round(max(0.20 * (kcal_train + kcal_rest) / 2 / 9, 0.8 * w))
        carb_t = round((kcal_train - protein * 4 - fat * 9) / 4)
        notes.append("fat lowered toward 20 % of energy to make room for carbohydrate")
    if carb_t / w < carb_guide[0]:
        notes.append(f"training-day carbs {carb_t / w:.1f} g/kg are below the {carb_guide[0]}–{carb_guide[1]} g/kg guideline: "
                     "energy may be underestimated (check session intensity/METs) or protein is set high — discuss")
    carb_r = round((kcal_rest - protein * 4 - fat * 9) / 4)

    sex = p["sex"]
    micros = {}
    avg_kcal = (kcal_train * n_train + kcal_rest * (7 - n_train)) / 7
    for k, (m, f, ul, note) in REF.items():
        floor = m if sex == "male" else f
        aim = floor
        why = note
        if k in ("thiamin_mg", "riboflavin_mg", "niacin_mg", "b6_mg") and floor:
            aim = round(floor * max(1.0, avg_kcal / REF_KCAL[sex]), 2)
            why = f"scaled to {avg_kcal:.0f} kcal/day"
        if k == "magnesium_mg":
            aim = round(floor * 1.2)
            why = "+20 % for sweat losses and training load"
        if k == "zinc_mg":
            tier = {"vegan": 1, "vegetarian": 1}.get(p["diet"], 0)
            floor = (16 if tier else 14) if sex == "male" else (10 if tier else 8)
            aim = round(floor * 1.1, 1)
            why = ("high-phytate (plant-based) tier" if tier else "medium-phytate tier") + ", +10 % for sweat"
        if k == "iron_mg":
            # DGE 2023: 16 mg menstruating · 11 mg premenopausal without menstruation · 14 mg postmenopausal
            if sex == "female" and p.get("postmenopausal"):
                floor = aim = 14
                why = "14 mg after menopause (DGE)"
            elif sex == "female" and p.get("menstruating", True) is False:
                floor = aim = 11
                why = ("11 mg premenopausal without menstruation (DGE) — set postmenopausal: true if after "
                       "menopause (14 mg); if periods stopped because of low energy availability, that needs review")
            if p["diet"] in ("vegetarian", "vegan"):
                aim = round(floor * 1.8)
                why = "×1.8 for non-haem iron bioavailability (IOM); check ferritin"
            if sex == "female" and p.get("menstruating", True):
                why += "; menstruating athletes: screen ferritin"
        if k == "calcium_mg" and p["age"] < 19:
            floor, aim = max(floor, 1200), max(aim, 1200)
            why = "D-A-CH 15–<19 band: 1,200 mg"
        if k == "calcium_mg" and sex == "female" and p.get("low_energy_availability_risk"):
            aim = 1500
            why = "1,500 mg if low energy availability/amenorrhoea risk"
        if k == "sodium_mg":
            sw = p.get("sweat_l_per_session", 1.0) * p.get("sweat_sodium_mg_per_l", 1000)
            aim = round(floor + sw * sum(s["per_week"] for s in p["sessions"]) / 7)
            why = f"+ sweat ≈ {sw:.0f} mg per session"
        if k == "vitD_ug" and p.get("low_sun", True):
            why = "Oct–Mar above ~40° N there is no skin synthesis: plan a supplement and test 25(OH)D"
        if k == "nitrate_mg":
            floor, aim = 0, 400
            why = "training days only; EFSA ADI 3.7 mg/kg is set for additives — vegetable intake above it is normal"
        if k == "vitC_mg":
            aim = max(floor, 150)
            why = "150 mg covers heavy training; no benefit shown for megadoses"
        if isinstance(ul, list):
            micros[k] = {"floor": floor, "aim": aim, "ul": None,
                         "limits": [{"basis": b, "ul": v} for b, v in ul], "note": why, "source": ref_source(k)}
        else:
            micros[k] = {"floor": floor, "aim": aim, "ul": ul, "note": why, "source": ref_source(k)}

    # energy availability: intake minus planned exercise, per kg fat-free mass
    ffm = b.get("ffm_kg")
    ea = {"training": energy.assess(kcal_train, train_extra if n_train else 0, ffm),
          "rest": energy.assess(kcal_rest, 0, ffm),
          "week_avg": energy.assess((kcal_train * n_train + kcal_rest * (7 - n_train)) / 7, sess_week / 7, ffm),
          "method": "EA = (intake − planned exercise above resting) / FFM; steps and job activity not subtracted"}
    if ffm is None:
        if goal == "cut" or sess_week / 7 > 300:
            notes.append("energy availability not computed: no body-fat estimate, so fat-free mass is unknown — "
                         "ask for one (even a rough range) before setting a deficit for a heavily training athlete")
    else:
        for k in ("training", "week_avg"):
            if ea[k]["band"] == "low":
                notes.append(f"energy availability {k.replace('_', ' ')}: {energy.describe(ea[k])}")

    if status == "approximate":
        notes.append("reference values: " + reason)
    return {
        "training_days": n_train, "training_day_basis": day_basis,
        "energy_availability": ea,
        "supported": True, "population": status, "reference_population": REFERENCE_POPULATION,
        "bmr": b, "base_pal": BASE_PAL.get(p["occupation"]), "steps_kcal": round(steps),
        "session_kcal": [round(x) for x in sess_day], "tdee": {"training": round(tdee_train), "rest": round(tdee_rest), "avg": round(tdee_avg)},
        "goal_adjust_kcal": round(adj), "notes": notes, "protein_g_per_kg": round(protein / w, 2),
        "carb_guide_g_per_kg": carb_guide, "water_l": round(0.035 * w + p.get("sweat_l_per_session", 1.0) * sum(s["per_week"] for s in p["sessions"]) / 7, 1),
        "targets": {
            "training": {"kcal": kcal_train, "protein_g": protein, "carb_g": carb_t, "fat_g": fat},
            "rest": {"kcal": kcal_rest, "protein_g": protein, "carb_g": carb_r, "fat_g": fat},
            "fiber_min": 30, "salt_max": 6, "micros": micros,
            "reference": dict(REFERENCE),
        },
    }


def summary(p, r):
    if not r.get("supported", True):
        return f"## Not supported\n\n{r['reason']}.\n\n{r['advice']}"
    t = r["targets"]
    w = p["weight_kg"]
    L = ["## Energy", f"BMR ≈ {r['bmr']['used']} kcal ({r['bmr']['method']}); base PAL {r['base_pal']}; "
         f"steps above 3,000 ≈ {r['steps_kcal']} kcal; sessions ≈ {', '.join(map(str, r['session_kcal'])) or '–'} kcal each.",
         f"Training days: {r['training_days']} per week ({r['training_day_basis']}).",
         f"Maintenance ≈ {r['tdee']['training']} (training day) / {r['tdee']['rest']} (rest day) · goal adjustment {r['goal_adjust_kcal']:+} kcal/day.",
         "", "| Day | kcal | Protein g | Carbs g | Fat g | Carbs g/kg |", "|---|---|---|---|---|---|"]
    for d in ("training", "rest"):
        x = t[d]
        L.append(f"| {d} | {x['kcal']} | {x['protein_g']} ({x['protein_g'] / w:.1f}/kg) | {x['carb_g']} | {x['fat_g']} | {x['carb_g'] / w:.1f} |")
    lo, hi = r["carb_guide_g_per_kg"]
    ea = r.get("energy_availability", {})
    if ea:
        L.append("\nEnergy availability (intake − planned exercise, per kg fat-free mass):")
        for k, lab in (("training", "training day"), ("rest", "rest day"), ("week_avg", "week average")):
            L.append(f"- {lab}: {energy.describe(ea[k])}")
    for n in r.get("notes", []):
        L.append(f"\nNote: {n}")
    L.append(f"\nSport guideline for carbs: {lo}–{hi} g/kg on training days. Water ≈ {r['water_l']} L/day plus drinks around sessions.")
    ref = t["reference"]
    L += ["", "## Micronutrients (per day)",
          f"Floor = {ref['name']}, {ref['population']} (checked {ref['checked']}). Aim = athlete adjustment. UL = EFSA.",
          "", "| Nutrient | Floor | Aim | UL | Why | Source (derived) |", "|---|---|---|---|---|---|"]
    for k, v in t["micros"].items():
        src = v.get("source") or {}
        cite = f"[DGE {src['derived']}]({src['url']})" if src.get("url") else "–"
        ul = v["ul"] or "; ".join(f"{x['ul']} ({x['basis']})" for x in v.get("limits", [])) or "–"
        L.append(f"| {k} | {v['floor'] if v['floor'] is not None else '–'} | {v['aim'] if v['aim'] is not None else '–'} | "
                 f"{ul} | {v['note']} | {cite} |")
    return "\n".join(L)


if __name__ == "__main__":
    prof = json.load(open(sys.argv[1]))
    try:
        res = compute(prof)
    except ValueError as e:
        print(f"PROFILE ERROR: {e}")
        sys.exit(1)
    print(summary(prof, res))
    if not res.get("supported", True):
        sys.exit(2)
    if len(sys.argv) > 2:
        json.dump(res, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
