---
patch: 0.5.5e
refreshed: 2026-10-07
---
# Crafting knowledge (patch-dependent — verify against the live game)

> **Freshness stamp: researched 2026-10-03; item rules re-sourced from game data 2026-10-06 (patch
> 0.5.5e); mod tiers moved to `mod_tiers`, and currency text, essence modifiers and augment effects to
> `item_text`, 2026-10-07.** Affix limits
> are from the game's `Rarity` table, and the corrupted-item error from its client strings, both in
> repoe-fork/dat-export@16088913cc94 (game 4.5.5.2). The Greater/Perfect minimum modifier levels are
> from poe2db's currency page. Sources: dat-export `Rarity.csv`, `ClientStrings.csv`; poe2db
> `Stackable_Currency`. Where to look things up, and what to avoid, is in `poe2-core`'s
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
  that tier's modifier level — `mod_tiers` gives it as each tier's `itemLevel`.
- **Corrupted items take only the currencies made for them** — those whose text or `use` names a
  corrupted item; search `item_text` for "corrupted". The game's error for any other currency used on a
  corrupted item is "Target is corrupted." (client string `ItemErrorTargetCorrupted`). *Derived, not
  quoted:* a currency whose text doesn't name corrupted items fails with that error. Check for
  "Corrupted" on the item before anything else.
- **Fixed-value mods have no range.** A mod written without a `(min—max)` range, like
  `+1 to Level of all Minion Skills`, is the same at every roll. Only a *different tier* changes it.

## What each currency does

Look it up with `item_text`: the game's own text says what a currency does (`text`) and what it's used
on (`use`). Quote it; never fill it in from memory. Omens too — an omen's text names the currency it
changes, and how ("your next Chaos Orb will remove only prefix modifiers").

Essences (and Expedition's alloys) add a known modifier: their `adds` gives it for each kind of item
(`on`), with its value range and side. Their `text` says which rarity they take — some turn a Magic item
Rare, others remove a random modifier from a Rare first.

Runes, soul cores and idols (augments) go into an empty Augment socket; an Artificer's Orb adds one (its
text says to what). Their `adds` gives the effect for each kind of item they fit (`on`; "All" is any
equipment). A `bonded` effect is a Bonded modifier, which the game gives only to a Shaman who allocated
Wisdom of the Maji. `limit` caps how many can be socketed — the game: no more than one Ancient Augment
at a time — and `level` is the augment's level requirement. Read its text before socketing: most can be
replaced but not taken back out, and some can't be replaced either.

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

*Derived, not quoted:* each has a cost the player must hear before using it — read its text. Some can
destroy the item (Architect's Orb, Crystallised Corruption: "…or destroys it"), and an Orb of
Sacrifice removes a random modifier, which can be one the player wants to keep.

## Mod tiers

Look tiers up with `mod_tiers` — the item's base, the mod, and its item level. It lists every family a
base can roll, each tier's value range and the item level it needs, from the game's own data; a found
base with no matching family means the mod can't roll there. Never fill in a tier from memory.

Corruption is separate: on a helmet, a Vaal corruption enchantment can give `+1 to Level of all Minion
Skills`, and poe2db lists an "upgraded corruption" version at +2. Both make the item corrupted.

## Not researched

Mark these "not researched" if they come up rather than guessing: for an essence, whether its modifier
needs the item's level, and what it does when the side its modifier needs is full; how many Augment
sockets an item can have; Desecrated mods, the crafting bench / recombinators, Divine on
implicits, how an item becomes corrupted twice (the trade site has a "twice corrupted" filter, so some
way exists), and **odds** of hitting a specific mod (the game data the tools use marks which mods can
roll, not how likely each is).
