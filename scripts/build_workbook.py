#!/usr/bin/env python3
"""Build the formula-driven meal-plan workbook from plan.json.

  python build_workbook.py plan.json Meal_Plan_Macros.xlsx

Sheet layout (matches the format established in the user's project workbook):
  Week summary · Micros · EAA · Ingredients · Mon … Sun
Inputs are blue (grams on day sheets, per-100 g values, targets), cross-sheet links are green,
calculations are black. Every nutrient number is a live formula back to the Ingredients sheet,
so editing a gram amount or a label value recalculates days, micros, amino acids and the week.
Run scripts/recalc.py on the output afterwards and fix anything it reports.
"""
import sys, json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.comments import Comment

sys.path.insert(0, __import__("os").path.dirname(__file__))
import mealplan as M

FONT = "Arial"
BLUE, GREEN, BLACK, GREY, RED = "0000FF", "008000", "000000", "666666", "C00000"
HDR_FILL = PatternFill("solid", fgColor="E8ECE6")
MEAL_FILL = PatternFill("solid", fgColor="F4F6F2")
TOT_FILL = PatternFill("solid", fgColor="D9DFD6")
THIN = Side(style="thin", color="BBBBBB")


def f(color=BLACK, bold=False, size=10, italic=False):
    return Font(name=FONT, color=color, bold=bold, size=size, italic=italic)


def put(ws, ref, value, color=BLACK, bold=False, fmt=None, fill=None, italic=False, size=10, wrap=False):
    c = ws[ref]
    c.value = value
    c.font = f(color, bold, size, italic)
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    if wrap:
        c.alignment = Alignment(wrap_text=True, vertical="top")
    return c


MAC_COLS = [("kcal", "kcal", "#,##0"), ("protein_g", "Protein g", "0"), ("fat_g", "Fat g", "0"),
            ("satfat_g", "of which saturated g", "0"), ("unsat", "of which unsaturated g", "0"),
            ("carb_g", "Carbs g", "0"), ("fiber_g", "Fiber g", "0"), ("salt_g", "Salt g", "0.0")]
MICRO_KEYS = list(M.MICRO_LABELS.keys())
AA_KEYS = list(M.AA_LABELS.keys())
ING_FIRST = 6
ING_LAST = 500
# Ingredients columns: A name, B..I macros (kcal, P, fat, sat, unsat, carbs, fiber, salt), J source,
# K.. micros (23), then 11 amino acids, then digestibility
MIC0 = 11                      # K
AA0 = MIC0 + len(MICRO_KEYS)   # first AA column
DIG = AA0 + len(AA_KEYS)


def ing_rng(col):
    c = L(col)
    return f"Ingredients!${c}${ING_FIRST}:${c}${ING_LAST}"


