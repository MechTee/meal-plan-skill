#!/usr/bin/env python3
"""Core engine for the athlete-meal-plan skill.

Reads a plan.json (schema: references/plan-format.md) and computes everything the
artifacts need: per-recipe / per-meal / per-day nutrients, amino-acid scores,
batch-portion inventory over the cooking cycle, dated shopping runs with pack
rounding and carry-over, costs, and target checks.

CLI:
  python mealplan.py check   plan.json            -> markdown report (targets, micros, batches, cost)
  python mealplan.py compute plan.json out.json   -> computed.json used by the builders
"""
import json, math, sys, datetime as dt
from collections import defaultdict, OrderedDict

MACROS = ["kcal", "protein_g", "fat_g", "satfat_g", "carb_g", "sugar_g", "fiber_g", "salt_g"]
MICROS = ["thiamin_mg", "riboflavin_mg", "niacin_mg", "pantothenic_mg", "b6_mg", "biotin_ug",
          "folate_ug", "b12_ug", "potassium_mg", "phosphorus_mg", "magnesium_mg", "calcium_mg",
          "zinc_mg", "iron_mg", "selenium_ug", "iodine_ug", "vitA_rae_ug", "vitC_mg", "vitD_ug",
          "vitE_mg", "vitK_ug", "sodium_mg", "nitrate_mg"]
NUTRIENTS = MACROS + MICROS
AAS = ["his", "ile", "leu", "lys", "met", "cys", "phe", "tyr", "thr", "trp", "val"]
# FAO 2013 scoring pattern, older child/adolescent/adult, mg per g protein
FAO = {"his": 16, "ile": 30, "leu": 61, "lys": 48, "saa": 23, "aaa": 41, "thr": 25, "trp": 6.6, "val": 40}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAYNAMES = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday",
            "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}

# Labels used by the workbook and pages (key, label, unit)
MICRO_LABELS = OrderedDict([
    ("thiamin_mg", ("B1 Thiamin", "mg")), ("riboflavin_mg", ("B2 Riboflavin", "mg")),
    ("niacin_mg", ("B3 Niacin", "mg")), ("pantothenic_mg", ("B5 Pantothenic acid", "mg")),
    ("b6_mg", ("B6", "mg")), ("biotin_ug", ("B7 Biotin", "µg")), ("folate_ug", ("B9 Folate", "µg")),
    ("b12_ug", ("B12", "µg")), ("potassium_mg", ("Potassium (K)", "mg")),
    ("phosphorus_mg", ("Phosphorus (P)", "mg")), ("magnesium_mg", ("Magnesium (Mg)", "mg")),
    ("calcium_mg", ("Calcium (Ca)", "mg")), ("zinc_mg", ("Zinc (Zn)", "mg")), ("iron_mg", ("Iron (Fe)", "mg")),
    ("selenium_ug", ("Selenium (Se)", "µg")), ("iodine_ug", ("Iodine (I)", "µg")),
    ("vitA_rae_ug", ("Vitamin A", "µg RAE")), ("vitC_mg", ("Vitamin C", "mg")), ("vitD_ug", ("Vitamin D", "µg")),
    ("vitE_mg", ("Vitamin E", "mg")), ("vitK_ug", ("Vitamin K", "µg")), ("sodium_mg", ("Sodium (Na)", "mg")),
    ("nitrate_mg", ("Nitrate", "mg")),
])
AA_LABELS = OrderedDict([("his", "Histidine"), ("ile", "Isoleucine"), ("leu", "Leucine"), ("lys", "Lysine"),
                         ("met", "Methionine"), ("cys", "Cysteine"), ("phe", "Phenylalanine"),
                         ("tyr", "Tyrosine"), ("thr", "Threonine"), ("trp", "Tryptophan"), ("val", "Valine")])


class PlanError(Exception):
    pass


# ----------------------------------------------------------------------------- loading

def load(path):
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    validate(plan)
    return plan


def _item(it):
    """Recipe item -> (key, amount, note, display). Accepts list or dict."""
    if isinstance(it, dict):
        return it["ingredient"], float(it["amount"]), it.get("note"), it.get("display")
    it = list(it) + [None, None]
    return it[0], float(it[1]), it[2], it[3]


ALLERGY_STATUSES = ("none", "known", "unknown")


