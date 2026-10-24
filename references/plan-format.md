# plan.json format

One file drives every output. `assets/example_plan.json` is a complete, valid example (a 4-week
vegetarian lean-gain plan with four batch mains, a weekly rice batch, A/B cook days and a week
override) — copy its structure. `python3 scripts/mealplan.py check plan.json` validates the file
and lists every unknown key reference.

## Top level

```json
{
  "meta": {...},
  "targets": {...},
  "ingredients": {"<key>": {...}},
  "recipes": {"<key>": {...}},
  "days": {"Mon": {...}, "Tue": {...}, "...": {}, "Sun": {...}},
  "week_overrides": {"2": {"Sat": {...}}},
  "cycle": {...},
  "shopping": {...}
}
```

## meta

| key | meaning |
|---|---|
| name | plan name shown on pages |
| athlete, bw_kg | body weight drives protein/kg and per-feeding targets on pages |
| currency, locale, country | `"EUR"`, `"de-DE"` — formatting on the shopping page |
| freezer_portions | freezer capacity in containers; the check flags the peak above it |
| workbook_notes | list of short notes shown under the Week summary title (e.g. week-2/4 swaps) |
| ref_label | footer text for the micro bars, e.g. "Bars show % of your daily aim (D-A-CH + athlete adjustments)." |
| sources | `[["USDA FoodData Central","https://fdc.nal.usda.gov/"], …]` for the page footers |
| shopping_title, shopping_desc, shopping_notes | shopping page text |

## targets

```json
{
  "training": {"kcal": 3000, "protein_g": 215, "carb_g": 365, "fat_g": 76},
  "rest":     {"kcal": 2700, "protein_g": 215, "carb_g": 290, "fat_g": 76},
  "free_kcal": 200, "fiber_min": 30, "salt_max": 6,
  "micros": {"iodine_ug": {"floor": 200, "aim": 200, "ul": 600, "supplement": 133,
                           "supplement_note": "400 µg tablet every 3rd day"}}
}
```
`micros` keys are the nutrient keys below; take them from `targets.py` output. `supplement` is a
daily average and is added to food in checks and in the workbook ("Supplements / day" row).

Upper limits: `ul` applies to the **total** intake. `limits: [{"basis": "<form key>", "ul": n}]`
applies to one form only (magnesium → `magnesium_added_mg` 250; folate → `folic_acid_ug` 1000;
vitamin A → `retinol_ug` 3000; niacin → `nicotinamide_mg` 900 and `nicotinic_acid_mg` 10). Say what form a
supplement is in with `supplement_forms`, e.g. `{"supplement": 400, "supplement_forms": {"folic_acid_ug": 400}}`.
A magnesium supplement always counts as added magnesium; for the others an unknown supplement form
leaves the limit **unresolved** (reported, never "ok").

## ingredients

(`//` comments below are explanations only — JSON files cannot contain them.)

```json
"chunks": {
  "name": "Soy chunks, dry",            // unique — it is the lookup key in the workbook
  "unit": "g",                           // "g" or "ml"; values are per 100 of this unit
  "category": "Powders (online)",        // shopping-list group
  "source": "Vantastic Foods label (macros); USDA FDC 174276 soy flour defatted (micros)",
  "per100": {"kcal": 332, "protein_g": 49, "fat_g": 1.2, "satfat_g": 0.3, "carb_g": 27,
             "sugar_g": 7, "fiber_g": 8.8, "salt_g": 0.01, "iron_mg": 9, "magnesium_mg": 290},
  "aa": {"his": 1.27, "ile": 2.2, "leu": 3.82, "lys": 3.04, "met": 0.64, "cys": 0.64,
         "phe": 2.45, "tyr": 1.76, "thr": 1.86, "trp": 0.64, "val": 2.3},   // g per 100 g
  "digestibility": 0.9,
  "origin": "plant",                     // plant | fungal | animal | other (water, salt, pure compounds) — only animal foods contain preformed retinol
  "fortified_with": [],                  // parent nutrients added by the maker, e.g. ["calcium_mg", "vitD_ug", "folate_ug"]
  "piece_g": null,                       // grams per piece when bought by the piece
  "shop": {"buy": "stock", "pack_size": 1000, "pack_unit": "g", "pack_label": "Vantastic Soja Schnetzel 1 kg",
           "price": 8.99, "store": "online", "link": "https://…", "shelf_days": null, "carry": true,
           "note": "the fine variant suits the dal"}
}
```

Nutrient keys (`per100`): `kcal protein_g fat_g satfat_g carb_g sugar_g fiber_g salt_g` and
`thiamin_mg riboflavin_mg niacin_mg pantothenic_mg b6_mg biotin_ug folate_ug b12_ug potassium_mg
phosphorus_mg magnesium_mg calcium_mg zinc_mg iron_mg selenium_ug iodine_ug vitA_rae_ug vitC_mg
vitD_ug vitE_mg vitK_ug sodium_mg nitrate_mg`.
Nutrient **forms** with their own upper limits (optional per100 keys): `retinol_ug` (preformed
vitamin A, part of `vitA_rae_ug`), `folic_acid_ug` (synthetic, part of `folate_ug`),
`magnesium_added_mg` (added/supplemental magnesium), `nicotinamide_mg`, `nicotinic_acid_mg` (part of
`niacin_mg`). When a form is not given it is 0 where that is certain — the parent nutrient is 0;
retinol in a `plant`, `fungal` or `other` ingredient; folic acid, added magnesium and the niacin forms in a food not
`fortified_with` that nutrient — and unknown otherwise.