def build_ingredients(wb, plan):
    ws = wb.create_sheet("Ingredients")
    put(ws, "A1", "Ingredient database — values per 100 g (or 100 ml)", bold=True, size=13)
    put(ws, "A2", "Blue = inputs. Prefer label values of the exact product bought; the Source column says where each row "
                  "came from (label / USDA FDC id / BLS / Open Food Facts). Empty micronutrient cell = no data yet (counts as 0).",
        color=GREY, italic=True)
    put(ws, "A3", "Unsaturated = fat − saturated (mono + poly; trans fat treated as 0). Carbs are net carbs as on EU labels; "
                  "fiber is listed separately.", color=GREY, italic=True)
    put(ws, L(MIC0) + "4", "Micronutrients per 100 g — fold/unfold with the [–] above the column letters. Empty = not entered yet.",
        color=GREY, italic=True)
    put(ws, L(AA0) + "4", "Essential amino acids, g per 100 g — fold/unfold above the column letters.", color=GREY, italic=True)
    heads = ["Ingredient"] + [h for _, h, _ in MAC_COLS] + ["Source / product matched"] + \
            [f"{M.MICRO_LABELS[k][0]} ({M.MICRO_LABELS[k][1]})" for k in MICRO_KEYS] + \
            [f"{M.AA_LABELS[a]} (g)" for a in AA_KEYS] + ["Digestibility (0–1)"]
    for i, h in enumerate(heads, 1):
        c = put(ws, f"{L(i)}5", h, bold=True, fill=HDR_FILL, wrap=True)
    r = ING_FIRST
    rows = {}
    for key, ing in sorted(plan["ingredients"].items(), key=lambda kv: (kv[1].get("category", ""), kv[1]["name"])):
        p = ing["per100"]
        put(ws, f"A{r}", ing["name"], color=BLUE)
        vals = [p.get("kcal"), p.get("protein_g"), p.get("fat_g"), p.get("satfat_g"), None, p.get("carb_g"), p.get("fiber_g"), p.get("salt_g")]
        for j, (v, (_, _, fmt)) in enumerate(zip(vals, MAC_COLS)):
            col = L(2 + j)
            if j == 4:
                put(ws, f"{col}{r}", f"=IF(D{r}=\"\",\"\",D{r}-N(E{r}))", fmt="0.0")
            elif v is not None:
                put(ws, f"{col}{r}", v, color=BLUE, fmt="0.0#")
        put(ws, f"J{r}", ing.get("source", ""), color=BLUE)
        for j, k in enumerate(MICRO_KEYS):
            v = p.get(k)
            if v is None and k == "sodium_mg" and p.get("salt_g") is not None:
                put(ws, f"{L(MIC0 + j)}{r}", f"=I{r}*400", fmt="0")
            elif v is not None:
                put(ws, f"{L(MIC0 + j)}{r}", v, color=BLUE, fmt="0.0##")
        aa = ing.get("aa") or {}
        for j, a in enumerate(AA_KEYS):
            if a in aa:
                put(ws, f"{L(AA0 + j)}{r}", aa[a], color=BLUE, fmt="0.000")
        if "digestibility" in ing:
            put(ws, f"{L(DIG)}{r}", ing["digestibility"], color=BLUE, fmt="0.00")
        rows[key] = r
        r += 1
    ws.column_dimensions["A"].width = 34
    for i in range(2, 10):
        ws.column_dimensions[L(i)].width = 11
    ws.column_dimensions["J"].width = 44
    for i in range(MIC0, DIG + 1):
        ws.column_dimensions[L(i)].width = 12
    ws.column_dimensions.group(L(MIC0), L(AA0 - 1), hidden=False, outline_level=1)
    ws.column_dimensions.group(L(AA0), L(DIG - 1), hidden=False, outline_level=1)
    ws.freeze_panes = "B6"
    ws.row_dimensions[5].height = 42
    return rows


def day_title(plan, day):
    """Sheet title of a template day, e.g. "Wednesday — Training (legs)" — also the day heading on Micros/EAA."""
    d = plan["days"][day]
    title = f"{M.DAYNAMES[day]} — {d.get('type', 'training').capitalize()}"
    if d.get("label") and d["label"] != M.DAYNAMES[day]:
        title += d["label"][len(M.DAYNAMES[day]):]
    return title


