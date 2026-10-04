---
patch: 0.5.5d
refreshed: 2026-10-04
---
# Farming knowledge (patch-dependent — verify against the live game)

> **Freshness stamp: researched 2026-10-03, patch 0.5.5 (Forbidden Rites, ends with 1.0 on
> 2026-12-11).** Mechanics shift by patch. Treat this as **best-effort, not authoritative**; if the
> player sees something different in game, trust the game and lower confidence.
>
> **Sources:** official 0.5.5 patch notes (pathofexile.com forum thread 4000864 — quoted lines below
> are verbatim) and its hotfixes through 0.5.5d (checked 2026-10-04); poe2db.tw mechanic pages (Breach, Delirium, Ritual, Expedition, Abyss). Item
> families come from **poe2scout's live category lists**, not from memory. Not used: poe2wiki
> (bot-challenge wall), game8 (blocks AI crawlers), Maxroll (license forbids AI use), and the
> currency-seller "guide" sites that dominate search results.

This file says **how each mechanic is targeted and what its outputs are for**. It deliberately has
**no yields, drop rates, or run times** — nothing reliable reports them. Pair it with
`market_movers` for *what those outputs are worth right now*; never turn the two into "X div/hour".

## Mechanics → what they produce

| Mechanic | Target it with | poe2scout category | Output families (from live data) |
|---|---|---|---|
| Breach | Breach Tablets | `breach`, `fragments` | Catalysts (basic + Refined); Breach Splinter → Breachstone; Breachlord Sac |
| Delirium | Delirium Tablets; Grand Mirrors | `delirium`, `fragments` | Liquid emotions (Diluted → Concentrated → Potent, each with an "Ancient" variant); Simulacrum Splinter → Simulacrum |
| Ritual | Ritual Tablets | `ritual` | Omens; Idols; Raven-Touched Shard; An Audience with the King (in `fragments`) |
| Expedition | Expedition Tablets; Logbooks | `expedition` | Expedition Logbook; Sagas; Flux (Thaumaturgic by level, Blazing/Chilling/Crackling/Void, Perfect); Carved / Emergent artifacts |
| Abyss | Abyss Tablets; Abyssal Ravines | `abyss` | Bones — Gnawed / Preserved / Ancient Jawbone, Rib, Collarbone; Preserved Cranium; Altered Collarbone; Gaze augments |
| Essences | (found in maps) | `essences` | Essences by tier (Lesser → Greater → Perfect, plus untiered) |
| Runes | (general drops; some from Expedition) | `runes` | Runes by tier and named runes |

## Per mechanic

**Breach.** Breach Tablets add Breaches to a map. Splinters combine into a Breachstone, which opens
a Breach domain. Catalysts add quality to rings, amulets and jewels that boosts a specific mod type —
so their prices follow which mods the crafting meta wants. 0.5.5: *"When stabilising an Unstable
Breach, it now spawns the Rare Monsters in waves of 5, instead of spawning them all at once."*

**Delirium.** Walk through a Mirror of Delirium and stay inside the expanding fog. Liquid emotions
instil notables onto amulets (and modify jewels), so their prices track which notables builds want.
300 Simulacrum Splinters make a Simulacrum, a wave encounter leading to the Delirium pinnacle boss.
0.5.5: *"The amount of maps the Delirium Fog spreads to from a Grand Mirror has been reduced to 10"*
and *"The number of Delirium Monster Packs no longer scales higher beyond 100% Deliriousness."*
0.5.5b: *"Increased the droprate of Expedition, Temple & Delirium Tablets."*

**Ritual.** Ritual Tablets add altars; killing revived monsters earns Tribute, spent on the altar's
offered rewards (rerollable, deferrable). Omens modify how other crafting currency behaves (e.g.
which side Chaos/Regal/Exalted Orbs act on), so omen prices track the crafting meta. Forbidden Rites
is a Ritual-themed league: every campaign area has a Ritual encounter, and party members earn their
own Tribute in 0.5.5.

**Expedition.** Core (not league-only) since 0.5.5: *"Expedition Tablets can now be found in
Standard and in the new Forbidden Rites League."* Tablets add expeditions to maps; Logbooks open
larger Grand Expeditions; Sagas modify Grand Expeditions. Artifacts are traded to the Expedition
NPCs for items. 0.5.5b: *"Fixed a bug where Expedition could not spawn naturally in Endgame."* and
raised the Expedition Tablet drop rate (see Delirium).

**Abyss.** Abyss Tablets add Abysses. 0.5.5: *"Large Abyssal Ravines can now appear throughout the
Atlas. Maps found on these ravine are guaranteed to contain Abysses."* — so Abyss can be targeted by
where you map. Bones desecrate rare items at the Well of Souls (jawbone → weapons/quivers, rib →
armour, collarbone → jewellery, cranium → jewels); their prices follow desecration crafting demand.

**Fragments (not researched).** `fragments` mixes several mechanics' keys: Breach and Simulacrum
splinters (above), An Audience with the King (Ritual), and items this research could not confirm —
Crisis Fragments, the Fates, Origin Spark / Core / Cradle, Azmeri Reliquary Key, Kulemak's
Invitation. The only verified line: *"Fixed a bug where the Bring Me Your Leader Atlas Passive was
not dropping Crisis Fragments in high level areas."* **Price these, don't explain them** — say the
mechanic isn't in this file.

## Decision principles (stable across patches)

- **A mechanic is worth farming for its outputs' value *and* depth.** A rising but thin output
  can't be sold at the quoted price.
- **Crafting-input prices follow the crafting meta** (catalysts, emotions, omens, bones): a new
  popular craft lifts one family and leaves the rest flat. Expect split movement within a category.
- **League phase matters.** Early in a league, outputs used for progression sell high and fall as
  supply catches up; late in a league (Forbidden Rites ends 2026-12-11), demand thins out.
- **Never claim a rate.** "Breach outputs are up and deep" is supportable; "Breach makes 3 div/hour"
  is not.
