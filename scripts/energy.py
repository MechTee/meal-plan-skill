"""Energy availability (EA): energy intake minus exercise energy expenditure, per kg fat-free mass.

    EA = (energy intake − exercise energy expenditure) / FFM        [kcal per kg FFM per day]

Exercise energy expenditure (EEE) here is the planned sessions' cost above resting metabolism,
(MET − 1) × kg × hours — the same net estimate used for the energy targets. Daily steps and job
activity are not exercise and are not subtracted. Both EEE and FFM are estimates (METs, body-fat
method), so EA carries roughly ±15–25 % uncertainty; treat it as a screening number.

Reference points from the research literature (originally in women; used for all athletes as
screening values, not diagnostic cut-offs — IOC 2023 REDs consensus, Mountjoy et al.):
  < 30 kcal/kg FFM   low — associated with health and performance impairments; needs review
  30–45              reduced — expected in a planned cut; also where many men and lighter-active
                     athletes sit at energy balance (balance depends on resting and daily activity)
  ≥ 45               around energy balance in the original (female) research
No single number guarantees safety: symptoms (menstrual changes, low libido, recurrent injury,
illness, fatigue, stalled performance) matter more than the calculation.
"""

LOW, REDUCED = 30.0, 45.0


def assess(intake_kcal, exercise_kcal, ffm_kg):
    """EA for one day. Returns dict with value and band, or a 'not computed' result with the reason."""
    if not ffm_kg or ffm_kg <= 0:
        return {"value": None, "band": "not computed", "reason": "fat-free mass unknown (needs a body-fat estimate)"}
    if exercise_kcal is None:
        return {"value": None, "band": "not computed", "reason": "exercise energy expenditure unknown"}
    ea = (intake_kcal - exercise_kcal) / ffm_kg
    band = "low" if ea < LOW else ("reduced" if ea < REDUCED else "adequate")
    return {"value": round(ea, 1), "band": band, "intake_kcal": round(intake_kcal), "exercise_kcal": round(exercise_kcal),
            "ffm_kg": round(ffm_kg, 1)}


def describe(r):
    if r["value"] is None:
        return f"not computed — {r['reason']}"
    text = {"low": "LOW (< 30): review the plan and screen for REDs signs before going ahead",
            "reduced": "30–45: expected in a planned cut and common at maintenance in men; fine if weight trend and "
                       "wellbeing are on track, watch for REDs signs",
            "adequate": "≥ 45"}[r["band"]]
    return (f"{r['value']} kcal/kg FFM ({r['intake_kcal']} kcal intake − {r['exercise_kcal']} kcal exercise, "
            f"{r['ffm_kg']} kg FFM) — {text}. Screening estimate (±15–25 %), not a diagnosis.")