def validate(plan):
    errs = []
    ing = plan.get("ingredients", {})
    rec = plan.get("recipes", {})
    al = plan.get("meta", {}).get("allergies")
    if not isinstance(al, dict) or al.get("status") not in ALLERGY_STATUSES:
        errs.append('meta.allergies.status is required: "none", "known" or "unknown" '
                    '(an unanswered allergy question is "unknown", never "none")')
    elif al["status"] == "known" and not al.get("items"):
        errs.append('meta.allergies.status is "known" but meta.allergies.items is empty')
    elif al["status"] == "none" and al.get("items"):
        errs.append('meta.allergies.status is "none" but items are listed — use "known"')
    names = set()
    for k, v in ing.items():
        if "name" not in v:
            errs.append(f"ingredient {k}: missing name")
        elif v["name"] in names:
            errs.append(f"ingredient name '{v['name']}' is used twice (names are workbook lookup keys)")
        names.add(v.get("name"))
        if "per100" not in v:
            errs.append(f"ingredient {k}: missing per100")
    for k, r in rec.items():
        if r.get("kind") not in ("batch", "single"):
            errs.append(f"recipe {k}: kind must be 'batch' or 'single'")
        for it in r.get("items", []):
            key = _item(it)[0]
            if key not in ing:
                errs.append(f"recipe {k}: unknown ingredient '{key}'")
    for wk, dd in [("template", plan.get("days", {}))] + [
            (f"week {w}", d) for w, d in plan.get("week_overrides", {}).items()]:
        for day, d in dd.items():
            if day not in WEEKDAYS:
                errs.append(f"{wk}: unknown day '{day}' (use Mon..Sun)")
            for m in d.get("meals", []):
                for p in m.get("parts", []):
                    if "recipe" in p and p["recipe"] not in rec:
                        errs.append(f"{wk} {day} {m.get('name')}: unknown recipe '{p['recipe']}'")
                    if "ingredient" in p and p["ingredient"] not in ing:
                        errs.append(f"{wk} {day} {m.get('name')}: unknown ingredient '{p['ingredient']}'")
    missing = [d for d in WEEKDAYS if d not in plan.get("days", {})]
    if missing:
        errs.append(f"days missing from template week: {missing}")
    sd = plan.get("cycle", {}).get("start_date")
    if sd and dt.date.fromisoformat(sd).weekday() != 0:
        errs.append("cycle.start_date must be a Monday (week 1, day 1)")
    if errs:
        raise PlanError("\n".join(errs))


# ----------------------------------------------------------------------------- nutrients

def ing_nutrients(ingr, grams):
    """Nutrients for `grams` of an ingredient. None in per100 = unknown (tracked as missing)."""
    p = ingr["per100"]
    out, missing = {}, {}
    for k in NUTRIENTS:
        v = p.get(k)
        if v is None and k == "sodium_mg" and p.get("salt_g") is not None:
            v = p["salt_g"] * 400.0
        if v is None:
            out[k] = 0.0
            missing[k] = grams
        else:
            out[k] = v * grams / 100.0
    aa = ingr.get("aa") or {}
    aa_out = {a: (aa.get(a) or 0.0) * grams / 100.0 for a in AAS}
    dig = ingr.get("digestibility", 0.85)
    return out, missing, aa_out, dig


class Acc:
    """Accumulates nutrients, missing-data mass, amino acids and digestible protein."""

    def __init__(self):
        self.n = defaultdict(float)
        self.miss = defaultdict(float)
        self.aa = defaultdict(float)
        self.daa = defaultdict(float)  # digestible amino acids
        self.grams = 0.0

    def add_ing(self, ingr, grams):
        n, miss, aa, dig = ing_nutrients(ingr, grams)
        for k, v in n.items():
            self.n[k] += v
        for k, v in miss.items():
            self.miss[k] += v
        for a, v in aa.items():
            self.aa[a] += v
            self.daa[a] += v * dig
        self.grams += grams

    def add(self, other, f=1.0):
        for src, dst in ((other.n, self.n), (other.miss, self.miss), (other.aa, self.aa), (other.daa, self.daa)):
            for k, v in src.items():
                dst[k] += v * f
        self.grams += other.grams * f

    def score(self):
        p = self.n["protein_g"]
        if p < 3 or sum(self.aa.values()) <= 0:
            return None
        d = self.daa
        vals = {"his": d["his"], "ile": d["ile"], "leu": d["leu"], "lys": d["lys"],
                "saa": d["met"] + d["cys"], "aaa": d["phe"] + d["tyr"], "thr": d["thr"],
                "trp": d["trp"], "val": d["val"]}
        scores = {k: round(v * 1000.0 / p / FAO[k] * 100) for k, v in vals.items()}
        lim = min(scores, key=scores.get)
        return {"scores": scores, "limiting": lim, "diaas_est": scores[lim]}

    def mshare(self):
        if self.grams <= 0:
            return {}
        return {k: round(v / self.grams, 3) for k, v in self.miss.items() if v / self.grams > 0.001}

    def export(self, nd=3):
        return {"n": {k: round(self.n.get(k, 0.0), nd) for k in NUTRIENTS},
                "aa": {a: round(self.aa.get(a, 0.0), nd) for a in AAS},
                "score": self.score(), "mshare": self.mshare()}


