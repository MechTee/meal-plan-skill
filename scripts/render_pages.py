#!/usr/bin/env python3
"""Render the HTML artifacts from plan.json: one cooking page per recipe, one page per cook-day
session, and the dated shopping list.

  python render_pages.py plan.json out_dir [--only dal,chili] [--no-shopping] [--no-cookdays]

Each page is a self-contained HTML file: open it in a browser, or publish it with whatever page
hosting the host offers (one page per file, so each can be opened on a phone in the kitchen or at
the shop).
"""
import sys, os, json, argparse, html as _html
sys.path.insert(0, os.path.dirname(__file__))
import mealplan as M

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
ACCENTS = [("#A86F00", "#EDBB45"), ("#2F6FB0", "#7FB2EC"), ("#B23A6A", "#F08AB4"), ("#2E7D45", "#6BC383"),
           ("#7A4FB5", "#B99AF0"), ("#B5531F", "#F39A6A"), ("#1F7A7A", "#6CC9C9")]
PAGE_MICROS = ["fiber_g", "sodium_mg", "potassium_mg", "calcium_mg", "magnesium_mg", "phosphorus_mg", "iron_mg",
               "zinc_mg", "selenium_ug", "iodine_ug", "vitA_rae_ug", "vitC_mg", "vitD_ug", "vitE_mg", "vitK_ug",
               "thiamin_mg", "riboflavin_mg", "niacin_mg", "b6_mg", "folate_ug", "b12_ug"]


def amount_str(plan, key, amt, display):
    if display:
        return display
    unit = plan["ingredients"][key].get("unit", "g")
    if unit == "ml" and amt >= 1000:
        return f"{amt / 1000:g} L"
    if amt >= 1000 and unit == "g":
        return f"{amt / 1000:g} kg"
    return f"{M.fmt_num(round(amt, 1))} {unit}"


def refs(plan):
    T = plan.get("targets", {})
    out = {k: v.get("aim") or v.get("floor") for k, v in T.get("micros", {}).items() if (v.get("aim") or v.get("floor"))}
    if T.get("fiber_min"):
        out["fiber_g"] = T["fiber_min"]
    return out


