---
name: poe2-currency-tracker
description: Track the player's Path of Exile 2 currency by reading screenshots of their currency/crafting tabs into a remembered inventory, and answer affordability and net-worth questions. Use when the player shares a currency-tab screenshot or asks "what can I afford", "what's my net worth", or "how much currency do I have".
---
# poe2-currency-tracker

Load `poe2-core` first. There is **no PoE2 stash API**, so the inventory can't be read from the game —
the player sends **screenshots** of their currency/crafting tabs and this skill reads them (vision)
into a remembered, per-league inventory, then values it and answers "can I afford this?".

Vision can misread a stack count or a look-alike icon, so the rule is **confirm before saving** and
**never guess** — a wrong count silently corrupts every affordability answer downstream.

## State: currency inventory (per league)

Currency is **league-scoped**, shared across every character in that league (see the shared model in
`poe2-core`). Persist in memory keyed by league:

```
currency[league] = {
  tabs: {
    "<tab name>": {              # e.g. "currency", "crafting", "essences"
      items: [ { name, count, confidence } ],   # name = canonical (glossary-normalized)
      captured_at: <when the screenshot was read>,
      source: "screenshot"
    }, ...
  },
  adjustments: [ { name, delta, note, at } ],    # manual between-sync tweaks, e.g. spent 2 divine
  updated_at
}
```

**Totals** = per-name sum across all tabs, plus any `adjustments`. Keep tabs separate so re-sending one
tab replaces just that bucket instead of double-counting.

## Reading a screenshot

1. **Identify the tab.** Ask which tab it is if it's ambiguous ("is this your currency tab or a
   crafting tab?"). One screenshot → one named tab.
2. **Parse icon → canonical name + printed stack count.** Normalize names via
   `poe2-core/references/currency-glossary.md` (so "Divine Orb", not "div" or a guess). PoE2 stacks
   print the count on the icon; read it exactly.
3. **Score each line's confidence** from the image, per `poe2-core/references/confidence.md`: a crisp,
   full-resolution tab reads **High**; a compressed, cropped, or partially-hovered image reads **Low**
   and gets flagged. Don't average it away — flag the specific lines you're unsure of.
4. **Show what you read and ask to confirm** before saving:
   > Read from your **currency** tab: Exalted ×342, Divine ×11, Chaos ×80, Annul ×3 *(Annul count
   > blurry — Low)*. Save this? Correct anything that's off.
5. **On confirm, save** (replace that tab). On a correction, apply it and save the corrected value.

## Answering questions

- **Net worth / "how much do I have?"** → call `value_currency(holdings, league)` with the summed
  totals. It returns worth in exalted (base unit) and divine, per line and total. Report the total and
  the biggest contributors; state confidence from `ageSeconds` (per the rubric's **Market signals**
  table) and how confident the parsed counts were. If `unmatched` is non-empty, those lines weren't
  priced, so the total is **understated** — name them and say so rather than presenting a full total.
- **"Can I afford X?"** → compare X's price (from `poe2-price-check`; for a rare, its
  `priceStats.medianExalted`) against `totalExalted` — both are exalted. Answer in the same unit the
  item is quoted in. If the inventory is stale or was Low-confidence, say so and offer a re-screenshot.
- **Budget ceilings for trade filters** → hand the affordable amount to `build_trade_filter`'s
  `max_price` so searches only surface things the player can actually buy (F6).

## Manual adjustments & drift

The inventory goes stale the moment the player trades — that's expected, not a bug. Two ways to keep it
honest, cheapest first:
- **Re-screenshot** the tab after trading; that tab's counts are replaced. This is the source of truth.
- **Quick adjustment** between syncs: "spent 2 divine" → append `{name:"Divine Orb", delta:-2, ...}`.
  Adjustments are a stopgap; a fresh screenshot supersedes them (clear that tab's adjustments on resave).

When answering, if the inventory is old, note it ("last synced 2 days ago — re-screenshot for an exact
number") rather than presenting a stale total as current.

## Beginner how-to

If the player doesn't know what to send: *"Open your stash, click the Currency tab, screenshot it, and
drop it here"* (full steps in `poe2-core/references/how-to.md`). Repeat per tab you want tracked.

## Guardrails

- **Never invent or round a count you can't read.** Flag it Low and ask, or leave it out.
- **Confirm before every save.** No silent writes from a screenshot.
- Valuation is via `value_currency` (deterministic), not mental math over the list.
- Don't compile or expose anything beyond the currency the player chose to share.
