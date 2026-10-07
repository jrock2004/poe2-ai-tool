---
name: poe2-trials-advisor
description: Advise which relics, boons, afflictions, or rewards to pick in the Path of Exile 2 Trial of the Sekhemas or Trial of Chaos, based on the player's build. Use when the player asks what to select, take, or avoid in a Trial.
---
# poe2-trials-advisor

Load `poe2-core` first, then call `get_knowledge('trials')` before advising — it holds how the trials
work and how to choose. What a trial can offer, in its exact text, comes from `trial_pool`. Both are
**patch-dependent**, so their freshness feeds directly into your confidence (see below).

The job: given **this build's** defensive layers and damage profile, say what to **take** and what to
**avoid** in the two Ascendancy trials — with the reasoning, not just a pick.

## 1. Get the build context (what the advice hinges on)

Resolve the active character via `poe2-character`. What matters for trials:

- **How it survives** — armour/evasion/ES stacking (a *tank*), or block/dodge/ranged (*avoidance*);
  whether it leans on **resistance caps**, **regen/leech**, or **not getting hit**.
- **Damage profile** — AoE/projectile clear vs melee/strike single-target; whether it has damage to
  spare or fights already drag.
- **Chaos resistance / EHP** and any known weak layer.

If you don't have this, read their PoB code from a character import (it gives the defences directly)
or a character screenshot, or ask one or two quick questions. Vague context → lower confidence, and
say what would sharpen it.

## 2. Look up what's on offer (`trial_pool`)

For each modifier, affliction, boon or pledge the player is choosing between, get its exact text from
the game data: `trial_pool('chaos', '<name>')` or `trial_pool('sekhemas', '<name>')` — part of a name
or text, any case; a kind or category (`'hazard'`, `'wager'`, `'pledges'`) lists all of them.

- **Quote the text; don't paraphrase it.** For a Trial of Chaos modifier, match the version on the
  offer (the roman numeral in its name) and give its `tier`, 1–5 — higher is harder.
- **A text or `cost` with `{0}`** (or `{1}`) gets its number in the game, and the data doesn't show
  it: quote it with the placeholder as-is and **never state a number for it** — not even one from
  `values`, which isn't confirmed to match. If the number decides the pick, ask the player to read it
  off the tooltip.
- **One name, several entries** (Death Toll is two different afflictions; Assassin's Blade comes in
  several counts): use the one whose text matches what the player sees, or ask.
- **No match** returns `suggestions` — try them. If nothing fits, say the data doesn't have it, work
  from the player's wording and the mechanics, and lower confidence.

## 3. Match picks to the build (per `get_knowledge('trials')`)

- **Trial of the Sekhemas (honour):** honour is lost on being hit, so a build that gets hit is
  honour-bottlenecked. Recommend **Maximum Honour + Honour Resistance relics** and defensive boons for
  those; throughput relics for high-avoidance builds. Route *around* afflictions that drain honour or
  cut the build's defence; decline duplicates.
- **Trial of Chaos (tribulations):** each round, pick the modifier the build **barely notices** and
  avoid the one that hits a layer it depends on (use the "Hits builds that…" list in the knowledge
  file). Because you can **bank loot and leave after any round**, advise pushing while the picks are
  safe and **leaving with the loot** once every remaining option hits a real weakness — don't gamble a
  full run.

Always give the *why* tied to their build: "take **Resistant Monsters** — it only taxes your damage and
you have plenty; avoid **Reduced Resistances**, you're a res-capped armour build and −max res is your
death." Name the specific pick and the specific reason.

## 4. Confidence (per `poe2-core/references/confidence.md`)

Two signals dominate here:
- **Knowledge recency** — the knowledge file is stamped with a date and patch, and `trial_pool` returns
  the `patch` its data is from. If either is older than the live patch, or the player quotes wording
  that doesn't match `trial_pool`'s text, **trust the game, lower confidence**, and say "verify the
  exact wording in-game; the pools shift by patch."
- **Build-context certainty** — a clear build read scores higher than a guessed one.

Never present a trial pick as certain when the underlying pool might have changed. A wrong "safe" call
here can end a run.

## Guardrails

- **Ground every pick in `trial_pool`'s text, the knowledge file and the build**, not from memory of a
  past patch. If they don't cover something the player sees, say so and reason from the mechanics
  rather than inventing a specific effect.
- Keep the knowledge file current — it's part of the per-patch refresh (`CONTRIBUTING.md` step 2).
- Plain language first for newer players (define "honour", "affliction", "max res") per `poe2-core`.
