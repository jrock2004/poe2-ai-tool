---
name: poe2-build-review
description: Compare the player's Path of Exile 2 character to a build guide and produce a stage-aware, prioritized fix list. Use when the player wants to know how their skills/gear stack up against a guide they're following.
---
# poe2-build-review  (Phase 3)

Loads `poe2-core`. Pulls the character, ingests a guide (see `mcp` fetch_guide tiers), figures out
which guide stage matches the character's level, and produces a diff: what's missing for *this* stage,
what's off-spec, priority-ordered. Separates "deviated from the plan" from "just behind on gearing".

**Guide model:** ordered level/act stages + variant links (leveling → endgame) + Trial milestone hooks.
**Data:** guide via PoB code > static fetch > browser read > paste. Maxroll is robots-blocked to fetch.

TODO (Phase 3): guide parser into the staged model; level-based stage selection; diff engine.
