---
name: poe2-character
description: Manage the player's Path of Exile 2 character roster — onboard a new character, list characters, update a build, and set which one is active. Use when the player starts a new character, switches characters, or first uses the assistant.
---
# poe2-character  (Phase 2)

Loads `poe2-core`. Owns the whole roster lifecycle in one skill (create / list / update / set active).
Switching the active character is a state update here, not a separate skill; per-request overrides
("check my minion build's boots") are also handled.

**First-run onboarding:** interview one question at a time — which character, class/build, goal
(bossing/mapping/league-start), following a guide?, OAuth-connect or paste PoB? — and gauge experience
level. Write each answer to state as it comes in.
**State:** characters[] with an `active` flag; currency is league-scoped (see poe2-core model).

TODO (Phase 2): implement onboarding flow; OAuth character import; experience-level flag.