def build_day(wb, plan, day):
    d = plan["days"][day]
    ws = wb.create_sheet(day)
    T = plan.get("targets", {})
    t = T.get(d.get("type", "training"), {})
    title = day_title(plan, day)
    put(ws, "A1", title, bold=True, size=13)
    free = T.get("free_kcal")
    put(ws, "A2", f"Target: {t.get('kcal', 0):,} kcal planned" + (f" (+{free} free)" if free else "") +
        ". Grams in blue are editable; nutrients come from the Ingredients sheet.", color=GREY, italic=True)
    heads = ["Meal / ingredient", "Sub-group", "Amount (g/ml)", "Ingredient (lookup)"] + [h for _, h, _ in MAC_COLS]
    for i, h in enumerate(heads, 1):
        put(ws, f"{L(i)}4", h, bold=True, fill=HDR_FILL, wrap=True)
    r = 5
    meals = []
    for m in d.get("meals", []):
        put(ws, f"A{r}", m["name"], bold=True, fill=MEAL_FILL)
        for c in range(2, 13):
            ws.cell(r, c).fill = MEAL_FILL
        if m.get("time"):
            put(ws, f"B{r}", m["time"], color=GREY, fill=MEAL_FILL)
        r += 1
        first = r
        for p in m.get("parts", []):
            for k, g, sub, _ in M.part_lines(plan, p):
                ing = plan["ingredients"][k]
                put(ws, f"A{r}", "   " + ing["name"])
                put(ws, f"B{r}", sub, color=GREY)
                put(ws, f"C{r}", round(g, 2), color=BLUE, fmt="0.#")
                put(ws, f"D{r}", ing["name"], color=GREEN)
                for j, (_, _, fmt) in enumerate(MAC_COLS):
                    col = L(5 + j)
                    put(ws, f"{col}{r}", f"=IFERROR($C{r}*N(VLOOKUP($D{r},Ingredients!$A${ING_FIRST}:$I${ING_LAST},{2 + j},FALSE))/100,0)", fmt=fmt)
                r += 1
        last = r - 1
        put(ws, f"A{r}", f"Subtotal — {m['name']}", bold=True)
        for j, (_, _, fmt) in enumerate(MAC_COLS):
            col = L(5 + j)
            put(ws, f"{col}{r}", f"=SUM({col}{first}:{col}{last})", bold=True, fmt=fmt)
        meals.append({"name": m["name"], "first": first, "last": last, "sub": r})
        r += 2
    tot = r
    put(ws, f"A{tot}", "Day total", bold=True, fill=TOT_FILL)
    for j, (_, _, fmt) in enumerate(MAC_COLS):
        col = L(5 + j)
        put(ws, f"{col}{tot}", "=" + "+".join(f"{col}{m['sub']}" for m in meals), bold=True, fmt=fmt, fill=TOT_FILL)
    for c in range(2, 5):
        ws.cell(tot, c).fill = TOT_FILL
    put(ws, f"A{tot + 1}", "Target")
    tgt_map = {"kcal": "kcal", "protein_g": "protein_g", "fat_g": "fat_g", "carb_g": "carb_g"}
    for j, (k, _, fmt) in enumerate(MAC_COLS):
        if k in tgt_map and tgt_map[k] in t:
            put(ws, f"{L(5 + j)}{tot + 1}", t[tgt_map[k]], color=BLUE, fmt=fmt)
    if T.get("fiber_min"):
        put(ws, f"K{tot + 1}", T["fiber_min"], color=BLUE)
    if T.get("salt_max"):
        put(ws, f"L{tot + 1}", T["salt_max"], color=BLUE, fmt="0.0")
    put(ws, f"A{tot + 2}", "Δ vs target")
    for j, (k, _, fmt) in enumerate(MAC_COLS):
        col = L(5 + j)
        if ws[f"{col}{tot + 1}"].value is not None:
            put(ws, f"{col}{tot + 2}", f"={col}{tot}-{col}{tot + 1}", fmt="+#,##0;-#,##0;0")
    put(ws, f"A{tot + 3}", "Energy split (% of kcal)")
    put(ws, f"F{tot + 3}", f"=IFERROR(F{tot}*4/E{tot},0)", fmt="0%")
    put(ws, f"G{tot + 3}", f"=IFERROR(G{tot}*9/E{tot},0)", fmt="0%")
    put(ws, f"J{tot + 3}", f"=IFERROR(J{tot}*4/E{tot},0)", fmt="0%")
    put(ws, f"A{tot + 4}", "Protein per kg body weight")
    put(ws, f"F{tot + 4}", f"=F{tot}/{plan.get('meta', {}).get('bw_kg', 80)}", fmt="0.00")
    ws.conditional_formatting.add(f"E{tot + 2}", FormulaRule(formula=[f"ABS(E{tot + 2})>0.05*E{tot + 1}"], font=Font(name=FONT, color="C00000", bold=True)))
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 30
    for i in range(5, 13):
        ws.column_dimensions[L(i)].width = 11
    ws.row_dimensions[4].height = 30
    ws.freeze_panes = "B5"
    return {"sheet": day, "meals": meals, "total": tot, "type": d.get("type", "training"), "title": title}