def recipe_acc(plan, rkey):
    r = plan["recipes"][rkey]
    acc = Acc()
    for it in r.get("items", []):
        key, amt, _, _ = _item(it)
        acc.add_ing(plan["ingredients"][key], amt)
    return acc  # whole recipe (batch) / one serving (single)


def recipe_portion_acc(plan, rkey):
    r = plan["recipes"][rkey]
    whole = recipe_acc(plan, rkey)
    if r["kind"] == "batch":
        a = Acc()
        a.add(whole, 1.0 / float(r["portions"]))
        return a
    return whole


def part_lines(plan, part):
    """Expand a meal part into ingredient lines: (ing_key, grams, subgroup, from_batch_recipe_or_None)."""
    if "ingredient" in part:
        return [(part["ingredient"], float(part["amount"]), part.get("label", ""), None)]
    rkey = part["recipe"]
    r = plan["recipes"][rkey]
    por = float(part.get("portions", 1))
    lines = []
    if r["kind"] == "batch":
        f = por / float(r["portions"])
        tag = f"{r['title']} · {fmt_num(por)} of {fmt_num(r['portions'])} portions"
        for it in r["items"]:
            k, amt, _, _ = _item(it)
            lines.append((k, amt * f, tag, rkey))
    else:
        tag = r["title"] + ("" if por == 1 else f" × {fmt_num(por)}")
        for it in r["items"]:
            k, amt, _, _ = _item(it)
            lines.append((k, amt * por, tag, None))
    return lines


def fmt_num(x):
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def day_def(plan, week, day):
    ov = plan.get("week_overrides", {}).get(str(week), {})
    return ov.get(day) or plan["days"][day]


def meal_acc(plan, meal):
    acc = Acc()
    for p in meal.get("parts", []):
        for k, g, _, _ in part_lines(plan, p):
            acc.add_ing(plan["ingredients"][k], g)
    return acc


def day_acc(plan, d):
    acc = Acc()
    meals = []
    for m in d.get("meals", []):
        ma = meal_acc(plan, m)
        acc.add(ma)
        meals.append((m, ma))
    return acc, meals


# ----------------------------------------------------------------------------- calendar

def run_date(plan, week, day, prior=False):
    sd = plan.get("cycle", {}).get("start_date")
    if not sd:
        return None
    base = dt.date.fromisoformat(sd)
    return base + dt.timedelta(days=7 * (week - 1) + WEEKDAYS.index(day) - (7 if prior else 0))


def cycle_weeks(plan):
    return int(plan.get("cycle", {}).get("weeks", 1))


def sessions(plan):
    """Expand cooking sessions into concrete (week, day, prior, {recipe: batches})."""
    out = []
    for s in plan.get("cycle", {}).get("sessions", []):
        weeks = s.get("weeks") or list(range(1, cycle_weeks(plan) + 1))
        for w in weeks:
            out.append({"week": w, "day": s.get("day", "Sun"), "prior": bool(s.get("prior", False)),
                        "label": s.get("label", "Cook day"), "cook": s["cook"]})
    return out


def _units(plan, rk):
    """Freezer containers per portion: recipe.storage_units (containers per batch) / portions."""
    r = plan["recipes"][rk]
    if r.get("storage_units") is None:
        return 1.0
    return float(r["storage_units"]) / float(r["portions"])


def _ordkey(week, day, prior, phase):
    # phase 0 = shopping, 1 = cooking, 2 = eating, so a same-day cook feeds that day's meals
    return (7 * (week - 1) + WEEKDAYS.index(day) - (7 if prior else 0), phase)


# ----------------------------------------------------------------------------- batch inventory

