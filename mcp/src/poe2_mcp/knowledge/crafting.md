---
patch: 0.5.5
refreshed: 2026-10-03
---
# Crafting knowledge (patch-dependent — verify against the live game)

> **Freshness stamp: researched 2026-10-03.** Patch not confirmed at research time. Currency
> descriptions and mod tiers below are from poe2db's data pages; affix limits and corruption rules are
> from Mobalytics' crafting guides. Sources: poe2db `Stackable_Currency`, `Helmets_*`, `Amulets`,
> `Sceptres`; mobalytics.gg `poe-2/guides/item-modifiers`, `poe-2/guides/vaal-corrupting`. (Maxroll,
> poe2wiki and game8 are off-limits — see `CONTRIBUTING.md`.) If the player quotes different in-game
> wording, trust the game and lower confidence.

The skill's job is a **gate check before a cost check**: can this currency change the thing the player
wants at all? Most wasted currency comes from using the right orb for the wrong job — most often a
Divine on a mod that has no range.

---

## Item rules

- **Affix limits.** Magic: up to **1 prefix + 1 suffix**. Rare: up to **3 prefixes + 3 suffixes**.
  A mod can only be added if its side (prefix/suffix) has room.
- **Mod level gates item level.** A mod tier can only roll on an item whose item level is at least
  that tier's modifier level. poe2db lists this as the tier's "Level".
- **Corrupted items can't be modified** — no currency works on them, including another Vaal Orb.
  Check for "Corrupted" on the item before anything else.
- **Fixed-value mods have no range.** A mod written without a `(min—max)` range, like
  `+1 to Level of all Minion Skills`, is the same at every roll. Only a *different tier* changes it.

## What each currency does

Descriptions quoted from poe2db's currency page.

| Currency | Does | Works on |
|---|---|---|
| Orb of Transmutation | "Upgrades a Normal item to a Magic item with 1 modifier" | Normal |
| Orb of Augmentation | "Augments a Magic item with a new random modifier" | Magic with an open affix |
| Regal Orb | "Upgrades a Magic item to a Rare item, adding 1 modifier" | Magic |
| Orb of Alchemy | "Upgrades a Normal or Magic item to a Rare item with 4 random modifiers" | Normal, Magic |
| Exalted Orb | "Augments a Rare item with a new random modifier" | Rare with an open affix |
| Chaos Orb | "Removes a random modifier and augments a Rare item with a new random modifier" | Rare |
| Orb of Annulment | "Removes a random modifier from an item" | Magic, Rare |
| Divine Orb | "Randomises the numeric values of modifiers on an item" | Any uncorrupted item with ranged mods |
| Fracturing Orb | "Fracture a random modifier on a rare item with at least 4 modifiers, locking it in place" | Rare, 4+ mods |
| Vaal Orb | "Modifies an item unpredictably and Corrupts it" | Uncorrupted |
| Orb of Chance | "Unpredictably either upgrades a Normal item to Unique rarity or destroys it" | Normal |
| Hinekora's Lock | "Allows an item to foresee the result of the next Currency item used on it. Modifying the item in any way removes the ability to foresee" | — |

**Greater / Perfect tiers.** Transmutation, Augmentation, Regal, Exalted and Chaos come in Greater
and Perfect versions with a **minimum modifier level**:

| Currency | Greater | Perfect |
|---|---|---|
| Transmutation, Augmentation | 44 | 70 |
| Regal, Exalted, Chaos | 35 | 50 |

*Derived, not quoted:* a minimum modifier level means tiers below it can't roll. That can **exclude
the tier the player wants** — e.g. +2 minion levels on a helmet is modifier level 41 (below), so a
Greater Transmutation (min 44) cannot roll it. Check the target tier's level against the minimum
before recommending a Greater/Perfect orb.

### Divine Orb — the common mistake

Divine rerolls numbers **within each mod's current tier**. It never adds, removes, or changes the tier
of a mod. So it:

- **does nothing** to fixed-value mods (`+1 to Level of all Minion Skills` stays +1),
- **is worth it** only when the item's mods are already the right ones and the *rolls* within their
  ranges are low.

Whether Divine also rerolls implicit mods: **not researched.**

## Mod tiers worth knowing

Only tiers that have been checked against poe2db are listed. For anything else, say "check poe2db"
and lower confidence — never fill in a tier from memory.

**`+# to Level of all Minion Skills`** — suffix, fixed values, mod family `IncreaseSocketedGemLevel`.

| Tier name | Value | Modifier level | Helmets (all armour types) | Amulets | Sceptres |
|---|---|---|---|---|---|
| of the Taskmaster | +1 | 5 (sceptres: 2) | yes | yes | yes |
| of the Despot | +2 | 41 (sceptres: 25) | yes | yes | yes |
| of the Overseer | +3 | 75 (sceptres: 55) | no | yes | yes |
| of the Slavedriver | +4 | 78 | no | no | yes |

Helmets can also get it from **corruption**: a Vaal corruption enchantment gives +1, and poe2db lists
an "upgraded corruption" version at +2. Both make the item corrupted.

## Not researched

Mark these "not researched" if they come up rather than guessing: Essences, Omens, Desecrated mods,
the crafting bench / recombinators, Divine on implicits, and **odds** of hitting a specific mod (mod
weights exist on poe2db but haven't been pulled in).