def build_micros(wb, plan, days):
    ws = wb.create_sheet("Micros")
    put(ws, "A1", "Micronutrients per meal and day", bold=True, size=13)
    put(ws, "A2", "Live formulas: grams on each day sheet × per-100 g values on the Ingredients sheet. Empty ingredient cells count as 0, "
                  "so a nutrient with missing data reads low — check the Ingredients sheet before acting on a gap.", color=GREY, italic=True)
    r = 4
    totals = {}
    for dinfo in days:
        put(ws, f"A{r}", dinfo["title"], bold=True)
        r += 1
        put(ws, f"A{r}", "Meal", bold=True, fill=HDR_FILL)
        for j, k in enumerate(MICRO_KEYS):
            put(ws, f"{L(2 + j)}{r}", f"{M.MICRO_LABELS[k][0]} ({M.MICRO_LABELS[k][1]})", bold=True, fill=HDR_FILL, wrap=True)
        ws.row_dimensions[r].height = 42
        r += 1
        first = r
        for m in dinfo["meals"]:
            put(ws, f"A{r}", m["name"])
            sh = dinfo["sheet"]
            for j, k in enumerate(MICRO_KEYS):
                put(ws, f"{L(2 + j)}{r}",
                    f"=SUMPRODUCT(SUMIF({ing_rng(1)},{sh}!$D${m['first']}:$D${m['last']},{ing_rng(MIC0 + j)}),{sh}!$C${m['first']}:$C${m['last']})/100",
                    fmt="0.0#")
            r += 1
        put(ws, f"A{r}", "Day total", bold=True, fill=TOT_FILL)
        for j, _ in enumerate(MICRO_KEYS):
            col = L(2 + j)
            put(ws, f"{col}{r}", f"=SUM({col}{first}:{col}{r - 1})", bold=True, fmt="0.0#", fill=TOT_FILL)
        totals[dinfo["sheet"]] = r
        r += 2
    ws.column_dimensions["A"].width = 30
    for j in range(len(MICRO_KEYS)):
        ws.column_dimensions[L(2 + j)].width = 12
    ws.freeze_panes = "B4"
    return totals


