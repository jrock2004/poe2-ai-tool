---
name: poe2-price-check
description: Price a Path of Exile 2 item or currency and say what it's realistically worth, with a confidence level. Use when the player pastes an item, asks "what's this worth", or asks about currency exchange rates.
---
# poe2-price-check  (Phase 1)

Loads `poe2-core`. Given a pasted item, a currency, or a description, returns a fair price range and a
list/snipe recommendation, with confidence.

**Inputs:** pasted item text (Ctrl+C in game), a currency name, or a plain description.
**Data:** currencies/uniques → poe2scout; rare items → the `/trade2` adapter (see `mcp/README.md`).
**Output:** price range, confidence band + reason, and (for rares) a ready trade filter (see F6).
**Beginner note:** if they don't know how to copy an item, point to `poe2-core/references/how-to.md`.

TODO (Phase 1): wire poe2scout currency/unique pricing; handle "no listings" by widening the search;
implement the trade-filter output.
