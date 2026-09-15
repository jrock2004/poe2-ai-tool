---
name: poe2-currency-tracker
description: Track the player's Path of Exile 2 currency by reading screenshots of their currency/crafting tabs into a remembered inventory, and answer affordability questions. Use when the player shares a currency-tab screenshot or asks "what can I afford" or "what's my net worth".
---
# poe2-currency-tracker  (Phase 2)

Loads `poe2-core`. Reads screenshots of currency/crafting tabs (vision) into a structured, remembered
inventory — because there is **no PoE2 stash API**. Confirms parsed counts with the player before
saving. Answers affordability and net-worth (valued via poe2scout rates), and feeds price ceilings to
trade filters.

**Confirm-before-save:** show parsed counts ("Exalted x342, Divine x11 …") and let the player correct.
**Multi-tab:** each screenshot maps to a named tab; re-sending a tab replaces it (no double-count).
**Currency is league-scoped**, shared across characters in that league.

TODO (Phase 2): screenshot parse; per-tab merge; net-worth via poe2scout; confirm-before-save UX.