def build_eaa(wb, plan, days):
    ws = wb.create_sheet("EAA")
    put(ws, "A1", "Essential amino acids per meal and day", bold=True, size=13)
    put(ws, "A2", "Live formulas from the Ingredients sheet (g amino acid per 100 g). Leucine ≥ 2.5 g per protein feeding is the "
                  "usual threshold for a full muscle-protein-synthesis response.", color=GREY, italic=True)
    heads = ["Meal", "Protein (g)"] + [f"{M.AA_LABELS[a]} (g)" for a in AA_KEYS] + ["Total of the 11 (g)", "Leucine ≥ 2.5 g?"]
    r = 4
    totals = {}
    for dinfo in days:
        put(ws, f"A{r}", dinfo["title"], bold=True)
        r += 1
        for i, h in enumerate(heads, 1):
            put(ws, f"{L(i)}{r}", h, bold=True, fill=HDR_FILL, wrap=True)
        ws.row_dimensions[r].height = 30
        r += 1
        first = r
        sh = dinfo["sheet"]
        for m in dinfo["meals"]:
            put(ws, f"A{r}", m["name"])
            put(ws, f"B{r}", f"={sh}!F{m['sub']}", color=GREEN, fmt="0.0")
            for j, a in enumerate(AA_KEYS):
                put(ws, f"{L(3 + j)}{r}",
                    f"=SUMPRODUCT(SUMIF({ing_rng(1)},{sh}!$D${m['first']}:$D${m['last']},{ing_rng(AA0 + j)}),{sh}!$C${m['first']}:$C${m['last']})/100",
                    fmt="0.00")
            put(ws, f"N{r}", f"=SUM(C{r}:M{r})", fmt="0.0")
            put(ws, f"O{r}", f'=IF(B{r}<10,"–",IF(E{r}>=2.5,"yes","no"))')
            r += 1
        put(ws, f"A{r}", "Day total", bold=True, fill=TOT_FILL)
        for c in range(2, 15):
            col = L(c)
            put(ws, f"{col}{r}", f"=SUM({col}{first}:{col}{r - 1})", bold=True, fmt="0.0", fill=TOT_FILL)
        totals[sh] = r
        r += 2
    ws.conditional_formatting.add(f"O1:O{r}", CellIsRule(operator="equal", formula=['"no"'], font=Font(name=FONT, color="C00000", bold=True)))
    ws.column_dimensions["A"].width = 30
    for c in range(2, 16):
        ws.column_dimensions[L(c)].width = 12
    ws.freeze_panes = "B4"
    return totals