Leave a key **out** (or `null`) when unknown — it is tracked as missing data and shown as "≥" on the
pages; write `0` only when the true value is zero. `sodium_mg` defaults to `salt_g × 400`.
Carbs are net carbs (EU-label style); fibre separate. For US-label data subtract fibre from total
carbohydrate.

`shop.buy`:
- `stock` — bought once per cycle on the stock-up run (dry goods, tins, frozen, powders, spices)
- `fresh` — bought on the fresh run that covers the day it is eaten (leaves, fruit, drinks)
- `batch` — bought on the cook day for the batch session (onions, peppers, roots); day use of a
  batch-class item goes on the fresh run
- omit `shop` for things never bought (tap water)

`pack_unit: "pc"` + `piece_g` for items sold per piece (kiwi 75 g, avocado ~150 g flesh, lemon
juice per lemon). `shelf_days` makes leftovers expire; `carry: false` forbids carry-over.

## recipes

```json
"dal": {"title": "Red Lentil Dal", "kind": "batch", "portions": 5, "storage_units": null,
        "tag": "lean", "when": "Batch · Sunday A", "desc": "…",
        "items": [["lentils", 300], ["tomatoes", 800, null, "2 × 400 g"], ["chunks", 100, "fine variant blends in"]],
        "prep": ["…"], "steps": [["Simmer half-covered, stir every few minutes.", 20], ["Portion by weight.", null]],
        "notes": ["…"], "accent": ["#A86F00", "#EDBB45"]}
```
- `kind`: `batch` (cooked in sessions, eaten as portions from the freezer/fridge) or `single`
  (made fresh each time; `items` are one serving).
- Items: `[ingredient_key, amount, note?, display?]` — amount in the ingredient's unit; `display`
  overrides the shown amount ("2 tins").
- `portions` may be "parts": a rice batch of 400 g dry split into 23 parts lets days take 4 or 3
  parts. Set `storage_units` (containers per batch, e.g. 6 bags) so the freezer count is right.
- `steps`: `[text, minutes|null]` — minutes become a timer button on the page.

## days and week_overrides

```json
"Mon": {"label": "Monday", "type": "training", "meals": [
  {"name": "Pre-workout plate", "time": "15:30", "parts": [
     {"recipe": "salad"}, {"recipe": "dal", "portions": 1}, {"recipe": "rice", "portions": 4},
     {"ingredient": "avocado", "amount": 70, "label": "fat topper"}]}]}
```
- All seven days are required (`Mon` … `Sun`). `type` is `training` or `rest` (picks targets).
- `label` may carry a suffix, e.g. `"Wednesday (legs)"` → sheet title "Wednesday — Training (legs)".
- `week_overrides` replaces whole days in specific weeks of the cycle (`"2": {"Sat": {…}}`). The
  workbook shows the template week; overrides feed batch balance and shopping, and should be
  mentioned in `meta.workbook_notes`.

## cycle

```json
"cycle": {"weeks": 4, "start_date": "2026-11-02",
  "sessions": [
    {"label": "Sunday A", "weeks": [1, 3], "day": "Sun", "prior": true,
     "cook": {"dal": 1, "chili": 1, "curry": 1, "bolo": 1, "rice": 1},
     "steps": [["Start rice and soak chunks first.", null], ["…", 20]]},
    {"label": "Sunday B", "weeks": [2, 4], "day": "Sun", "prior": true, "cook": {"chili": 1, "curry": 1, "rice": 1}}]}
```
- `start_date` is the Monday of week 1. `prior: true` puts the event in the previous calendar week
  (the Sunday *before* the week it feeds). Sessions happen before that day's meals.
- `cook` maps batch recipe → number of batches. `steps`/`prep`/`notes` feed the cook-day page;
  without `steps` the page lists the recipes in order.

## shopping

```json
"shopping": {
  "stock_run": {"day": "Sat", "prior": true, "label": "Stock-up", "store": "REWE + online"},
  "fresh_runs": [{"day": "Sat", "prior": true, "label": "Weekly fresh run", "store": "REWE + Lidl",
                  "covers": ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]}],
  "batch_label": "Batch shop", "batch_store": "REWE"}
```
- One stock-up run per cycle (week 1), one batch shop per cook session (same day), and the fresh
  runs every week. Split fresh runs for perishables, e.g. Sat covers Sun–Wed and Wed covers Thu–Sat.
- The engine buys whole packs, reuses leftovers first (FIFO, expired lots dropped), and reports per
  item `packs` for the coming cycle, `packs_by_cycle` (alternating buys) and `lasts_cycles` for slow
  movers. Cost: `first_cycle_till_cost` (what the first cycle costs at the till) and `cycle_cost` /
  `weekly_cost` (pro-rated steady state — use this for the budget).
