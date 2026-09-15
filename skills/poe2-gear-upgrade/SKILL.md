---
name: poe2-gear-upgrade
description: Look at the player's Path of Exile 2 character and recommend gear upgrades ranked by value-per-currency, with trade filters to find them. Use when the player asks "how do I improve my gear" or "what should I upgrade next".
---
# poe2-gear-upgrade  (Phase 2)

Loads `poe2-core`. Finds weak slots vs. the build's needs (resist caps, life/ES, damage bottleneck),
then for each weak slot produces a realistic market upgrade ranked by value-per-currency, plus a trade
filter to find it. Iterates: the player pastes back search results and the skill refines the filter.

**Inputs:** the active character (OAuth) or a pasted PoB code; the player's currency (for price ceilings).
**Data:** rare search via `/trade2` adapter; affordability via `poe2-currency-tracker`.

TODO (Phase 2): stat-weakness analysis; trade-filter generation + refine loop.