def inventory(plan, cycles=3):
    """Simulate batch portions over several cycles. Returns per-recipe stats and shortfalls."""
    W = cycle_weeks(plan)
    batch = [k for k, r in plan["recipes"].items() if r["kind"] == "batch"]
    events = []
    for c in range(cycles):
        for s in sessions(plan):
            t = _ordkey(s["week"], s["day"], s["prior"], 1)
            for rk, n in s["cook"].items():
                events.append((c * 7 * W + t[0], 1, c, s["week"], s["day"], rk, n * float(plan["recipes"][rk]["portions"])))
        for w in range(1, W + 1):
            for day in WEEKDAYS:
                d = day_def(plan, w, day)
                for m in d.get("meals", []):
                    for p in m.get("parts", []):
                        if "recipe" in p and plan["recipes"][p["recipe"]]["kind"] == "batch":
                            t = _ordkey(w, day, False, 2)
                            events.append((c * 7 * W + t[0], 2, c, w, day, p["recipe"], -float(p.get("portions", 1))))
    events.sort(key=lambda e: (e[0], e[1]))
    stock = defaultdict(float)
    peak = defaultdict(float)
    peak_total = 0.0
    shortfalls = []
    eaten = defaultdict(lambda: defaultdict(float))
    cooked = defaultdict(lambda: defaultdict(float))
    for t, ph, c, w, day, rk, q in events:
        stock[rk] += q
        if q < 0:
            eaten[c][rk] += -q
            if stock[rk] < -1e-9:
                shortfalls.append({"cycle": c + 1, "week": w, "day": day, "recipe": rk, "short": round(-stock[rk], 2)})
        else:
            cooked[c][rk] += q
        if c == cycles - 1:
            peak[rk] = max(peak[rk], stock[rk])
            peak_total = max(peak_total, sum(v * _units(plan, k) for k, v in stock.items() if v > 0))
    last = cycles - 1
    per = {}
    for rk in batch:
        per[rk] = {"title": plan["recipes"][rk]["title"], "eaten": eaten[last][rk], "cooked": cooked[last][rk],
                   "spare": cooked[last][rk] - eaten[last][rk], "peak_stored": round(peak[rk], 2)}
    steady_short = [s for s in shortfalls if s["cycle"] == cycles]
    first_short = [s for s in shortfalls if s["cycle"] == 1]
    return {"per_recipe": per, "peak_total_portions": round(peak_total, 2),
            "steady_shortfalls": steady_short, "startup_shortfalls": first_short}


# ----------------------------------------------------------------------------- shopping

def _runs(plan):
    """Concrete shopping runs for one cycle: list of dicts with week/day/prior/kind/covers."""
    W = cycle_weeks(plan)
    cfg = plan.get("shopping", {})
    runs = []
    st = cfg.get("stock_run", {"day": "Sat", "prior": True})
    runs.append({"id": "stock", "kind": "stock", "week": 1, "day": st.get("day", "Sat"), "prior": st.get("prior", True),
                 "label": st.get("label", "Stock-up"), "store": st.get("store", "")})
    for i, s in enumerate(sessions(plan)):
        runs.append({"id": f"batch-{s['week']}-{i}", "kind": "batch", "week": s["week"], "day": s["day"],
                     "prior": s["prior"], "label": cfg.get("batch_label", "Batch shop") + f" · {s['label']}",
                     "store": cfg.get("batch_store", ""), "session": s})
    fr = cfg.get("fresh_runs") or [{"day": "Sat", "prior": True, "covers": WEEKDAYS}]
    for w in range(1, W + 1):
        for j, f in enumerate(fr):
            runs.append({"id": f"fresh-{w}-{j}", "kind": "fresh", "week": w, "day": f["day"],
                         "prior": f.get("prior", False), "covers": f.get("covers", WEEKDAYS),
                         "label": f.get("label", "Fresh run"), "store": f.get("store", "")})
    for r in runs:
        r["date"] = run_date(plan, r["week"], r["day"], r["prior"])
        r["t"] = _ordkey(r["week"], r["day"], r["prior"], 0)
    runs.sort(key=lambda r: r["t"])
    return runs


def _buy(ingr):
    sh = ingr.get("shop")
    if not sh:
        return "none"
    return sh.get("buy", "stock")