def build_week(wb, plan, days, mic_tot, eaa_tot):
    ws = wb["Week summary"]
    T = plan.get("targets", {})
    put(ws, "A1", "Week summary — nutrients per day", bold=True, size=13)
    put(ws, "A2", "Day values link to the day sheets (green). Blue = targets from the plan plus general references "
                  "(fiber ≥ 30 g, salt ≤ 6 g).", color=GREY, italic=True)
    notes = plan.get("meta", {}).get("workbook_notes", [])
    alerts = M.allergy_alerts(plan)
    if alerts:  # the allergy line takes row 3; plan notes move up beside the legend
        put(ws, "A3", "ALLERGY: " + " · ".join(a["text"] for a in alerts),
            color=RED if any(a["level"] == "warn" for a in alerts) else BLACK, bold=True)
        if notes:
            ws["A2"].value += " · " + " · ".join(notes)
    elif notes:
        put(ws, "A3", " · ".join(notes), color=GREY, italic=True)
    heads = ["Day", "Type"] + [h for _, h, _ in MAC_COLS] + ["kcal target", "Δ kcal", "Protein target", "Δ protein", "Fiber min", "Salt max"]
    for i, h in enumerate(heads, 1):
        put(ws, f"{L(i)}4", h, bold=True, fill=HDR_FILL, wrap=True)
    ws.row_dimensions[4].height = 30
    r = 5
    for dinfo in days:
        sh, tot = dinfo["sheet"], dinfo["total"]
        t = T.get(dinfo["type"], {})
        put(ws, f"A{r}", M.DAYNAMES[sh])
        put(ws, f"B{r}", dinfo["type"].capitalize())
        for j, (_, _, fmt) in enumerate(MAC_COLS):
            put(ws, f"{L(3 + j)}{r}", f"={sh}!{L(5 + j)}{tot}", color=GREEN, fmt=fmt)
        put(ws, f"K{r}", t.get("kcal"), color=BLUE, fmt="#,##0")
        put(ws, f"L{r}", f"=C{r}-K{r}", fmt="+#,##0;-#,##0;0")
        put(ws, f"M{r}", t.get("protein_g"), color=BLUE)
        put(ws, f"N{r}", f"=D{r}-M{r}", fmt="+0;-0;0")
        put(ws, f"O{r}", T.get("fiber_min", 30), color=BLUE)
        put(ws, f"P{r}", T.get("salt_max", 6), color=BLUE)
        r += 1
    put(ws, f"A{r}", "Week average", bold=True, fill=TOT_FILL)
    for c in range(3, 15):
        col = L(c)
        put(ws, f"{col}{r}", f"=AVERAGE({col}5:{col}{r - 1})", bold=True, fmt="#,##0" if c in (3, 11, 12) else "0", fill=TOT_FILL)
    ws.conditional_formatting.add(f"L5:L{r - 1}", FormulaRule(formula=["ABS(L5)>0.05*K5"], font=Font(name=FONT, color="C00000", bold=True)))
    ws.conditional_formatting.add(f"I5:I{r - 1}", FormulaRule(formula=["I5<O5"], font=Font(name=FONT, color="C00000", bold=True)))

    # micronutrients
    r += 3
    put(ws, f"A{r}", "Micronutrients per day (links to the Micros sheet)", bold=True, size=12)
    r += 1
    put(ws, f"A{r}", "Day", bold=True, fill=HDR_FILL)
    for j, k in enumerate(MICRO_KEYS):
        put(ws, f"{L(2 + j)}{r}", f"{M.MICRO_LABELS[k][0]} ({M.MICRO_LABELS[k][1]})", bold=True, fill=HDR_FILL, wrap=True)
    ws.row_dimensions[r].height = 42
    r += 1
    m0 = r
    for dinfo in days:
        put(ws, f"A{r}", M.DAYNAMES[dinfo["sheet"]])
        for j, _ in enumerate(MICRO_KEYS):
            put(ws, f"{L(2 + j)}{r}", f"=Micros!{L(2 + j)}{mic_tot[dinfo['sheet']]}", color=GREEN, fmt="0.0#")
        r += 1
    m1 = r - 1
    mt = T.get("micros", {})
    rows = {}
    for label, key, color in (("Food average", None, BLACK), ("Supplements / day", "supplement", BLUE), ("Average incl. supplements", None, BLACK),
                              ("Floor (reference)", "floor", BLUE), ("Aim (athlete)", "aim", BLUE), ("Upper limit", "ul", BLUE), ("% of aim", None, BLACK)):
        put(ws, f"A{r}", label, bold=True)
        rows[label] = r
        for j, k in enumerate(MICRO_KEYS):
            col = L(2 + j)
            if label == "Food average":
                put(ws, f"{col}{r}", f"=AVERAGE({col}{m0}:{col}{m1})", fmt="0.0#")
            elif label == "Average incl. supplements":
                put(ws, f"{col}{r}", f"={col}{rows['Food average']}+N({col}{rows['Supplements / day']})", fmt="0.0#")
            elif label == "% of aim":
                put(ws, f"{col}{r}", f"=IF(N({col}{rows['Aim (athlete)']})=0,\"\",{col}{rows['Average incl. supplements']}/{col}{rows['Aim (athlete)']})", fmt="0%")
            else:
                v = (mt.get(k) or {}).get(key)
                if v is not None:
                    c = put(ws, f"{col}{r}", v, color=color)
                    note = (mt.get(k) or {}).get("supplement_note") if key == "supplement" else None
                    if note:
                        c.comment = Comment(note, "plan")
        r += 1
    pr = rows["% of aim"]
    rng = f"B{pr}:{L(1 + len(MICRO_KEYS))}{pr}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=["0.9"], font=Font(name=FONT, color="C00000", bold=True)))
    ar, ur = rows["Average incl. supplements"], rows["Upper limit"]
    ws.conditional_formatting.add(f"B{ar}:{L(1 + len(MICRO_KEYS))}{ar}",
                                  FormulaRule(formula=[f"AND(N(B{ur})>0,B{ar}>B{ur})"], fill=PatternFill("solid", fgColor="F8D7D3")))

    # amino acids
    r += 2
    put(ws, f"A{r}", "Essential amino acids per day (links to the EAA sheet)", bold=True, size=12)
    r += 1
    heads = ["Day", "Protein (g)"] + [f"{M.AA_LABELS[a]} (g)" for a in AA_KEYS]
    for i, h in enumerate(heads, 1):
        put(ws, f"{L(i)}{r}", h, bold=True, fill=HDR_FILL, wrap=True)
    r += 1
    a0 = r
    for dinfo in days:
        put(ws, f"A{r}", M.DAYNAMES[dinfo["sheet"]])
        for c in range(2, 14):
            put(ws, f"{L(c)}{r}", f"=EAA!{L(c)}{eaa_tot[dinfo['sheet']]}", color=GREEN, fmt="0.0")
        r += 1
    a1 = r - 1
    put(ws, f"A{r}", "Week total", bold=True)
    for c in range(2, 14):
        put(ws, f"{L(c)}{r}", f"=SUM({L(c)}{a0}:{L(c)}{a1})", fmt="0")
    wt = r
    r += 2
    put(ws, f"A{r}", "Scoring vs FAO 2013 adult pattern (mg per g protein; unadjusted for digestibility — the cooking pages show the digestibility-corrected estimate)",
        color=GREY, italic=True)
    r += 1
    groups = [("Histidine", ["C"], 16), ("Isoleucine", ["D"], 30), ("Leucine", ["E"], 61), ("Lysine", ["F"], 48),
              ("Met + Cys", ["G", "H"], 23), ("Phe + Tyr", ["I", "J"], 41), ("Threonine", ["K"], 25),
              ("Tryptophan", ["L"], 6.6), ("Valine", ["M"], 40)]
    put(ws, f"A{r}", "Amino acid", bold=True, fill=HDR_FILL)
    put(ws, f"A{r + 1}", "mg per g protein (week)", bold=True)
    put(ws, f"A{r + 2}", "FAO 2013 pattern", bold=True)
    put(ws, f"A{r + 3}", "Score", bold=True)
    for i, (name, cols, pat) in enumerate(groups):
        col = L(2 + i)
        put(ws, f"{col}{r}", name, bold=True, fill=HDR_FILL)
        put(ws, f"{col}{r + 1}", "=(" + "+".join(f"{c}{wt}" for c in cols) + f")*1000/$B${wt}", fmt="0.0")
        put(ws, f"{col}{r + 2}", pat, color=BLUE)
        put(ws, f"{col}{r + 3}", f"={col}{r + 1}/{col}{r + 2}", fmt="0%")
    last = L(1 + len(groups))
    put(ws, f"A{r + 4}", "Limiting amino acid", bold=True)
    put(ws, f"B{r + 4}", f"=INDEX(B{r}:{last}{r},MATCH(MIN(B{r + 3}:{last}{r + 3}),B{r + 3}:{last}{r + 3},0))", bold=True)
    ws.conditional_formatting.add(f"B{r + 3}:{last}{r + 3}", CellIsRule(operator="lessThan", formula=["1"], font=Font(name=FONT, color="C00000", bold=True)))
    ws.column_dimensions["A"].width = 30
    for c in range(2, 26):
        ws.column_dimensions[L(c)].width = 12
    ws.freeze_panes = "B5"


def build(plan, out):
    wb = Workbook()
    wb.active.title = "Week summary"
    wb.create_sheet("Micros")  # placeholders keep the sheet order: Week summary, Micros, EAA, Ingredients, Mon..Sun
    wb.create_sheet("EAA")
    del wb["Micros"], wb["EAA"]
    build_ingredients(wb, plan)
    days = [build_day(wb, plan, d) for d in M.WEEKDAYS]
    mic = build_micros(wb, plan, days)
    eaa = build_eaa(wb, plan, days)
    build_week(wb, plan, days, mic, eaa)
    order = ["Week summary", "Micros", "EAA", "Ingredients"] + M.WEEKDAYS
    wb._sheets = [wb[n] for n in order]
    wb.active = 0
    wb.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    plan = M.load(sys.argv[1])
    build(plan, sys.argv[2] if len(sys.argv) > 2 else "Meal_Plan_Macros.xlsx")
