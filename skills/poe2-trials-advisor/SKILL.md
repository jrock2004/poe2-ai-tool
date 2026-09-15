---
name: poe2-trials-advisor
description: Advise which relics, boons, afflictions, or rewards to pick in the Path of Exile 2 Trial of the Sekhemas or Trial of Chaos, based on the player's build. Use when the player asks what to select, take, or avoid in a Trial.
---
# poe2-trials-advisor

Load `poe2-core` first, then read `references/trials-knowledge.md` before advising. The recommendation
is only as current as that file, which is **patch-dependent** — so its freshness stamp feeds directly
into your confidence (see below).

The job: given **this build's** defensive layers and damage profile, say what to **take** and what to
**avoid** in the two Ascendancy trials — with the reasoning, not just a pick.

## 1. Get the build context (what the advice hinges on)

Resolve the active character via `poe2-character`. What matters for trials:

- **How it survives** — armour/evasion/ES stacking (a *tank*), or block/dodge/ranged (*avoidance*);
  whether it leans on **resistance caps**, **regen/leech**, or **not getting hit**.
- **Damage profile** — AoE/projectile clear vs melee/strike single-target; whether it has damage to
  spare or fights already drag.
- **Chaos resistance / EHP** and any known weak layer.

If you don't have this, ask one or two quick questions (or read a character screenshot). Vague context
→ lower confidence, and say what would sharpen it.

## 2. Match picks to the build (per `references/trials-knowledge.md`)

- **Trial of the Sekhemas (honour):** honour is lost on being hit, so a build that gets hit is
  honour-bottlenecked. Recommend **Maximum Honour + Honour Resistance relics** and defensive boons for
  those; throughput relics for high-avoidance builds. Route *around* afflictions that drain honour or
  cut the build's defence; decline duplicates.
- **Trial of Chaos (tribulations):** each round, pick the affliction the build **barely notices** and
  avoid the one that hits a layer it depends on (use the affliction→weakness table in the knowledge
  file). Because you can **bank loot and leave after any round**, advise pushing while the picks are
  safe and **leaving with the loot** once every remaining option hits a real weakness — don't gamble a
  full run.

Always give the *why* tied to their build: "take **Resistant Monsters** — it only taxes your damage and
you have plenty; avoid **Reduced Resistances**, you're a res-capped armour build and −max res is your
death." Name the specific pick and the specific reason.

## 3. Confidence (per `poe2-core/references/confidence.md`)

Two signals dominate here:
- **Knowledge recency** — the knowledge file is stamped as of a date/patch. If it may be stale, or the
  player quotes affliction wording that doesn't match it, **trust the game, lower confidence**, and say
  "verify the exact wording in-game; the pools shift by patch."
- **Build-context certainty** — a clear build read scores higher than a guessed one.

Never present a trial pick as certain when the underlying pool might have changed. A wrong "safe" call
here can end a run.

## Guardrails

- **Ground every pick in the knowledge file + the build**, not from memory of a past patch. If the file
  doesn't cover something the player sees, say so and reason from the mechanics rather than inventing a
  specific effect.
- Keep the knowledge file current — it's part of the patch-churn maintenance (plan §10).
- Plain language first for newer players (define "honour", "affliction", "max res") per `poe2-core`.