def shopping(plan, cycles=4):
    """Dated shopping runs for the coming cycle (cycle 1, dates from cycle.start_date) with pack
    rounding, carry-over of leftovers (FIFO, with expiry from shop.shelf_days) and per-cycle pack
    counts so alternating buys ("2 bags one cycle, 1 the next") and slow movers ("lasts ~3 cycles")
    are visible. Cost is reported two ways: what cycle 1 costs at the till, and the pro-rated
    steady-state cost (need / pack size x price) that the weekly budget should use."""
    W = cycle_weeks(plan)
    ING = plan["ingredients"]
    runs = _runs(plan)
    warnings = []
    demand = defaultdict(lambda: defaultdict(float))
    stock_need = defaultdict(float)
    fresh_by_week_day = {}
    for r in runs:
        if r["kind"] == "fresh":
            for d in r["covers"]:
                if (r["week"], d) in fresh_by_week_day:
                    warnings.append(f"week {r['week']} {d} is covered by two fresh runs")
                fresh_by_week_day[(r["week"], d)] = r["id"]
    batch_run_for = {(r["week"], r["day"], r["prior"]): r["id"] for r in runs if r["kind"] == "batch"}

    def add(k, g, rid):
        b = _buy(ING[k])
        if b == "none":
            return
        if b == "stock":
            stock_need[k] += g
        elif rid:
            demand[rid][k] += g

    for w in range(1, W + 1):
        for day in WEEKDAYS:
            for m in day_def(plan, w, day).get("meals", []):
                for p in m.get("parts", []):
                    if "recipe" in p and plan["recipes"][p["recipe"]]["kind"] == "batch":
                        continue  # bought with the cook session
                    for k, g, _, _ in part_lines(plan, p):
                        rid = fresh_by_week_day.get((w, day))
                        if not rid and _buy(ING[k]) not in ("stock", "none"):
                            warnings.append(f"no fresh run covers week {w} {day} ({ING[k]['name']})")
                        add(k, g, rid)
    for s in sessions(plan):
        rid = batch_run_for[(s["week"], s["day"], s["prior"])]
        for rk, n in s["cook"].items():
            for it in plan["recipes"][rk]["items"]:
                k, amt, _, _ = _item(it)
                add(k, amt * n, rid)
    demand["stock"] = stock_need

    lots = defaultdict(list)
    per_cycle = []
    for c in range(cycles):
        cyc = {}
        for r in runs:
            date = r["date"] + dt.timedelta(days=7 * W * c) if r["date"] else None
            for k, need in demand.get(r["id"], {}).items():
                if need <= 0:
                    continue
                sh = ING[k].get("shop") or {}
                if date:
                    lots[k] = [l for l in lots[k] if l[1] is None or l[1] >= date]
                have = sum(l[0] for l in lots[k])
                pack_amt = _pack_amount(ING[k])
                short = max(0.0, need - have)
                packs = math.ceil(short / pack_amt - 1e-9) if pack_amt else None
                bought = packs * pack_amt if pack_amt else short
                remaining = need
                for l in lots[k]:
                    take = min(l[0], remaining)
                    l[0] -= take
                    remaining -= take
                lots[k] = [l for l in lots[k] if l[0] > 1e-6]
                leftover = bought - remaining
                if leftover > 1e-6 and sh.get("carry", True):
                    exp = date + dt.timedelta(days=int(sh["shelf_days"])) if (date and sh.get("shelf_days")) else None
                    lots[k].append([leftover, exp])
                cyc[(r["id"], k)] = (packs, have)
        per_cycle.append(cyc)

    out_runs = []
    till = 0.0
    prorated = 0.0
    for r in runs:
        items = []
        for k, need in sorted(demand.get(r["id"], {}).items(), key=lambda kv: ING[kv[0]]["name"]):
            if need <= 0:
                continue
            ingr = ING[k]
            sh = ingr.get("shop") or {}
            pack_amt = _pack_amount(ingr)
            packs, have = per_cycle[0][(r["id"], k)]
            seq = [pc[(r["id"], k)][0] for pc in per_cycle]
            price = sh.get("price")
            it = {"key": k, "name": ingr["name"], "need": round(need, 1), "unit": ingr.get("unit", "g"),
                  "packs": packs, "packs_by_cycle": seq,
                  "pack_label": sh.get("pack_label") or (f"{fmt_num(sh.get('pack_size'))} {sh.get('pack_unit', 'g')}" if sh.get("pack_size") else ""),
                  "price_each": price, "cost": round(packs * price, 2) if (packs is not None and price is not None) else None,
                  "store": sh.get("store") or r.get("store", ""), "link": sh.get("link"),
                  "category": ingr.get("category", "Other"), "note": sh.get("note")}
            if r["kind"] == "stock" and pack_amt:
                it["lasts_cycles"] = round(pack_amt / need, 1) if need else None
                if len(set(seq)) > 1:
                    it["alternating"] = f"{min(seq)}–{max(seq)} per cycle (next cycles: {', '.join(str(x) for x in seq)})"
            if price is not None and pack_amt:
                prorated += need / pack_amt * price
            items.append(it)
        cost = round(sum(i["cost"] or 0 for i in items), 2)
        till += cost
        out_runs.append({**{k: v for k, v in r.items() if k not in ("t", "session")},
                         "date": r["date"].isoformat() if r["date"] else None, "items": items, "cost": cost})
    missing_price = sorted({i["name"] for r in out_runs for i in r["items"] if i["price_each"] is None})
    return {"runs": out_runs, "first_cycle_till_cost": round(till, 2), "cycle_cost": round(prorated, 2),
            "weekly_cost": round(prorated / W, 2), "warnings": sorted(set(warnings)), "missing_price": missing_price}


