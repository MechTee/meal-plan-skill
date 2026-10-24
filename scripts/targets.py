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
  "low_sun": true, "menstruating": false, "low_energy_availability_risk": false
}
Prints a markdown summary and writes targets.json in the plan.json "targets" shape.
Numbers are starting estimates: tell the athlete to adjust kcal from the 7-day weight
average after 2–3 weeks (~±150 kcal per step).
"""
import json, sys

MET = {  # Compendium of Physical Activities (Ainsworth 2011 / Herrmann 2024), gross METs
    "resistance_light": 3.5, "resistance_vigorous": 5.0, "powerlifting": 6.0, "hiit": 8.0,
    "running_easy": 8.3, "running_tempo": 10.5, "cycling_moderate": 6.8, "cycling_vigorous": 10.0,
    "swimming_moderate": 6.0, "rowing_moderate": 7.0, "team_sport": 7.0, "martial_arts": 10.3,
    "climbing": 7.5, "yoga": 2.5, "walking_brisk": 4.3, "hiking": 6.0,
}
BASE_PAL = {"desk": 1.25, "standing": 1.4, "manual": 1.6}  # incl. thermic effect of food, excl. extra steps/training

# Reference values: D-A-CH (DGE/ÖGE/SGE) adults 25–<51 as of 2026 knowledge — floor = reference intake.
# UL = EFSA tolerable upper level (or safe level) for TOTAL intake unless noted.
# Verify any value you are unsure of on dge.de / efsa.europa.eu before finalising a plan.
REF = {  # key: (male, female, UL, note)
    "thiamin_mg": (1.2, 1.0, None, "scales with energy intake"),
    "riboflavin_mg": (1.4, 1.1, None, "scales with energy intake"),
    "niacin_mg": (15, 12, None, "UL applies to supplemental nicotinamide/nicotinic acid only"),
    "pantothenic_mg": (5, 5, None, "estimated value"),
    "b6_mg": (1.6, 1.4, 12, "EFSA UL 12 mg (2023)"),
    "biotin_ug": (40, 40, None, "estimated value"),
    "folate_ug": (300, 300, None, "UL 1000 µg applies to synthetic folic acid only"),
    "b12_ug": (4.0, 4.0, None, "vegan: must supplement; absorption saturates — dose per pack"),
    "potassium_mg": (4000, 4000, None, "estimated value"),
    "phosphorus_mg": (700, 700, None, "EFSA AI 550 mg"),
    "magnesium_mg": (350, 300, None, "EFSA UL 250 mg applies to supplements only"),
    "calcium_mg": (1000, 1000, 2500, ""),
    "zinc_mg": (14, 8, 25, "phytate-dependent; see diet adjustment"),
    "iron_mg": (11, 16, 40, "EFSA safe level 40 mg (2024); women 19–50 value — verify current DGE band"),
    "selenium_ug": (70, 60, 255, "EFSA UL 255 µg (2023)"),
    "iodine_ug": (200, 200, 600, "EFSA AI 150 µg; plant drinks are rarely iodised"),
    "vitA_rae_ug": (850, 700, 3000, "UL is for preformed retinol"),
    "vitC_mg": (110, 95, None, "no UL; GI upset above ~1 g supplemental"),
    "vitD_ug": (20, 20, 100, "reference assumes no sun synthesis"),
    "vitE_mg": (14, 12, 300, "estimated value"),
    "vitK_ug": (70, 60, None, "estimated value"),
    "sodium_mg": (1500, 1500, None, "general advice: ≤ 6 g salt; athletes add sweat losses"),
    "nitrate_mg": (None, None, None, "performance dose ~6–8 mmol (≈ 370–500 mg) 2–3 h pre-session"),
}
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
        most = max(s["per_week"] for s in sessions)
        if td == 0 or (most <= 7 and td < most):
            raise ValueError(f"training_days={td} is fewer than a session type's {most} sessions per week")
        return td, "training_days from the profile"
    if len(sessions) == 1:
        n = sessions[0]["per_week"]
        if n > 7:
            raise ValueError("more than 7 sessions of one type per week: give training_days (doubles)")
        return int(n), "single session type"
    n = min(7, int(sum(s["per_week"] for s in sessions)))
    return n, (f"assumed {n} training days (session types on separate days); if some sessions share a day, "
               "set training_days or each session's days — this changes the training-day vs rest-day split")


def compute(p):
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
            if p["diet"] in ("vegetarian", "vegan"):
                aim = round(floor * 1.8)
                why = "×1.8 for non-haem iron bioavailability (IOM); check ferritin"
            if sex == "female" and p.get("menstruating", True):
                why += "; menstruating athletes: screen ferritin"
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
        micros[k] = {"floor": floor, "aim": aim, "ul": ul, "note": why}

    return {
        "training_days": n_train, "training_day_basis": day_basis,
        "bmr": b, "base_pal": BASE_PAL.get(p["occupation"]), "steps_kcal": round(steps),
        "session_kcal": [round(x) for x in sess_day], "tdee": {"training": round(tdee_train), "rest": round(tdee_rest), "avg": round(tdee_avg)},
        "goal_adjust_kcal": round(adj), "notes": notes, "protein_g_per_kg": round(protein / w, 2),
        "carb_guide_g_per_kg": carb_guide, "water_l": round(0.035 * w + p.get("sweat_l_per_session", 1.0) * sum(s["per_week"] for s in p["sessions"]) / 7, 1),
        "targets": {
            "training": {"kcal": kcal_train, "protein_g": protein, "carb_g": carb_t, "fat_g": fat},
            "rest": {"kcal": kcal_rest, "protein_g": protein, "carb_g": carb_r, "fat_g": fat},
            "fiber_min": 30, "salt_max": 6, "micros": micros,
        },
    }


def summary(p, r):
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
    for n in r.get("notes", []):
        L.append(f"\nNote: {n}")
    L.append(f"\nSport guideline for carbs: {lo}–{hi} g/kg on training days. Water ≈ {r['water_l']} L/day plus drinks around sessions.")
    L += ["", "## Micronutrients (per day)", "| Nutrient | Floor | Aim | UL | Why |", "|---|---|---|---|---|"]
    for k, v in t["micros"].items():
        L.append(f"| {k} | {v['floor'] if v['floor'] is not None else '–'} | {v['aim'] if v['aim'] is not None else '–'} | {v['ul'] or '–'} | {v['note']} |")
    return "\n".join(L)


if __name__ == "__main__":
    prof = json.load(open(sys.argv[1]))
    res = compute(prof)
    print(summary(prof, res))
    if len(sys.argv) > 2:
        json.dump(res, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
