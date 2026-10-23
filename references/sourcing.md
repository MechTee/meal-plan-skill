# Sourcing: products, label values, packs and prices

Goal of phase 5: every ingredient row describes a product the athlete can put in a basket, with
its label values, pack size, price and shop. Generic values are only placeholders.

## Order of preference for nutrient values

1. The athlete's own data: receipts, photos of labels, pasted label text. Ask for them in the
   sourcing interview ("Deep") — they beat everything else.
2. Product label from the shop's site or Open Food Facts (world.openfoodfacts.org — barcode or name
   search; check the data matches the current recipe).
3. National composition database for the matching food: Germany BLS (Bundeslebensmittelschlüssel),
   UK CoFID/McCance & Widdowson, France CIQUAL, Netherlands NEVO, Nordic Fineli, US USDA FoodData
   Central (Foundation, then SR Legacy). Use these for micros and amino acids labels lack, scaled to
   the label's protein when the product's protein differs.
4. fddb.info / similar crowd databases only as a last resort for macros, marked as such.

Write the origin into `source` per ingredient (product name, database and id). When a label omits
fibre or a micro, leave it unknown — don't invent it.

## Pack sizes and recipe sizing

- Check the actual pack sizes at the athlete's shop before fixing batch quantities, then size batches
  to whole packs (2 × 400 g tins, a 1 kg net, a 125 g bag of leaves).
- Drained weight for tinned pulses (~240–265 g per 400 g tin) — define the ingredient per drained
  gram and the pack in drained grams.
- Bulk online buys (soy chunks, oats, powders, legumes) usually halve the price per kg; check
  shipping thresholds and bundle orders.

## Prices

- Prefer the shop's own online prices. Some shop sites block automated fetching; then use price
  trackers and search snippets, and label prices as "last seen, not live". Never invent a price or a
  product URL — leave `price` empty (the page lists it as missing) rather than guess.
- Many products × shops: run price research in parallel subagents, each with a short list of products,
  the shop, and the instruction to return exact product name, pack size, price, URL and date seen,
  or "not found".

## Germany (worked notes from earlier plans)

- Shops: REWE, EDEKA (full-range), Lidl, Aldi Süd/Nord, Penny, Netto, Kaufland (discount/large),
  dm/Rossmann (drugstore: protein powders, yeast flakes, some supplements), online bulk
  (KoRo, planeo, Schusterscheune, Jamoona, kokku) for soy chunks/legumes/nuts.
- shop.rewe.de tends to block WebFetch; supermarktcheck.de pages are fetchable and give last-seen
  prices; WebSearch snippets of shop pages often carry the price.
- Organic (Bio) plant drinks in Germany cannot be fortified with vitamins and calcium carbonate —
  fortified options are conventional (e.g. Alpro, some discounter high-protein soy drinks). None are
  usually iodised → plan iodine.
- Iodised salt (Jodsalz) carries ~15–25 mg iodine/kg; German composition data use ~20 mg/kg.
- German-language search terms find more: "Sojaschnetzel 1 kg", "Rote Linsen 500 g Preis",
  "Kidneybohnen Abtropfgewicht".
- Batch-tested supplements: Kölner Liste (koelnerliste.com).

## Other countries

Ask for the main supermarket(s) and look up their own-brand equivalents; the plan structure does not
change. Use local pack norms (US: 15 oz cans ≈ 425 g, 1 lb bags) but keep the plan metric unless the
athlete asks otherwise.