def _pack_amount(ingr):
    sh = ingr.get("shop") or {}
    pack = float(sh.get("pack_size") or 0)
    if sh.get("pack_unit") == "pc":
        return pack * float(ingr.get("piece_g") or 0)
    return pack


# ----------------------------------------------------------------------------- full compute

def compute(plan):
    W = cycle_weeks(plan)
    res = {"meta": plan.get("meta", {}), "targets": plan.get("targets", {}), "recipes": {}, "days": {}, "weeks": {}}
    for rk, r in plan["recipes"].items():
        if r["kind"] == "batch":
            res["recipes"][rk] = {"1 portion": recipe_portion_acc(plan, rk).export(),
                                  "Whole batch": recipe_acc(plan, rk).export()}
        else:
            res["recipes"][rk] = {"1 serving": recipe_acc(plan, rk).export()}
    for day in WEEKDAYS:
        d = plan["days"][day]
        a, meals = day_acc(plan, d)
        res["days"][day] = {"type": d.get("type", "training"), "total": a.export(),
                            "meals": [{"name": m["name"], **ma.export()} for m, ma in meals]}
    # per-week day totals when overrides exist
    for w in range(1, W + 1):
        res["weeks"][w] = {day: day_acc(plan, day_def(plan, w, day))[0].export()["n"] for day in WEEKDAYS}
    res["inventory"] = inventory(plan)
    res["shopping"] = shopping(plan)
    res["checks"] = checks(plan, res)
    return res


def used_ingredients(plan):
    """Ingredient keys that are actually eaten or cooked in the cycle (template, overrides, sessions)."""
    used = set()
    W = cycle_weeks(plan)
    for w in range(1, W + 1):
        for day in WEEKDAYS:
            for m in day_def(plan, w, day).get("meals", []):
                for p in m.get("parts", []):
                    for k, _, _, _ in part_lines(plan, p):
                        used.add(k)
    for s in sessions(plan):
        for rk in s["cook"]:
            for it in plan["recipes"][rk]["items"]:
                used.add(_item(it)[0])
    return used


def scanned_ingredients(plan):
    """Everything the allergy check must cover: every ingredient eaten or cooked in the cycle plus every
    ingredient of every recipe in plan.recipes — render_pages publishes all of them (recipe pages and the
    shopping list's quick reference), including recipes no longer on the schedule."""
    keys = used_ingredients(plan)
    for r in plan.get("recipes", {}).values():
        for it in r.get("items", []):
            keys.add(_item(it)[0])
    return keys


def allergy_alerts(plan):
    """Allergy lines every generated output shows prominently (pages, shopping lists, workbook).
    [{"level": "warn"|"info", "text": …}] — warn while the status is unknown or the check has findings."""
    a = allergy_check(plan)
    if a["status"] == "unknown":
        return [{"level": "warn", "text": "Allergies and intolerances NOT CONFIRMED — check every ingredient "
                                          "with the athlete before cooking or buying anything on this page."}]
    out = [{"level": "warn", "text": f} for f in a["flags"]]
    if a["status"] == "known":
        out.append({"level": "info", "text": "Planned free of: " + ", ".join(a["items"]) +
                    ". Check the label of every pack you buy — recipes and factories change."})
    return out


