---
name: poe2-gear-upgrade
description: Look at the player's Path of Exile 2 character and recommend gear upgrades ranked by value-per-currency, with trade filters to find them. Use when the player asks "how do I improve my gear", "what should I upgrade next", or "is this an upgrade".
---
# poe2-gear-upgrade

Load `poe2-core` first. This is the composition skill (F1): read the character, find the slots that are
holding the build back, and for each one produce a **realistic, affordable** market upgrade with a trade
link — prioritized so the player fixes the biggest problem per currency spent, not everything at once.

It composes what's already built: `poe2-character` (whose build, and its goal), a gear read (screenshot),
`find_stat_filters` + `build_trade_filter` + `search_trade` (the upgrades), and `value_currency` +
`poe2-currency-tracker` (what's actually affordable).

## 1. Get the character and its gear

- Resolve the character via `poe2-character` (active one, or a named override). Use its **goal** and
  **archetype** — an upgrade is only an upgrade *relative to what the build is trying to do*.
- Read the gear, best fidelity first: a **PoB code** via `parse_pob_code` (gives computed resistances,
  life/ES, DPS + gear + gems — ideal for diagnosis), else a **character screenshot**, else the player's
  description. There's no OAuth auto-import (GGG isn't issuing keys). If a slot is unreadable, say so
  rather than assuming it's empty.

## 2. Diagnose the weak slots (survivability before damage)

Rank problems by severity, not by what's easiest to shop for:

1. **Uncapped elemental resistances.** Fire/Cold/Lightning cap at **75%**. Anything below cap is the
   top priority — it's the difference between surviving a hit and not. Chaos res is often negative and
   harder to fix; note it but don't obsess unless the build is chaos-fragile.
2. **Low life / energy shield** for the character's level and goal (bossing wants more than mapping).
3. **Unmet attribute or requirement gaps** (str/dex/int to equip/use skills), and **Spirit** for
   minion/aura builds (it gates how much they can run).
4. **Damage bottleneck** — only after the defensive floor is met. Which stat the build scales
   (from the archetype/guide) is what you look for here.

Compare against the build's **goal/guide targets** where known; don't invent exact numbers the game
may not use. State plainly *which* slot is weakest and *why* — "your boots have no resistances and
you're 40% fire, that's your survivability hole."

## 3. Find upgrades for the weak slot(s)

For each priority slot:

1. **Resolve the fixing mod** with `find_stat_filters` (e.g. "+# to maximum Life", "#% to Fire
   Resistance").
2. **Build the filter** with the slot's category and a realistic `min` — set it a bit *below* an
   ideal roll so you get real comparables, and combine the 1–2 mods that actually matter for that slot
   (e.g. boots: movement speed + the missing resist). Set `max_price` from the player's budget.
3. **Search** with `search_trade` and read the cheapest matches.

**Slot → trade category** (verified):

| Slot | category | Slot | category |
|---|---|---|---|
| Helmet | `armour.helmet` | Amulet | `accessory.amulet` |
| Body armour | `armour.chest` | Ring | `accessory.ring` |
| Gloves | `armour.gloves` | Belt | `accessory.belt` |
| Boots | `armour.boots` | Weapon | `weapon.<type>` — confirm the subtype |

Weapon/off-hand subtypes vary (crossbow, bow, quarterstaff, spear, …); if unsure of the exact category
string, search without a category and filter by the weapon's mods, or confirm the type first.

## 4. Rank by value-per-currency and set the budget

- Pull the player's currency worth from `poe2-currency-tracker` / `value_currency` and use it as the
  price ceiling, so recommendations are things they can **actually buy now**, not aspirational.
- Rank by **biggest problem fixed per currency**: a cheap item that caps a resist beats an expensive
  one that adds marginal damage. Present the cheapest listing that genuinely fixes the slot, then a
  step-up option if they want to spend more.
- Mark each as **affordable now** vs **save up** against their currency. Give the trade `url` for each —
  the player buys it themselves (never auto-buy/whisper).

## 5. Iterate

This is a loop, not a one-shot. The player pastes back what the search returned or bought; critique it
("those are overpriced because the crit filter is too tight — drop it and the floor halves") and refine
the filter. Keep the last search in active trade context so "cheaper" / "loosen it" continues without
re-stating everything. If a search returns nothing, widen it (per `poe2-price-check`) rather than
reporting a shaky result.

## Confidence (per `poe2-core/references/confidence.md`)

- **High** — real gear read from a clear screenshot + a healthy sample of comparable listings.
- **Medium** — some gear or intent inferred, or a thin listing sample.
- **Low** — build/goal guessed, or a slot unreadable. Say what would raise it (a clearer character
  screenshot, confirming the build's goal, a currency-tab screenshot for the budget).

## Guardrails

- **Fix survivability before damage.** Don't rank a damage upgrade above an uncapped resist.
- **Respect the budget.** Don't push an item the player can't afford without labeling it "save up".
- **One problem at a time.** Recommend the highest-impact fix first; don't tell them to replace six
  slots at once.
- Never buy, list, or whisper. Output is advice + trade links the player acts on.
