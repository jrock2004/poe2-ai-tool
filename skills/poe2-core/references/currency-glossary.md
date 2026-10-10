# Currency glossary

Normalize what the player types into a currency the tools can price. **Do not hard-code prices** —
they move constantly; fetch them with `get_currency_prices(category, search)`. This file is about
*names, shorthand, and how prices are quoted*, which are stable.

## How prices are quoted (PoE2, not PoE1)

- **The base unit is the Exalted Orb**, not Chaos. In PoE2 the economy is denominated in **exalted**
  (ex); high-value things are quoted in **divine** (div). `get_currency_prices` returns both.
  A PoE1 player will assume a chaos base — say "exalted-based" the first time it matters.
- Rule of thumb: cheap things in exalted, expensive things in divine. The league's `DivinePrice` is
  "exalted per divine" (~450 ex/div at time of writing), which is how the tools convert between them.
- Chaos Orb exists but is a crafting orb here, not the base trade unit.

## Reading a search back

`get_currency_prices` searches poe2scout's **display name** (the `Text`, e.g. "Divine Orb"), so
normalize a shorthand to its canonical name before searching (`div` → search "Divine"). The `apiId`
column is poe2scout's stable id for that currency (handy for exact identification / dedup).

## Common shorthand → canonical name (category `currency`)

| Player types | Canonical name | apiId | Role |
|---|---|---|---|
| ex, exalt, exalts | Exalted Orb | `exalted` | **base unit**; add a mod to a rare |
| div, divine, d | Divine Orb | `divine` | high-value unit; reroll mod values |
| chaos, c | Chaos Orb | `chaos` | remove+add a mod on a rare |
| annul, ann | Orb of Annulment | `annul` | remove a random mod |
| regal | Regal Orb | `regal` | magic → rare |
| alch, alchemy | Orb of Alchemy | `alch` | normal → rare |
| aug, augment | Orb of Augmentation | `aug` | add a mod to a magic item |
| transmute, trans | Orb of Transmutation | `transmute` | normal → magic |
| chance | Orb of Chance | `chance` | normal → random rarity |
| vaal | Vaal Orb | `vaal` | corrupt (unpredictable) |
| gcp | Gemcutter's Prism | `gcp` | gem quality |
| whetstone, whet | Blacksmith's Whetstone | `whetstone` | martial weapon quality |
| scrap | Armourer's Scrap | `scrap` | armour quality |
| bauble | Glassblower's Bauble | `bauble` | flask quality |
| mirror | Mirror of Kalandra | `mirror` | duplicate an item (chase) |
| fracture, frac | Fracturing Orb | `fracturing-orb` | fracture a mod (chase) |
| wisdom, wis | Scroll of Wisdom | `wisdom` | identify |

Not exhaustive — the full priced list (38+ in `currency` alone) is runtime-discoverable. If a name
isn't here, search it directly or fall back to `price_unique`.

## Tiered orbs (new in PoE2)

Several orbs come in **Lesser / (base) / Greater / Perfect** tiers — e.g. Jeweller's Orbs exist only
as `lesser-jewellers-orb`, `greater-jewellers-orb`, `perfect-jewellers-orb`; Exalted/Regal/Chaos/
Transmutation/Augmentation each have `greater-*` and `perfect-*` variants. Higher tier = stronger
effect and higher price. When a player says "greater ex" or "perfect regal", match the tier prefix.

The tiers are not a pattern to extend: not every item has every tier (there is a Greater Tempered
Rune but no Perfect one). An item exists when `item_text` or a price tool returns it, not because its
siblings do.

## Socketables: runes, soul cores, idols, ancient augments

Everything that goes in a socket is kept in the **Runes** stash tab, which has five pages. A player
who has only ever seen one page can take a name from another for a made-up item, so when you name a
socketable, say its kind and where it's found: *"Perfect Iron Rune (top tier of the Iron Rune, level
50; on the Currency Exchange under Perfect Runes)"*.

`get_stash_layout("socketable")` says which page holds an item (`subTab`, counted from 0):

| `subTab` | Page | Names look like |
|---|---|---|
| 0 | General runes | Lesser / (base) / Greater Iron, Desert, Body… Rune; Greater Rune of …; *Name*'s Rune of … |
| 1 | Kalguuran Runes (the page's in-game tooltip) | Warding Rune of …, Ancient Rune of …, Rune of …, … of Aldur, Masterwork Rune |
| 2 | Soul cores | Soul Core of …, *Name*'s Soul Core of … |
| 3 | Idols | *Animal* Idol, Idol of … |
| 4 | Ancient augments | *Name*'s Gaze, *Name*'s Thesis, Emergent …, Carved …, Raven-Touched Shard |

An **Ancient Rune** of … is a Kalguuran rune; it isn't an ancient augment, despite the name.

**Perfect runes** (the top tier of the general runes) have no slot in the tab's layout data. The
Currency Exchange lists them under its own heading, **Perfect Runes**, next to Runes and Greater
Runes. Point the player there.

## Other categories (pick the right `category`)

`get_currency_prices` is per-category. Beyond `currency`, poe2scout exposes: `fragments`, `runes`,
`essences`, `ultimatum`, `expedition`, `ritual`, `vaultkeys`, `breach`, `abyss`, `uncutgems`,
`lineagesupportgems`, `delirium`, `incursion`, `idol`, `verisium`, `vaal`. If the player asks about
an essence or a rune, query that category, not `currency`.
