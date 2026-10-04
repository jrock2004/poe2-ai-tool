---
name: poe2-crafting
description: Say whether a Path of Exile 2 crafting currency is worth using on a specific item for a specific goal — and stop the player before they waste it. Use when the player asks "should I divine this", "is this worth an exalt/chaos/regal", "can I get +2 on this", or "how do I roll X on this item".
---
# poe2-crafting

Load `poe2-core` first. One item, one goal, one currency: **can this currency get the item to the
goal, and is it the best way to spend it?** The answer is often "no — that orb can't change that
mod," and saying so before any cost talk is the skill's main value.

Facts about currencies, affix limits, and mod tiers come **only** from
`references/crafting-knowledge.md`. If what you need isn't there, say "not researched — check poe2db"
and lower confidence. Never fill in a tier, item-level gate, or odds from memory.

Scope: single-currency decisions and short paths (a few orbs). Not full multi-step craft plans, and
not Essences, Omens, Desecrated mods, or the bench — those are "not researched".

## 1. Read the item

Get, best fidelity first: the **in-game item text** (Ctrl+C, per `poe2-core/references/how-to.md`),
else a **screenshot**, else the player's description. From it, establish:

- **Rarity** (Normal / Magic / Rare / Unique) and **item level**.
- **Corrupted?** If yes, stop: nothing can modify it.
- **Each explicit mod**, whether it's a **prefix or suffix**, and whether it has a **range** or a
  fixed value. Match mods to tiers in the knowledge file by text and value where you can.
- **Open affixes** — how many prefix/suffix slots are still free against the rarity's limits.

Anything you inferred rather than read (rarity from a description, prefix/suffix from memory of a mod
not in the knowledge file), say so — it lowers confidence.

## 2. Pin down the goal

Restate the goal as a target mod and tier ("suffix `+2 to Level of all Minion Skills`, tier *of the
Despot*"). Then check it's **reachable on this item at all**:

- Does the target tier roll on this **item class**? (Helmets cap at +2 minion levels.)
- Is the item's **item level ≥ the tier's modifier level**?
- Is there an **open affix of the right side**, or would one have to be removed first?

If the tier isn't in the knowledge file, you can't confirm reachability — say so.

## 3. Gate check: can this currency do it?

Using the currency table in the knowledge file, answer plainly before anything else:

- **Wrong rarity** — e.g. Chaos or Exalted on a Magic item, Augmentation on a Rare.
- **Wrong kind of change** — Divine only rerolls numbers within the current tiers. It can't add a mod,
  remove one, or change a tier, and does nothing to fixed-value mods.
- **Minimum modifier level excludes the target** — a Greater/Perfect orb whose minimum is above the
  target tier's modifier level can never roll it.
- **No room** — an adding orb with no open affix on the needed side.

If the currency fails the gate, **say "don't use it" and why in one sentence**, then go to §4 for what
would work. Don't soften this — telling the player their divine is safe is the point.

## 4. Real paths to the goal

List the 1–3 paths that can actually reach the goal, cheapest first:

- **Fresh base** — Transmute/Augment new bases of sufficient item level (plain orbs, unless a
  Greater/Perfect minimum still allows the target tier).
- **Remove and re-add** — Annulment then an adding orb, or Chaos on a Rare. Name the risk: removal is
  random, so it can hit the mod the player wants to keep.
- **Buy it** (trade leagues only — see §5).

Describe odds qualitatively ("unlikely — one random suffix out of many"). Mod weights aren't
researched, so **never give a percentage or "1 in N"**.

## 5. Cost and alternatives

**Ask whether the character is in SSF if it isn't clear from the conversation** — don't assume
either way.

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

- **High** — item read from item text or a clear screenshot, and every tier/gate in the answer is in
  the knowledge file, which matches the live patch.
- **Medium** — some item detail inferred, or the knowledge file may be a patch behind.
- **Low** — a tier, gate, or currency behaviour in the answer is "not researched", or the item was
  only described. Name the one thing that would raise it (the item text, or confirming the tier on
  poe2db).

A "don't use it" verdict that rests only on currency behaviour (e.g. Divine vs. a fixed-value mod) can
be High even when the tiers aren't researched — the gate doesn't depend on them. For trade-league
cost comparisons, the market thresholds in `confidence.md` also apply and the band is capped by the
weakest signal.

## Guardrails

- **Gate before cost.** Never price a craft the currency can't perform.
- **No invented numbers.** Tiers, item-level gates, and currency behaviour come from the knowledge
  file; odds are qualitative only.
- **Corrupted means stop.**
- **Don't assume SSF or trade** — ask.
- Never buy, list, or whisper. Output is advice and trade links the player acts on.
