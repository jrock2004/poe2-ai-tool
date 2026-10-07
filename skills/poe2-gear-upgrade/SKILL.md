---
name: poe2-gear-upgrade
description: Look at the player's Path of Exile 2 character and recommend gear upgrades ranked by value-per-currency, with trade filters to find them (or, for SSF, how to craft or farm them). Use when the player asks "how do I improve my gear", "what should I upgrade next", or "is this an upgrade".
---
# poe2-gear-upgrade

Load `poe2-core` first. This is the composition skill (F1): read the character, find the slots that are
holding the build back, and for each one produce a **realistic, affordable** market upgrade with a trade
link — prioritized so the player fixes the biggest problem per currency spent, not everything at once.

It composes what's already built: `poe2-character` (whose build, and its goal), a gear read (a PoB code
from a character import, or a screenshot), `find_stat_filters` + `build_trade_filter` + `search_trade`
(the upgrades), and `value_currency` + `poe2-currency-tracker` (what's actually affordable).

## 1. Get the character, its gear, and its *targets*

- Resolve the character via `poe2-character` (active one, or a named override). Use its **goal** and
  **archetype** — an upgrade is only an upgrade *relative to what the build is trying to do*.
- Read the gear, best fidelity first: a **PoB code from a character import** via `parse_pob_code` (the
  real gear, with computed resistances, life/ES and DPS — ideal for diagnosis; the how-to "Get your
  character into Path of Building" gets one), else a **character screenshot**, else the player's
  description. If a slot is unreadable, say so rather than assuming it's empty.
- **Anchor to the build's targets, don't invent them.** "What you *should* be running" depends on the
  build's plan, which the gear alone doesn't tell you. In order of preference:
  1. **A guide the player is following** — hand off to `poe2-build-review` / `fetch_guide` to get the
     stage-appropriate targets (defence layers, the scaling stat, gem/gear the build expects).
  2. **The PoB's own shape** — the ascendancy, tree, and gems reveal intent (e.g. an evasion/life build
     vs. an ES stacker); read the plan *from the build* rather than assuming a generic one.
  3. **General benchmarks** — only as a fallback, and **say so**: "you're not following a guide I can
     see, so this is generic (cap resists, more life/EHP); a guide or your target would sharpen it,"
     and drop the confidence band accordingly (§Confidence).
  Never assert a build "should" use X without one of these — a low-life evasion build and an ES stacker
  want opposite gear.

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

**SSF characters** (`trade_mode`, see `poe2-core`) can't buy, so §3–§5 don't apply — the trade search,
value-per-currency ranking, and budget are all market steps. Instead, for each weak slot in severity
order (§2):

1. **Name the target** — the 1–2 mods that fix the slot, from the build's targets (§1). Don't invent
   tier numbers: take them from `mod_tiers` (the base, the mod, its item level) or the guide.
2. **Name the route** — craft it from a base the player has (hand off to `poe2-crafting`, which checks
   the currency can actually do it), or keep playing for it: what to pick up and check while mapping.
3. **Net-diff still applies** (§3b) to anything they craft or find.

Confidence comes from the gear read and the target's source (§1); the market signals don't apply.

**Trade characters:**

For each priority slot:

1. **Resolve the fixing mod** with `find_stat_filters` (e.g. "+# to maximum Life", "#% to Fire
   Resistance").
2. **Build the filter** with the slot's category and a realistic `min` — set it a bit *below* an
   ideal roll so you get real comparables, and combine the 1–2 mods that actually matter for that slot
   (e.g. boots: movement speed + the missing resist). Set `max_price` from the player's budget, and
   `max_level` to the character's level (from the PoB code, or ask) so every result can be worn now —
   or to the level they're planning for, if they ask ahead ("what should I buy at 65?").
3. **Search** with `search_trade` and read the cheapest matches. Its `priceStats.medianExalted` is the
   slot's realistic cost — use it (not the single cheapest listing) for ranking and affordability.

**Slot → trade category** (verified):

| Slot | category | Slot | category |
|---|---|---|---|
| Helmet | `armour.helmet` | Amulet | `accessory.amulet` |
| Body armour | `armour.chest` | Ring | `accessory.ring` |
| Gloves | `armour.gloves` | Belt | `accessory.belt` |
| Boots | `armour.boots` | Weapon | `weapon.<type>` — confirm the subtype |

Weapon/off-hand subtypes vary (crossbow, bow, quarterstaff, spear, …); if unsure of the exact category
string, search without a category and filter by the weapon's mods, or confirm the type first.

## 3b. Net-diff the swap — never break the build to fix one stat

An upgrade **replaces** an item, so judge the *whole difference*, not just the headline mod it adds. A
piece that adds life but drops a stat the build needs is a downgrade. Before recommending any swap,
account for everything the current item provides and check the replacement doesn't regress it:

- **Attributes vs. requirements.** Losing Str/Dex/Int can drop you **below a gem or gear requirement**,
  making a skill or item **unusable**. Compare each attribute against its requirement (PoB exposes
  `Str`/`ReqStr`, `Dex`/`ReqDex`, `Int`/`ReqInt`): headroom = attribute − requirement. If the old item
  supplies more of an attribute than your headroom, the replacement **must** replace that attribute or
  the swap breaks the build. Say the exact numbers.
- **Resistances.** Don't uncap a resist to add life. If the old item carried the resistance keeping you
  at 75%, the new one must too (watch thin overcaps especially).
- **Spirit / reservations.** Losing Spirit can push you past what your auras/heralds/marks reserve
  (PoB's `SpiritUnreserved` is the headroom). Flag it if the swap would over-reserve.
- **The build's scaling stat.** Don't drop the mod the build's damage actually keys on (e.g. `+Level of
  all Projectile Skills`) just to add a defensive stat, unless that's the deliberate trade.

Present the swap as a **net change** ("+105 life, keeps Str/Dex above requirements, but −39 Spirit —
you'd need to free ~20 Spirit"), and reject outright any option that makes gear/skills unusable.

## 4. Rank by value-per-currency and set the budget

- Pull the player's currency worth from `poe2-currency-tracker` / `value_currency` and use it as the
  price ceiling, so recommendations are things they can **actually buy now**, not aspirational.
- Rank by **biggest problem fixed per currency**: a cheap item that caps a resist beats an expensive
  one that adds marginal damage. The "currency" side is each slot's `priceStats.medianExalted`, so
  slots compare in one unit. Present the cheapest listing that genuinely fixes the slot (unless it's a
  lone outlier — see the rubric), then a step-up option if they want to spend more.
- Mark each as **affordable now** vs **save up** by comparing `medianExalted` to `value_currency`'s
  `totalExalted` — both are exalted, so no conversion. Give the trade `url` for each —
  the player buys it themselves (never auto-buy/whisper).

## 5. Iterate

This is a loop, not a one-shot. The player pastes back what the search returned or bought; critique it
("those are overpriced because the crit filter is too tight — drop it and the floor halves") and refine
the filter. Keep the last search in this conversation so "cheaper" / "loosen it" continues without
re-stating everything. If a search returns nothing, widen it (per `poe2-price-check`) rather than
reporting a shaky result.

## Confidence (per `poe2-core/references/confidence.md`)

- **High** — real gear, from a character-import PoB code or a clear screenshot, + a healthy sample of
  comparable listings.
- **Medium** — some gear or intent inferred, or a thin listing sample.
- **Low** — build/goal guessed, or a slot unreadable. Say what would raise it (a PoB code from a
  character import, confirming the build's goal, a currency-tab screenshot for the budget).

"Healthy" / "thin" sample means the rubric's **Market signals** thresholds on each slot's
`priceStats` (sample, spread, coverage) and `ageSeconds` — the band is capped by the weakest. When
slots score differently, give the overall band from the recommended (top-ranked) slot and flag any
other slot that's Low.

## Guardrails

- **Never break the build to fix one stat.** Net-diff every swap (§3b) — an item that adds life but
  drops an attribute below a skill/gear requirement, uncaps a resist, or over-reserves Spirit is a
  downgrade. Reject it.
- **Don't assert what the build "should" run without a source** — a guide, the PoB's own shape, or a
  stated goal (§1). If it's generic benchmarks, say so and lower confidence.
- **Fix survivability before damage.** Don't rank a damage upgrade above an uncapped resist.
- **Respect the budget.** Don't push an item the player can't afford without labeling it "save up".
- **One problem at a time.** Recommend the highest-impact fix first; don't tell them to replace six
  slots at once.
- Never buy, list, or whisper. Output is advice + trade links the player acts on.
