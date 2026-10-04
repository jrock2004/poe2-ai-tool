---
name: poe2-price-check
description: Price a Path of Exile 2 item or currency and say what it's realistically worth, with a confidence level. Use when the player pastes an item, asks "what's this worth", asks about currency exchange rates, or wants trade filters / a search link for an upgrade.
---
# poe2-price-check  (Phase 1)

Load `poe2-core` first — it owns the confidence rubric, the beginner how-to reference, and the
"never auto-trade" rule. This skill turns a currency name, a unique, or a pasted rare item into a
realistic price and (for rares) a ready-to-use trade search, always with a grounded confidence band.

## Decide what you're pricing

1. **A currency** ("what's chaos going for?", "divine rate?") → poe2scout, `get_currency_prices`.
2. **A unique item** (named item, orange text) → poe2scout, `price_unique`.
3. **A rare item** (yellow item with random mods; the interesting case) → the `/trade2` adapter:
   `find_stat_filters` → `build_trade_filter` → `search_trade`. poe2scout **cannot** price rares.

If the player pasted raw item text (Ctrl+C in game), read the rarity line to tell unique from rare.
If they don't know how to copy an item, give the one-liner from `poe2-core/references/how-to.md`
("hover the item, press Ctrl+C, paste here").

## Currencies and uniques (poe2scout)

- Currency: `get_currency_prices(category, search)` — category is the apiId (`currency`, `essence`,
  `runes`, `catalysts`, …), `search` narrows by name. Prices come back in both exalted and divine.
- Unique: `price_unique(name)` — exact match returns the reference price; otherwise it returns
  close-name suggestions. If there's no match, say so and offer the nearest names; don't invent a price.
- League defaults to the saved one (the active character's); pass `league` only to override.

## Rare items (the /trade2 flow)

A rare's value is its *mods*, so price it by finding what similar items actually sell for:

1. **Pick the mods that matter.** From the pasted item (or the player's description), choose the few
   affixes that drive value — not every line. E.g. for boots: movement speed, life, a key resistance.
2. **Resolve each to a filter id:** `find_stat_filters("+80 to maximum Life")` → candidate ids. Use
   the top (explicit) match unless a pseudo/aggregate makes more sense; numbers are wildcards, so the
   value never blocks the match.
3. **Build the filter:** `build_trade_filter(category="armour.boots", stats=[{id, min}], max_price=…)`.
   Set `min`s a little *below* the item's rolls to catch comparables, not just exact clones. Set
   `max_price` from the player's currency budget when known (see `poe2-currency-tracker`).
4. **Search:** `search_trade(query, limit=10)`. It returns a clickable trade link, how many listings
   matched, the cheapest few (mods, price, seller, and a whisper string the player copies), and
   `priceStats` — those listings converted to exalted (min / median / max, spread).
5. **Price from `priceStats`, not by eyeballing listings.** Lead with `medianExalted` and give the
   range `minExalted`–`medianExalted` (convert to divine for big numbers). If the median is more than
   2× the min, the floor is probably a price-fixer — say so and price from the median. Always give
   the player the `url` and note they trade themselves.

### "No listings → widen the search" (required behavior)

If `matched` is 0 or very small, do **not** report a shaky price. Loosen one thing at a time, say
what you changed, and re-search:

- Drop the least important mod, or lower a `min` (an 80-life filter with 0 hits → try 70, then 60).
- Allow offline sellers (`build_trade_filter(..., online_only=False)`).
- Raise or remove `max_price`.
- Broaden the category if it was too specific.

Narrate it plainly: *"Nothing matched at 80 life + 30% MS; I dropped movement speed to 25% and found
6 listings."* Widening lowers confidence — reflect that in the band.

## Trade filters as the deliverable (F6) and the iterate loop

The player acts, never the tool. Output is a **link + the exact filters** (and per-listing whisper
text to copy) — never an auto-purchase or whisper. After a search, invite the loop: the player pastes
back what they saw or bought, and you critique and refine ("those are overpriced because the crit
filter is too tight — drop it and the floor halves"). Keep the last search in this conversation so
"search again, cheaper" continues without re-stating everything.

## SSF characters

When the character being worked on is SSF (`trade_mode`, see `poe2-core`), still price the item — what
trade players pay is a fair signal of how rare or wanted a drop is, and whether it's worth crafting on.
Label it as a reference: *"trade players pay ~X for this — you can't sell it in SSF, but it tells you
it's a strong drop."* Leave out the trade link, whisper strings, budget `max_price`, and the iterate
loop, unless the player asks for the search to see comparables.

A price is the same in either mode, so don't stop to ask `trade_mode` just to price something — if it's
unknown, answer the trade way.

## Confidence (per `poe2-core/references/confidence.md`)

Score the market signals from the tool fields, using the thresholds in the rubric's **Market
signals** table — the band is capped by the weakest one:
- **Rares** — `priceStats.converted` (sample size), `priceStats.spreadRatio` (spread),
  `priceStats.unconvertedCurrencies` (coverage), `ageSeconds` (freshness). `matched` is only depth.
- **Currency** — `quantityListed` (depth), `trend.changePctVsDivine` (volatility), and `ageSeconds`.
- **Uniques** — `price_unique` has no listing volume, so it tops out at **Medium**.
- **Input certainty** — real pasted item = higher; a vague description = lower, and say what would
  sharpen it (the actual item text, the target league, the budget).
- **Widening** — each loosening step moves you further from the player's actual item; say what was
  loosened, and drop a band if the comparables no longer really match it.
- **Reusing an earlier price** — check its `fetchedAt`; re-query if it's stale rather than restating it.

End every answer with e.g. `Confidence: Medium — 5 listings, prices ranged ~2×; loosened MS to 25%.`

## Guardrails

- Never buy, list, or whisper. `search_trade` is read-only and rate-limited; if it returns a 429/blocked
  note, back off and tell the player to retry shortly — don't hammer it.
- Don't fabricate rare prices from poe2scout — it doesn't have them; use `/trade2` or say you can't.
