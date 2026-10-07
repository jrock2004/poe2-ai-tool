---
patch: 0.5.5e
refreshed: 2026-10-06
---
# Crafting knowledge (patch-dependent — verify against the live game)

> **Freshness stamp: researched 2026-10-03; item rules and corrupted-item currencies re-sourced from
> game data 2026-10-06 (patch 0.5.5e).** Currency descriptions and mod tiers are from poe2db's data
> pages. Affix limits are from the game's `Rarity` table, and the corrupted-item error from its client
> strings, both in repoe-fork/dat-export@16088913cc94 (game 4.5.5.2). Sources: poe2db
> `Stackable_Currency`, `Helmets_*`, `Amulets`, `Sceptres`; dat-export `Rarity.csv`,
> `ClientStrings.csv`. Where to look things up, and what to avoid, is in `poe2-core`'s
> `references/sources.md`. If the player quotes different in-game wording, trust the game and lower
> confidence.

The skill's job is a **gate check before a cost check**: can this currency change the thing the player
wants at all? Most wasted currency comes from using the right orb for the wrong job — most often a
Divine on a mod that has no range.

---

## Item rules

- **Affix limits** (`Rarity` table). Magic: up to 2 mods, at most **1 prefix + 1 suffix**. Rare: up
  to 6 mods, at most **3 prefixes + 3 suffixes**. A mod can only be added if its side
  (prefix/suffix) has room.
- **Mod level gates item level.** A mod tier can only roll on an item whose item level is at least
  that tier's modifier level. poe2db lists this as the tier's "Level".
- **Corrupted items take only the corruption currencies** listed under "Currencies for corrupted
  items" below. The game's error for a currency used on a corrupted item is "Target is corrupted."
  (client string `ItemErrorTargetCorrupted`). *Derived, not quoted:* the other currencies in this
  file don't name corrupted items, so treat them as failing with that error. Check for "Corrupted"
  on the item before anything else.
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

### Currencies for corrupted items

Descriptions quoted from poe2db's currency page.

| Currency | Does |
|---|---|
| Architect's Orb | "Modifies a Corrupted Equipment or Jewel item unpredictably or destroys it" |
| Yaomac's Orb of Sacrifice | "Upgrades a Corruption Enchantment on a Rare Weapon or Quiver and removes a random Modifier" |
| Kopec's Orb of Sacrifice | "Upgrades a Corruption Enchantment on a Rare Armour and removes a random Modifier" |
| Kamasa's Orb of Sacrifice | "Upgrades a Corruption Enchantment on a Rare Amulet, Ring or Belt and removes a random Modifier" |
| Yugul's Orb of Sacrifice | "Upgrades a Corruption Enchantment on a Rare Jewel and removes a random Modifier" |
| Vaal Cultivation Orb | "Replaces up to 2 modifiers on a Corrupted Vaal Unique" / "Replaces other Uniques with a Corrupted Unique of the same Item Class" |
| Crystallised Corruption | "Modifies a Corrupted Skill Gem unpredictably or destroys it" |

*Derived, not quoted:* each of these has a cost the player must hear before using it. Architect's
Orb and Crystallised Corruption can destroy the item, and an Orb of Sacrifice removes a random
modifier, which can be one the player wants to keep.

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
the crafting bench / recombinators, Divine on implicits, how an item becomes corrupted twice (the
trade site has a "twice corrupted" filter, so some way exists), and **odds** of hitting a specific
mod (mod weights exist on poe2db but haven't been pulled in).