def fill(template, title, data, accent):
    html = open(os.path.join(ASSETS, template), encoding="utf-8").read()
    # JSON inside <script>: escape <, > and & so no plan string can close the script element or open a comment
    js = (json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
          .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return (html.replace("__TITLE__", _html.escape(title, quote=True)).replace("__DATA__", js)
            .replace("__ACCENT_L__", accent[0]).replace("__ACCENT_D__", accent[1]))


def recipe_data(plan, comp, rk):
    r = plan["recipes"][rk]
    meta = plan.get("meta", {})
    items = []
    for it in r["items"]:
        k, amt, note, disp = M._item(it)
        if k == "water" and not disp and amt == 0:
            continue
        items.append([plan["ingredients"][k]["name"], amount_str(plan, k, amt, disp), note])
    kind = r.get("label") or ("Batch recipe" + (f" · {r['tag']}" if r.get("tag") else "") if r["kind"] == "batch" else "Recipe")
    serves = f"{M.fmt_num(r['portions'])} portions" if r["kind"] == "batch" else (r.get("serves") or "1 serving")
    return {"id": rk, "title": r["title"], "kind": kind, "when": r.get("when", ""), "serves": serves,
            "desc": r.get("desc", ""), "ing": {"*": items}, "prep": r.get("prep", []),
            "steps": [list(s) if isinstance(s, (list, tuple)) else [s, None] for s in r.get("steps", [])],
            "notes": r.get("notes", []), "variants": comp["recipes"][rk], "bw": meta.get("bw_kg", 80),
            "unit": "variant", "refs": refs(plan), "refLabel": meta.get("ref_label"),
            "sources": meta.get("sources"), "noProtein": r.get("no_protein_note"), "smallNote": r.get("small_protein_note"),
            "alerts": M.allergy_alerts(plan)}


def cookday_pages(plan):
    seen = {}
    for s in plan.get("cycle", {}).get("sessions", []):
        lab = s.get("label", "Cook day")
        if lab in seen:
            continue
        acc = M.Acc()
        agg = {}
        for rk, n in s["cook"].items():
            acc.add(M.recipe_acc(plan, rk), n)
            for it in plan["recipes"][rk]["items"]:
                k, amt, _, _ = M._item(it)
                agg[k] = agg.get(k, 0) + amt * n
        items = [[plan["ingredients"][k]["name"], amount_str(plan, k, v, None), None]
                 for k, v in sorted(agg.items(), key=lambda kv: plan["ingredients"][kv[0]]["name"]) if k != "water"]
        titles = [f"{plan['recipes'][rk]['title']}" + (f" ×{n}" if n != 1 else "") for rk, n in s["cook"].items()]
        steps = s.get("steps") or [[f"Cook the {t} — follow its own page.", None] for t in titles]
        ports = sum(float(plan["recipes"][rk]["portions"]) * n for rk, n in s["cook"].items() if plan["recipes"][rk].get("storage_units") is None)
        wk = s.get("weeks")
        seen[lab] = {"id": "cook-" + lab.lower().replace(" ", "-"), "title": f"{lab} — cook day", "kind": "Cook-day plan",
                     "when": f"{s.get('day', 'Sun')}" + (f" · weeks {', '.join(map(str, wk))}" if wk else " · every week"),
                     "serves": f"{M.fmt_num(ports)} portions + extras",
                     "desc": "Everything cooked in this session: " + ", ".join(titles) + ".",
                     "ing": {"*": items}, "prep": s.get("prep", []), "steps": steps, "notes": s.get("notes", []),
                     "variants": {"Whole session": acc.export()}, "bw": plan.get("meta", {}).get("bw_kg", 80),
                     "unit": "session", "refs": refs(plan), "refLabel": plan.get("meta", {}).get("ref_label"),
                     "sources": plan.get("meta", {}).get("sources"),
                     "smallNote": "Totals for the whole session — divide by the portions to compare with a meal.",
                     "alerts": M.allergy_alerts(plan)}
    return list(seen.values())


def recipe_line(plan, rk):
    r = plan["recipes"][rk]
    parts = []
    for it in r["items"]:
        k, amt, _, disp = M._item(it)
        parts.append(f"{amount_str(plan, k, amt, disp)} {plan['ingredients'][k]['name'].lower()}")
    head = f"({M.fmt_num(r['portions'])} portions) " if r["kind"] == "batch" else ""
    return head + " · ".join(parts)


def shopping_data(plan, comp):
    sh = comp["shopping"]
    meta = plan.get("meta", {})
    return {"id": meta.get("id", "plan"), "title": meta.get("shopping_title", "Shopping list"),
            "eyebrow": f"{M.cycle_weeks(plan)}-week cycle · {meta.get('name', '')}",
            "desc": meta.get("shopping_desc", "Dated shop runs. Quantities are whole packs after using up what is left from earlier runs."),
            "currency": meta.get("currency", "EUR"), "locale": meta.get("locale", "en-GB"),
            "cycleWeeks": M.cycle_weeks(plan), "runs": sh["runs"],
            "costs": {"weekly": sh["weekly_cost"], "cycle": sh["cycle_cost"], "firstTill": sh["first_cycle_till_cost"]},
            "recipes": [{"title": plan["recipes"][rk]["title"], "line": recipe_line(plan, rk)} for rk in plan["recipes"]],
            "alerts": M.allergy_alerts(plan),
            "notes": meta.get("shopping_notes", []) + (["Prices missing for: " + ", ".join(sh["missing_price"])] if sh["missing_price"] else [])}


def shopping_markdown(plan, comp):
    """Markdown version of the shopping list for a Project doc (checkbox lists, one section per run)."""
    sh, meta, inv = comp["shopping"], plan.get("meta", {}), comp["inventory"]
    cur = meta.get("currency", "EUR")
    W = M.cycle_weeks(plan)
    out = [f"# {meta.get('shopping_title', 'Shopping list')} — {W}-week cycle", ""]
    if meta.get("name"):
        out += [f"Plan: {meta['name']}", ""]
    for a in M.allergy_alerts(plan):
        out += [("> **⚠ Allergy:** " if a["level"] == "warn" else "> **Allergy:** ") + a["text"], ""]
    if meta.get("changelog"):
        out += ["*" + " ".join(meta["changelog"]) + "*", ""]
    if inv["per_recipe"]:
        out += ["**Portions per cycle**", "", "| | Eaten | Cooked | Spare |", "|---|---|---|---|"]
        for v in inv["per_recipe"].values():
            out.append(f"| {v['title']} | {M.fmt_num(round(v['eaten'], 2))} | {M.fmt_num(round(v['cooked'], 2))} | {M.fmt_num(round(v['spare'], 2))} |")
        out.append("")
    for r in sh["runs"]:
        out += ["---", "", f"## {r['date']} · {r['label']}" + (f" · {r['store']}" if r.get("store") else ""), ""]
        cat = None
        for it in sorted(r["items"], key=lambda i: (i["category"], i["name"])):
            if it["category"] != cat:
                cat = it["category"]
                out += ["", f"### {cat}", ""]
            p = it["packs"]
            qty = "skip (enough left)" if p == 0 else (f"{p} × {it['pack_label']}" if p is not None else f"{round(it['need'])} {it['unit']}")
            bits = []
            if it.get("price_each") is not None and p:
                bits.append(f"~{it['price_each']:.2f} each")
            if str(it.get("link") or "").startswith(("https://", "http://")):
                bits.append(f"[link]({it['link']})")
            extra = []
            extra.append(f"uses {round(it['need'])} {it['unit']}")
            if it.get("alternating"):
                extra.append(it["alternating"])
            if it.get("lasts_cycles") and it["lasts_cycles"] >= 1.5:
                extra.append(f"lasts ~{it['lasts_cycles']} cycles")
            if it.get("note"):
                extra.append(it["note"])
            out.append(f"- [ ] **{it['name']}** — {qty}" + (" · " + " · ".join(bits) if bits else "") + f" *({'; '.join(extra)})*")
        out.append("")
    out += ["---", "", "## Cost", "", "| | Approx. " + cur + " |", "|---|---|"]
    out.append(f"| Recurring cost per cycle (budget) | {sh['cycle_cost']:.0f} |")
    out.append(f"| Per week | {sh['weekly_cost']:.0f} |")
    out.append(f"| of which food eaten / thrown away per cycle | {sh['consumed_value_per_cycle']:.0f} / {sh['waste_per_cycle']:.0f} |")
    out.append(f"| First cycle at the till | {sh['first_cycle_till_cost']:.0f} |")
    out += ["", "## Recipes (quick reference)", ""]
    for rk in plan["recipes"]:
        out.append(f"**{plan['recipes'][rk]['title']}** {recipe_line(plan, rk)}")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("out_dir")
    ap.add_argument("--only")
    ap.add_argument("--no-shopping", action="store_true")
    ap.add_argument("--no-cookdays", action="store_true")
    a = ap.parse_args()
    plan = M.load(a.plan)
    comp = json.loads(json.dumps(M.compute(plan), default=M._json_default))
    os.makedirs(a.out_dir, exist_ok=True)
    only = set(a.only.split(",")) if a.only else None
    written = []
    for i, rk in enumerate(plan["recipes"]):
        if only and rk not in only:
            continue
        r = plan["recipes"][rk]
        acc = tuple(r["accent"]) if r.get("accent") else ACCENTS[i % len(ACCENTS)]
        path = os.path.join(a.out_dir, f"{rk}.html")
        open(path, "w", encoding="utf-8").write(fill("recipe_page.html", r["title"], recipe_data(plan, comp, rk), acc))
        written.append(path)
    if not a.no_cookdays and not only:
        for j, d in enumerate(cookday_pages(plan)):
            path = os.path.join(a.out_dir, f"{d['id']}.html")
            open(path, "w", encoding="utf-8").write(fill("recipe_page.html", d["title"], d, ACCENTS[(j + 3) % len(ACCENTS)]))
            written.append(path)
    if not a.no_shopping and not only:
        sd = shopping_data(plan, comp)
        path = os.path.join(a.out_dir, "shopping-list.html")
        open(path, "w", encoding="utf-8").write(fill("shopping_list.html", sd["title"], sd, ACCENTS[3]))
        written.append(path)
        path = os.path.join(a.out_dir, "shopping-list.md")
        open(path, "w", encoding="utf-8").write(shopping_markdown(plan, comp))
        written.append(path)
    print("\n".join(written))


if __name__ == "__main__":
    main()
