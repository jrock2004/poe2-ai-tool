---
name: poe2-vendor-regex
description: Build a Path of Exile 2 vendor search string that lights up the items worth buying for the player's current character and gear — the mods it's missing, on bases it can use. Use when the player asks for a "vendor regex", "what should I look for at the vendor", "a search string for vendors", or "I'm in act 3, what should I buy".
---
# poe2-vendor-regex

Load `poe2-core` first. One string the player pastes into a vendor's search box, so that only the items
worth buying for **this** character light up: the mods its current gear is missing, on bases the build
can use, with everything else hidden.

The string is built by `build_vendor_regex` from a curated, tested fragment table. **Never write or edit
regex fragments yourself** — a hand-written fragment miscounts characters and matches the wrong mods. If
the build needs a mod the tool doesn't list, say it isn't supported yet and leave it out.

Vendors sell for gold, so trade and SSF characters use this the same way.

## 1. Get the character, its gear, and what it's missing

- Resolve the character via `poe2-character` (active one, or a named override).
- Read its gear and targets exactly as `poe2-gear-upgrade` does in **"Get the character, its gear, and
  its *targets*"**, then rank the gaps as in **"Diagnose the weak slots"** — survivability first.
- Know the character's **level** (from the PoB, or ask). Vendor items carry a level requirement; when
  you explain the result, remind the player that anything above their level can't be worn yet.
- Ask for the vendor's **item level**: "hover any item at the vendor and tell me its *Item Level*."
  It decides which mod tiers the vendor can stock, so the string only asks for rolls that can appear.
  If the player doesn't know it, build the string without it and say so.

## 2. Turn the build into the tool's inputs

The tool description lists the valid keys. Map the build onto them:

- **`hide_classes`** — weapon and off-hand classes the build's skills can't use (from the PoB's gems or
  the guide). This is what keeps a minion build from lighting up maces and quivers.
- **`want_classes`** — a class worth buying on almost any roll, because the base itself is the upgrade
  (e.g. a sceptre for an early minion build). Usually empty.
- **The gate: `slot_classes` + `slot_defences`** — jewellery (`amulet`, `ring`, `belt`), the build's
  weapon class, and its defence type. **If the build's defence type isn't in the tool's list, omit the
  gate entirely** (no slot classes either — jewellery alone would hide every armour piece) and tell the
  player other defence types will light up too.
- **`want`** — the gaps from step 1, **most important first** (the tool drops from the end when the
  string is too long):
  - an uncapped resistance → `resistance`; low life or ES → `max_life` / `max_energy_shield` /
    `increased_energy_shield` for the build's defence;
  - boots without good movement speed → `movement_speed`; Spirit or minion levels for minion builds.
  - **`min_value`** (only for mods marked `(n)`): set it just above what the player already wears, so
    only real upgrades light up — boots with 15% movement speed → `min_value: 20`. Pass the vendor's
    **`item_level`** too.
  - **`any_base: true`** only for must-haves worth taking on any base the build can use (movement speed,
    +skill levels for the build's skills). Every `any_base` mod appears twice in the string, so use it
    sparingly.
- **Flasks and charms** — by default, want `charges_per_second` with `any_base: true` (that's how flasks
  and charms pass the gate) and put `flask_removes_recovery` in **`avoid`**: a flask that removes life or
  mana when used is never worth buying. **If the build's guide asks for different flask mods, follow the
  guide** and say so.
- **`avoid`** — mods that rule an item out whatever else it rolls. Avoided mods are never dropped.

## 3. Build it

Call `build_vendor_regex`. On `valid: false`, fix the input (the error names the bad key) and call
again — don't fall back to writing a string by hand. If `dropped` is not empty, tell the player which
wants didn't fit and offer a second string for them. If `unreachable` is not empty, tell the player
those rolls can't appear at these vendors yet (their item level is too low) — that's an answer, not a
failure: e.g. "30% movement speed boots don't show up at this vendor level, so I left them out".

## 4. Answer

- The string in its own code block, ready to copy.
- How to use it: at a vendor, click the search box at the bottom of their window (or press Ctrl+F),
  paste with Ctrl+V. Matching items are highlighted.
- One short line on what will light up and why ("boots with 20%+ movement speed, and resistances or ES
  on sceptres, jewellery and ES gear — your fire resistance is the gap").
- Before buying, check the item against what the player wears: a highlighted item can still be a
  downgrade if it drops a resistance or an attribute the build needs (`poe2-gear-upgrade`, **"Net-diff
  the swap"**).

## Confidence (per `poe2-core/references/confidence.md`)

- **High** — gear read from a PoB, build targets from a guide or the PoB, nothing dropped, defence gate
  used.
- **Medium** — gear from a screenshot or the player's description, some wants dropped, no defence
  gate (other defence types light up too), or no vendor item level.
- **Low** — the build or its gaps are guessed. Say what would raise it (a PoB code, or the guide link).

## Guardrails

- **Only the tool writes the string.** No hand-written fragments or edits.
- **Survivability before damage** in the `want` order, as in `poe2-gear-upgrade`.
- **One string, short explanation.** Offer a second string only for dropped wants.
- **Never buy, sell, or whisper.** The player shops; this only highlights.
