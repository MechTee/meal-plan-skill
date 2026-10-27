#!/usr/bin/env python3
"""Cross-check a recalculated workbook against the Python engine.

  python check_workbook.py plan.json Meal_Plan_Macros.xlsx

Compares, for every day definition of the cycle (template days and week overrides), the Week summary kcal / protein / salt with mealplan.py, plus
each day's micronutrient and leucine totals. Run after scripts/recalc.py (the workbook needs
cached values). Prints a short report; exits 1 on any mismatch beyond rounding.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mealplan as M
import build_workbook as B
from openpyxl import load_workbook

TOL = 0.02  # relative


def close(a, b):
    a, b = float(a or 0), float(b or 0)
    return abs(a - b) <= max(TOL * max(abs(a), abs(b)), 0.05)


def main():
    plan = M.load(sys.argv[1])
    res = M.compute(plan)
    wb = load_workbook(sys.argv[2], data_only=True)
    ws = wb["Week summary"]
    bad = []
    if ws["C5"].value is None:
        print("Workbook has no cached values — run scripts/recalc.py first.")
        sys.exit(2)
    # every distinct day definition of the cycle: the 7 template days plus each week override
    groups = M.day_groups(plan)
    cdays = res["cycle_days"]                      # same order as day_groups()
    heads = [B.day_heading(plan, g) for g in groups]
    rows = {ws.cell(r, 1).value: r for r in range(5, 5 + len(groups))}
    for (title, row_label), cd in zip(heads, cdays):
        n = cd["total"]["n"]
        r = rows.get(row_label)
        if r is None:
            bad.append(f"Week summary: no row for {row_label}")
            continue
        for col, k in (("C", "kcal"), ("D", "protein_g"), ("J", "salt_g")):
            v = ws[f"{col}{r}"].value
            if not close(v, n[k]):
                bad.append(f"{row_label} {k}: workbook {v} vs engine {n[k]:.2f}")
    mic, eaa = wb["Micros"], wb["EAA"]
    micro_keys = list(M.MICRO_LABELS)
    # a day block is its exact heading (the day sheet's title) followed by the "Meal" header row;
    # meal names may contain " — " too, so nothing else switches the current day
    titles = {title: i for i, (title, _) in enumerate(heads)}
    for sheet, keys, first_col in ((mic, micro_keys, 2), (eaa, M.AAS, 3)):
        cur, checked = None, []
        for r in range(1, sheet.max_row + 1):
            a = sheet.cell(r, 1).value
            if a in titles and sheet.cell(r + 1, 1).value == "Meal":
                cur = titles[a]
                continue
            if a == "Day total" and cur is not None:
                src = cdays[cur]["total"]["aa" if sheet is eaa else "n"]
                lab = heads[cur][1]
                for j, k in enumerate(keys):
                    v = sheet.cell(r, first_col + j).value
                    if not close(v, src.get(k, 0)):
                        bad.append(f"{sheet.title} {lab} {k}: workbook {v} vs engine {src.get(k, 0):.3f}")
                checked.append(cur)
                cur = None
        if sorted(checked) != list(range(len(groups))):
            missing = [heads[i][1] for i in range(len(groups)) if i not in checked]
            extra = sorted({heads[i][1] for i in checked if checked.count(i) > 1})
            bad.append(f"{sheet.title}: day totals checked for {len(checked)} of {len(groups)} days"
                       + (f" — missing {', '.join(missing)}" if missing else "")
                       + (f" — repeated {', '.join(extra)}" if extra else ""))
    if bad:
        print(f"{len(bad)} mismatches:\n" + "\n".join(bad[:40]))
        sys.exit(1)
    print("workbook matches engine: day kcal/protein/salt, micronutrient and amino-acid day totals")


if __name__ == "__main__":
    main()
