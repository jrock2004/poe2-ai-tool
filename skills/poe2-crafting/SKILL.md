---
name: poe2-crafting
description: Say whether a Path of Exile 2 crafting currency is worth using on a specific item for a specific goal — and stop the player before they waste it. Use when the player asks "should I divine this", "is this worth an exalt/chaos/regal", "can I get +2 on this", or "how do I roll X on this item".
---
# poe2-crafting

**Before any other tool call, invoke the `poe2-core` skill** with the Skill tool; its rules apply here
and aren't restated. One item, one goal, one currency: **can this currency get the item to the
goal, and is it the best way to spend it?** The answer is often "no — that orb can't change that
mod," and saying so before any cost talk is the skill's main value.

Mod tiers and their item-level gates come **only** from `mod_tiers` (the game's own data, per base);
what a currency, omen, essence or rune does **only** from `item_text` (the game's own text); affix
limits and the rules around them **only** from `get_knowledge('crafting')`. If what you need isn't in
any of them, say "not researched — check poe2db" and lower confidence. Never fill in a tier, item-level
gate, currency effect, or odds from memory.

Scope: single-currency decisions and short paths (a few orbs, an essence, a rune, or an omen steering
one of them). Not full multi-step craft plans, and not Desecrated mods or the bench — those are "not
researched".

## 1. Read the item

Get, best fidelity first: the **in-game item text** (Ctrl+C, per `poe2-core/references/how-to.md`),
else a **screenshot**, else the player's description. From it, establish:

- **Rarity** (Normal / Magic / Rare / Unique) and **item level**.
- **Corrupted?** If yes, only currencies whose text names a corrupted item can change it (search
  `item_text` for "corrupted"). If the player's currency isn't one of them, stop there.
- **Each explicit mod**, whether it's a **prefix or suffix**, and whether it has a **range** or a
  fixed value. Match each mod to its tier with `mod_tiers` — the item's base type (its item text names
  it), the mod as `search` — by its value.
- **Open affixes** — how many prefix/suffix slots are still free against the rarity's limits.

Anything you inferred rather than read (rarity from a description, a mod's side or tier you couldn't
match in `mod_tiers`), say so — it lowers confidence.

## 2. Pin down the goal

Restate the goal as a target mod and tier ("suffix `+2 to Level of all Minion Skills`, tier *of the
Despot*"). Then check it's **reachable on this item at all**:

- Does the target roll on this **base** at all, and up to which tier? Call `mod_tiers` with the base,
  the target mod as `search`, and the item's `item_level`. A found base with no matching family means
  it can't roll there — say so plainly.
- Can the target tier roll at this **item level**? Its `canRoll` says; each tier's `itemLevel` is the
  gate.
- Is there an **open affix of the right side**, or would one have to be removed first?

If `mod_tiers` can't find the base (check its `suggestions`), you can't confirm reachability — say so.

## 3. Gate check: can this currency do it?

Look the currency up with `item_text` — its `text` says what it does, its `use` what it's used on —
and, with the knowledge file's rules, answer plainly before anything else:

- **Wrong rarity** — e.g. Chaos or Exalted on a Magic item, Augmentation on a Rare.
- **Wrong kind of change** — Divine only rerolls numbers within the current tiers. It can't add a mod,
  remove one, or change a tier, and does nothing to fixed-value mods.
- **Minimum modifier level excludes the target** — a Greater/Perfect orb whose minimum is above the
  target tier's modifier level (its `itemLevel` in `mod_tiers`) can never roll it.
- **No room** — an adding orb with no open affix on the needed side.
- **Corrupted item** — any currency whose text doesn't name a corrupted item fails on it.

If the currency fails the gate, **say "don't use it" and why in one sentence**, then go to §4 for what
would work. Don't soften this — telling the player their divine is safe is the point.

## 4. Real paths to the goal

List the 1–3 paths that can actually reach the goal, cheapest first:

- **Fresh base** — Transmute/Augment new bases of sufficient item level (plain orbs, unless a
  Greater/Perfect minimum still allows the target tier).
- **Remove and re-add** — Annulment then an adding orb, or Chaos on a Rare. Name the risk: removal is
  random, so it can hit the mod the player wants to keep.
- **Steer it with an omen** — search `item_text` for the currency's name: an omen whose text names it
  can narrow what it does (Omen of Sinistral Erasure: the next Chaos Orb removes only prefixes). Its
  `use` says how to activate it; it's used up when it triggers.
- **Use an essence** — search `item_text` for the target mod (e.g. "movement speed"): an essence (or
  alloy) whose `adds` has it `on` this kind of item adds exactly that modifier, in the range shown. Its
  `text` says which rarity it takes — some turn a Magic item Rare, others remove a random modifier from
  a Rare first (name that risk, as for Chaos). Its `side` needs room; what happens when that side is
  full is not researched.
- **Socket a rune, soul core or idol** — search `item_text` for the target mod: an augment whose
  `adds` has it `on` this kind of item ("All" is any equipment) gives that effect. It needs an empty
  Augment socket (an Artificer's Orb adds one). Check its `limit` against what's already socketed and
  its `level` against the character's. Count a `bonded` effect only for a Shaman with Wisdom of the
  Maji. Say what its text says about replacing it later — some can't be. Name it with its kind and
  where it's found (`poe2-core/references/currency-glossary.md` → "Socketables").
- **Buy it** (trade leagues only — see §5).

On a corrupted item, the only paths are the currencies made for corrupted items, or a new item. Say
what each one risks, from its text — some can destroy the item, and some remove a random mod.

Describe odds qualitatively ("unlikely — one random suffix out of many"). The game data says what can
roll, not how likely it is, so **never give a percentage or "1 in N"**.

## 5. Cost and alternatives

Branch on the character's `trade_mode` (see "Trade or SSF" in `poe2-core`).

- **SSF:** no market. Compare against what else that currency could do for the player — e.g. a
  Divine is better spent on a finished Rare with low rolls on the right mods.
- **Trade league:** price the currency with `value_currency` / `get_currency_prices`, and price the
  finished item with `find_stat_filters` + `build_trade_filter` + `search_trade` (per
  `poe2-price-check`). If the finished item's `priceStats.medianExalted` is below the expected
  crafting spend, say **"just buy it"** and give the trade link. The player buys it themselves.

## 6. Answer

Lead with the verdict — **use it / don't use it / use X instead** — then the one-line reason, the
recommended path, and confidence. Keep it short; the player is usually standing at the stash.

## Confidence (per `poe2-core/references/confidence.md`)

- **High** — item read from item text or a clear screenshot, every tier, gate and currency effect in
  the answer comes from `mod_tiers`, `item_text` or the knowledge file, and their `patch` matches the
  live patch.
- **Medium** — some item detail inferred, or the data may be a patch behind (its `patch` is older).
- **Low** — a tier, gate, or currency behaviour in the answer is "not researched", or the item was
  only described. Name the one thing that would raise it (the item text, or the item's base type).

A "don't use it" verdict that rests only on currency behaviour (e.g. Divine vs. a fixed-value mod) can
be High even when the tiers aren't researched — the gate doesn't depend on them. For trade-league
cost comparisons, the market thresholds in `confidence.md` also apply and the band is capped by the
weakest signal.

## Guardrails

- **Gate before cost.** Never price a craft the currency can't perform.
- **No invented numbers or effects.** Tiers and item-level gates come from `mod_tiers`, what a
  currency does from `item_text`; odds are qualitative only.
- **Corrupted means only the currencies made for corrupted items.** Everything else fails on one.
- **Don't assume SSF or trade** — read `trade_mode`, per `poe2-core`.
- Never buy, list, or whisper. Output is advice and trade links the player acts on.