def allergy_check(plan):
    """Allergy findings. Every flag here is blocking: resolve before the plan is approved or cooked."""
    al = plan.get("meta", {}).get("allergies") or {"status": "unknown"}
    out = {"status": al.get("status", "unknown"), "items": [a.lower() for a in al.get("items", [])],
           "conflicts": [], "traces": [], "unchecked": [], "flags": []}
    if out["status"] == "unknown":
        out["flags"].append("ALLERGY STATUS UNKNOWN — confirm allergies and intolerances with the athlete "
                            "before anything is cooked or bought")
        return out
    if out["status"] == "none":
        return out
    want = set(out["items"])
    traces_matter = al.get("traces_matter", True)
    for k in sorted(scanned_ingredients(plan)):
        ing = plan["ingredients"][k]
        if "allergens" not in ing:
            out["unchecked"].append(ing["name"])
            continue
        hit = want & {a.lower() for a in ing.get("allergens", [])}
        if hit:
            out["conflicts"].append({"ingredient": ing["name"], "allergens": sorted(hit)})
        trace = want & {a.lower() for a in ing.get("may_contain", [])}
        if trace and traces_matter:
            out["traces"].append({"ingredient": ing["name"], "allergens": sorted(trace)})
    for c in out["conflicts"]:
        out["flags"].append(f"ALLERGEN CONFLICT: {c['ingredient']} contains {', '.join(c['allergens'])}")
    for c in out["traces"]:
        out["flags"].append(f"ALLERGEN TRACES: {c['ingredient']} may contain {', '.join(c['allergens'])}")
    if out["unchecked"]:
        out["flags"].append("ALLERGENS NOT CHECKED for: " + ", ".join(out["unchecked"]) +
                            " — add `allergens` from the product label")
    return out


def checks(plan, res):
    T = plan.get("targets", {})
    alg = allergy_check(plan)
    out = {"days": [], "micros": [], "flags": list(alg["flags"]), "allergies": alg}
    for day in WEEKDAYS:
        n = res["days"][day]["total"]["n"]
        t = T.get(res["days"][day]["type"], {})
        row = {"day": day, "type": res["days"][day]["type"]}
        for k in ("kcal", "protein_g", "carb_g", "fat_g", "fiber_g", "salt_g"):
            row[k] = round(n[k], 1)
            if k in t:
                row[k + "_target"] = t[k]
                row[k + "_delta"] = round(n[k] - t[k], 1)
        out["days"].append(row)
        if "kcal" in t and abs(n["kcal"] - t["kcal"]) > 0.05 * t["kcal"]:
            out["flags"].append(f"{day}: kcal {n['kcal']:.0f} vs target {t['kcal']} (>5 % off)")
        if "protein_g" in t and n["protein_g"] < t["protein_g"] - 10:
            out["flags"].append(f"{day}: protein {n['protein_g']:.0f} g is >10 g under target {t['protein_g']} g")
        if T.get("fiber_min") and n["fiber_g"] < T["fiber_min"]:
            out["flags"].append(f"{day}: fibre {n['fiber_g']:.0f} g under {T['fiber_min']} g")
        if T.get("salt_max") and n["salt_g"] > T["salt_max"] * 1.5:
            out["flags"].append(f"{day}: salt {n['salt_g']:.1f} g (pre-workout/intra salt may justify it — check)")
        sc = res["days"][day]["total"]["score"]
        if sc and sc["scores"][sc["limiting"]] < 100:
            out["flags"].append(f"{day}: day-level amino-acid score {sc['scores'][sc['limiting']]} (limiting {sc['limiting']})")
    mt = T.get("micros", {})
    for k, lim in mt.items():
        vals = [res["days"][d]["total"]["n"].get(k, 0) for d in WEEKDAYS]
        miss = max(res["days"][d]["total"]["mshare"].get(k, 0) for d in WEEKDAYS)
        avg = sum(vals) / 7
        row = {"key": k, "avg": round(avg, 2), "min": round(min(vals), 2), "max": round(max(vals), 2),
               "floor": lim.get("floor"), "aim": lim.get("aim"), "ul": lim.get("ul"),
               "supplement": lim.get("supplement", 0), "missing_share": miss}
        tot_avg = avg + (lim.get("supplement") or 0)
        row["avg_incl_supp"] = round(tot_avg, 2)
        st = "ok"
        if lim.get("floor") and tot_avg < lim["floor"]:
            st = "below floor"
        elif lim.get("aim") and tot_avg < lim["aim"]:
            st = "below aim"
        if lim.get("ul") and (max(vals) + (lim.get("supplement") or 0)) > lim["ul"]:
            st = "ABOVE UL"
        if miss > 0.1 and st != "ok":
            st += " (data incomplete)"
        row["status"] = st
        out["micros"].append(row)
        if st != "ok":
            out["flags"].append(f"micro {k}: {st} — week avg {tot_avg:.1f} (floor {lim.get('floor')}, aim {lim.get('aim')}, UL {lim.get('ul')})")
    inv = res["inventory"]
    for s in inv["steady_shortfalls"]:
        out["flags"].append(f"batch shortfall: {s['recipe']} short {s['short']} portions in week {s['week']} {s['day']}")
    fz = plan.get("meta", {}).get("freezer_portions")
    if fz and inv["peak_total_portions"] > fz:
        out["flags"].append(f"freezer: peak {inv['peak_total_portions']} containers stored vs capacity {fz}")
    for w in res["shopping"]["warnings"]:
        out["flags"].append("shopping: " + w)
    return out


