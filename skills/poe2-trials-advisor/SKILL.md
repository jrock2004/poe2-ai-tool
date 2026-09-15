---
name: poe2-trials-advisor
description: Advise which relics, boons, or rewards to pick in the Path of Exile 2 Trial of Sekhemas or Trial of Chaos, based on the player's build. Use when the player asks what to select in a Trial.
---
# poe2-trials-advisor  (Phase 3)

Loads `poe2-core`. Given the active build context, recommends picks in Trial of Sekhemas / Trial of
Chaos (e.g. "take honour-resistance, your build is honour-fragile"; "avoid -max-res, you're at a
defensive floor"). Ties into guide milestone hooks.

**Needs a maintained knowledge file** of the boon/affliction/reward/relic pools — contents shift by
patch (see plan §10 maintenance).

TODO (Phase 3): author trials knowledge file; build-aware recommendation logic.
