# Outputs: scratchpad, workbook, shopping list, cooking pages

## Scratchpad (phase 4, inline in chat — not an artifact)

Keep it to what the athlete must judge. Template:

```markdown
**Targets** — training 3,000 kcal · 215 P / 365 C / 76 F (2.5 g/kg protein) · rest 2,700 kcal · +200 free
Basis: BMR ≈ 1,940, maintenance ≈ 2,950, slight surplus. Adjust after 2–3 weeks from the weekly average.

**Training day (18:00 session)**
| Time | Meal | What | kcal | P | C | F |
|---|---|---|---|---|---|---|
| 07:30 | Breakfast | overnight oats, soy drink, isolate, berries, seeds | 690 | 44 | 80 | 19 |
| 15:30 | Pre-workout plate | rucola-beet salad · rice · dal (batch) | 720 | 40 | 120 | 7 |
| 17:00 | Pre-workout drink | citrulline 15 g · beta-alanine 4 g · taurine 2 g · salt 2 g · glycerol 40 g in 1.3 L | 170 | 0 | 40 | 0 |
| … | | | | | | |
| | **Total** | | **3,190** | **209** | **350** | **86** |

**Rest day** — same table, only rows that differ.

**Rotation** (pre-workout → main) | Mon dal → curry | Tue chili → bolo | …

**Batch rhythm** — Sunday A (wk 1, 3): 4 batches · Sunday B (wk 2, 4): chili + curry
| Batch | Eaten / cycle | Cooked | Spare |

**Micros to watch** (week average incl. supplements vs aim) — only rows not "ok" + diet-critical ones
**Supplements** — dose · timing · why
**Cost** ≈ €72/week (steady state)
**Open questions** — 1–3 bullets
```

Then `AskUserQuestion`: "Approve and build" (recommended when there are no flags) / "Change
something" / "Show a full day in detail".

## Workbook (`build_workbook.py`)

Sheets, in order — this matches the athlete's established workbook and must stay this way:

| Sheet | Content |
|---|---|
| Week summary | rows Mon–Sun: type, kcal, protein, fat, sat, unsat, carbs, fibre, salt (green links to day sheets), targets (blue), Δ; week average; micronutrient table per day (links to Micros) with food average, supplements/day, average incl. supplements, floor, aim, UL, % of aim; EAA table per day (links to EAA) with FAO-pattern scoring and the limiting amino acid |
| Micros | per day block: one row per meal × 23 micronutrients (SUMPRODUCT/SUMIF formulas into Ingredients), day total |
| EAA | per day block: per meal protein (link) + 11 essential amino acids, total, "Leucine ≥ 2.5 g?" |
| Ingredients | per 100 g/ml: macros, Source, 23 micros (outline-grouped), 11 amino acids (grouped), digestibility |
| Mon … Sun | "Meal / ingredient · Sub-group · Amount (g/ml) · Ingredient (lookup) · kcal · Protein · Fat · sat · unsat · Carbs · Fiber · Salt"; meal header rows, subtotals, day total, target, Δ, energy split, protein per kg |

Lookups: every formula matches ingredients by the **ID** column on the Ingredients sheet (e.g.
`ING_SOY_CHUNKS`, derived from the plan key, letters/digits/underscore only) — never by the display
name, because spreadsheet matching ignores case and treats `*`, `?`, `~` as wildcards. Day sheets
show the name in column A and the ID in "Ingredient ID (lookup)"; to swap an ingredient, paste
another ID there.

Conventions: Arial; blue = inputs, green = cross-sheet links, black = formulas; header fill
`#E8ECE6`; batch portions are expanded into scaled ingredient rows with the batch named in
"Sub-group" so every gram is visible and editable.

After building: run the xlsx skill's `recalc.py` (0 errors required) and spot-check three cells
against `mealplan.py compute` output. If the athlete already has a workbook in this format and only
wants it updated, edit theirs in place following the xlsx skill (keep their manual edits) instead of
regenerating.

## Shopping list (`render_pages.py` → `shopping-list.html` + `shopping-list.md`)

HTML artifact: header with weekly / cycle / first-cycle cost; cycle selector (dates shift by the
cycle length, ticks are stored per cycle); filters (upcoming, all, stock-up, batch, fresh); one card
per dated run, the next run opened and marked; items grouped by category with packs, pack label,
cost, shop, amount used, alternating-buy and "lasts ~N cycles" notes and links; recipe quick
reference; notes. Ticks persist in the viewer's browser; for cross-device sync add the shared-state
capability (load `artifact-capabilities` first).

Markdown (`shopping-list.md`): checkbox list per run with the same data plus the portions-per-cycle
table, cost table and recipe quick reference. If a Project is attached, write it there with
`Projects project_write` (path `claude/shopping-list-<N>-weeks.md`, replacing an older version
after reading it) and keep a one-line dated changelog in `meta.changelog`.

## Cooking pages (`render_pages.py` → `<recipe>.html`, `cook-<session>.html`)

Built from `assets/recipe_page.html` — the athlete's established page: kind/title/meta, variant
tabs (1 portion / whole batch), macro readout with energy split, tickable ingredients, prep, steps
with timers and a keep-screen-on button, amino-acid panel (protein vs 0.3–0.4 g/kg, leucine vs
2.5 g, estimated DIAAS, per-AA bars vs FAO pattern), notes, micro footer as % of the athlete's aim.

Page data (`const D`) is produced by the script; to customise a page, change `plan.json`
(`desc`, `notes`, `prep`, `steps`, `when`, `tag`, `accent`) and re-render — don't hand-edit HTML.

Publishing: one Artifact per page; titles = recipe titles; icon `recipe` (pages) and `cart`
(shopping list); a short description per page ("Batch recipe · 5 portions · lean"). Republish to the
same URLs on later changes (keep the artifact URL ↔ recipe key mapping in the Project or in
`meta.artifacts`).