# ----------------------------------------------------------------------------- report

def report(plan, res):
    L = []
    m = plan.get("meta", {})
    L.append(f"# Plan check — {m.get('name', 'meal plan')}\n")
    alg = res["checks"]["allergies"]
    label = {"none": "none (confirmed by the athlete)", "unknown": "UNKNOWN — confirm before cooking or shopping",
             "known": "known: " + ", ".join(alg["items"])}[alg["status"]]
    L.append(f"**Allergies:** {label}")
    if alg["status"] == "known":
        L.append(f"Conflicts: {len(alg['conflicts'])} · trace warnings: {len(alg['traces'])} · "
                 f"ingredients without allergen data: {len(alg['unchecked'])}")
    L.append("")
    L.append("## Days vs targets\n")
    L.append("| Day | Type | kcal | Δ | Protein g | Δ | Carbs g | Fat g | Fibre g | Salt g |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in res["checks"]["days"]:
        L.append(f"| {r['day']} | {r['type']} | {r['kcal']:.0f} | {r.get('kcal_delta', 0):+.0f} | {r['protein_g']:.0f} | "
                 f"{r.get('protein_g_delta', 0):+.0f} | {r['carb_g']:.0f} | {r['fat_g']:.0f} | {r['fiber_g']:.0f} | {r['salt_g']:.1f} |")
    if res["checks"]["micros"]:
        L.append("\n## Micronutrients (week average, food + listed supplements)\n")
        L.append("| Nutrient | Avg/day | incl. supp | Floor | Aim | UL | Status |")
        L.append("|---|---|---|---|---|---|---|")
        for r in res["checks"]["micros"]:
            lab = MICRO_LABELS.get(r["key"], (r["key"], ""))
            L.append(f"| {lab[0]} ({lab[1]}) | {r['avg']:.1f} | {r['avg_incl_supp']:.1f} | {r['floor'] or '–'} | {r['aim'] or '–'} | {r['ul'] or '–'} | {r['status']} |")
    inv = res["inventory"]
    if inv["per_recipe"]:
        L.append("\n## Batch portions per cycle (steady state)\n")
        L.append("| Batch | Eaten | Cooked | Spare | Peak stored |")
        L.append("|---|---|---|---|---|")
        for rk, v in inv["per_recipe"].items():
            L.append(f"| {v['title']} | {fmt_num(round(v['eaten'], 2))} | {fmt_num(round(v['cooked'], 2))} | {fmt_num(round(v['spare'], 2))} | {fmt_num(v['peak_stored'])} |")
        L.append(f"\nPeak freezer containers at once: {fmt_num(inv['peak_total_portions'])}")
        if inv["startup_shortfalls"]:
            L.append(f"\nFirst cycle from an empty freezer runs short {len(inv['startup_shortfalls'])}× — plan an extra start-up cook (see shortfalls in computed.json).")
    sh = res["shopping"]
    L.append(f"\n## Cost\n\nSteady state ≈ {sh['cycle_cost']:.2f} per cycle · ≈ {sh['weekly_cost']:.2f} per week "
             f"(first cycle at the till ≈ {sh['first_cycle_till_cost']:.2f}, includes stocking slow movers)")
    if sh["missing_price"]:
        L.append(f"\nNo price yet: {', '.join(sh['missing_price'])}")
    L.append("\n## Flags\n")
    L += [f"- {f}" for f in res["checks"]["flags"]] or ["- none"]
    return "\n".join(L)


def _json_default(o):
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    raise TypeError(type(o))


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("check", "compute"):
        print(__doc__)
        sys.exit(2)
    try:
        plan = load(sys.argv[2])
    except PlanError as e:
        print("PLAN ERRORS:\n" + str(e))
        sys.exit(1)
    res = compute(plan)
    if sys.argv[1] == "check":
        print(report(plan, res))
    else:
        out = sys.argv[3] if len(sys.argv) > 3 else "computed.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=_json_default)
        print(f"wrote {out}")
