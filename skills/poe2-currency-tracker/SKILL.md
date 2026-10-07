---
name: poe2-currency-tracker
description: Track the player's Path of Exile 2 currency by reading screenshots of their currency, essence, ritual, and other special stash tabs into a remembered inventory, and answer affordability and net-worth questions. Use when the player shares a stash-tab screenshot or asks "what can I afford", "what's my net worth", or "how much currency do I have".
---
# poe2-currency-tracker

Load `poe2-core` first. There is **no PoE2 stash API**, so the inventory can't be read from the game —
the player sends **screenshots** of their special stash tabs and this skill reads them (vision)
into a remembered inventory per league and trade mode, then values it and answers "can I afford this?".

Vision can misread a stack count or a look-alike icon, so the rule is **confirm before saving** and
**never guess** — a wrong count silently corrupts every affordability answer downstream.

## State: currency inventory (per league + trade mode)

Currency is pooled by **league and trade mode**: every trade character in a league shares one pool, and
every SSF character in it shares another — in-game they're separate stashes (see the shared model in
`poe2-core`). Saved state (`update_state`) keys it by both:

```
currency[league][trade_mode] = {
  tabs: {
    "<tab>": {                   # get_stash_layout's tab name, e.g. "currency", "essence"
      items: [ { name, count, confidence } ],   # name = canonical (glossary-normalized)
      captured_at: <when the screenshot was read>,
      source: "screenshot"
    }, ...
  },
  adjustments: [ { name, delta, note, at } ],    # manual between-sync tweaks, e.g. spent 2 divine
  updated_at
}
```

**Which pool** — the one matching the character being worked on: its `league` and `trade_mode`. If
there's no active character, or its `trade_mode` is unset, ask before saving — a screenshot saved to
the wrong pool silently corrupts both.

**Totals** = per-name sum across all tabs, plus any `adjustments`. Keep tabs separate so re-sending one
tab replaces just that bucket instead of double-counting: patch only that tab, e.g.
`{"currency": {"<league>": {"trade": {"tabs": {"currency": {...}}}}}}`. `adjustments` is an array, so
a patch replaces it whole — send the full list.

## Reading a screenshot

The special stash tabs are **fixed layouts**: each slot always holds the same item, held or not. So
**name every item from its slot, never from its icon art** — look-alikes (Lesser Jeweller's vs.
Artificer's, Chance vs. Divine, Gemcutter's vs. Glassblower's, the essence tiers) misread easily.
Read only the **count** from the image. `get_stash_layout(tab)` says which item is in which slot.

1. **Detect the tab.** Use the highlighted tab name at the top of the screenshot and the shape of the
   grid, then call `get_stash_layout` for it. It covers: abyss, breach, currency, delirium, essence,
   expedition, fragment, ritual, socketable. Confirm with the player only when:
   - the tab name is unreadable and the grid could fit more than one tab;
   - the screenshot doesn't fit the returned rows (a block missing or shifted, a different slot
     count) — stop and ask which tab it is; don't force the layout onto it;
   - it's an ordinary tab (not in that list) — slots there aren't fixed, so ask the player to name
     the items they want tracked rather than guessing from icons.
   One screenshot → one tab, saved under the tool's tab name.
2. **Walk the rows.** `rows` is in reading order: top to bottom, each row left to right across the
   whole tab, every slot counted — so a row's Nth slot on screen is its Nth entry. Rows are grouped
   by height within half a slot, so a block set a little lower (Currency's Etcher / Scrap /
   Whetstone) belongs to the row beside it. Tabs with pages (fragment, expedition, socketable) give
   each row a `subTab`; read only the rows for the page shown, and ask if you can't tell which.
3. **Read each slot:**
   - **Dim or silhouetted → 0.** It's a known item the player has none of. Leave it out of the save.
   - **Lit → the printed count, top-left.** Read it exactly. A lit slot with no legible count is a
     Low line — flag it; don't assume 1.
   - **II / III, bottom-right, is the tier mark**, not part of the count. Use it only to cross-check
     that the slot's item is a Greater / Perfect tier.
   - **`item` null is an open slot** — it holds whatever the player put there. If one is lit, its
     name comes from the icon alone: say so, mark that line Low, and ask the player to hover it.
   - **`label`** (Ritual) is the small currency icon above a group of omens. It labels the group; it
     isn't a slot and has no count.
   - **`craftingSlot`** — the tall slot in the middle. Never read it.
4. **Handle what the rows can't place:**
   - A slot outside every row (e.g. Ritual's strip down the left edge) is one of `onlyWhenHeld`.
     If exactly one candidate fits, use it; otherwise ask the player to hover it.
   - A slot named in `overlaps` sits on the same spot as another in the data. If it's dim, it's 0
     either way — skip it. If it's lit, ask which item it is. (Ritual's top row in 0.5.5: the wide
     slot shown is Head of the King; Petition Splinter under it is a legacy item, unusable since
     0.5.0.)
5. **Score each line's confidence** per `poe2-core/references/confidence.md`. A name read from its
   slot on a crisp screenshot is High. Lower it when:
   - the count is blurry, cropped, or partly hovered over;
   - the name came from an open slot's icon (Low);
   - **the layout's `patch` is older than the live patch** — Knowledge recency: the slot map may
     have moved. Say the layout hasn't been checked for this patch and ask the player to confirm
     any line that looks off.
   Flag the specific uncertain lines; don't average them away.
6. **Show what you read and ask to confirm** before saving:
   > Read from your **currency** tab: Exalted ×20, Divine ×4, Chaos ×2, Vaal ×12, Scroll of Wisdom
   > ×334 *(Wisdom count partly covered — Low)*. Save this? Correct anything that's off.
7. **On confirm, save** (replace that tab). On a correction, apply it and save the corrected value.

Names from `get_stash_layout` are the game's own names, so they price as-is through
`value_currency`; use `poe2-core/references/currency-glossary.md` only for names the player types.

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
- **"Should I sell or hold X?" / "what's moving?"** → that's `poe2-meta-strategy`: it reads this
  inventory against the week's divine-relative market moves.

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
