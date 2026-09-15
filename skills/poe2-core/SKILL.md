---
name: poe2-core
description: Shared foundation for all Path of Exile 2 assistant skills — game vocabulary, the grounded confidence rubric, and the beginner-friendly how-to reference. Load this whenever another poe2-* skill runs.
---

# poe2-core

The shared base every other `poe2-*` skill relies on. It is not used directly by the player; it is
loaded by the other skills so they all speak the same language, score confidence the same way, and
explain things to newcomers consistently.

## What lives here

- **`references/confidence.md`** — the grounded confidence rubric. Every answer any skill gives ends
  with a confidence band and a one-line reason. Read it before producing any recommendation.
- **`references/currency-glossary.md`** — currency names, common shorthand, and how prices are quoted
  (in exalted vs. divine). Used to normalize what the player types.
- **`references/how-to.md`** — step-by-step "how do I get that for you?" instructions (export a PoB
  code, copy an item in game, screenshot a currency tab, connect OAuth, find a build guide).

## Rules every skill inherits

1. **State confidence on every answer.** Use `references/confidence.md`. Never invent a percentage;
   derive a High/Medium/Low band from observable signals.
2. **Beginner-friendly by default.** Plain language before jargon; define a term the first time it is
   used. Attach a one-line "how to get this" hint to any request for data. If the player asks "how?"
   or "what's that?", answer from `references/how-to.md`. Tune verbosity to the player's stored
   experience level; they can change it any time.
3. **Never auto-trade.** Skills generate searches, prices, and advice. They never buy, sell, or
   whisper. Trade output is a filter set or a link the player uses themselves.
4. **Cite freshness.** When using market data, note how old it is; stale data lowers confidence.

## Player & character state (shared model)

Skills read and write a small persistent state (in Claude memory):

- **characters[]** — each with name, class/ascendancy, build archetype, goal, guide link, and an
  `active` flag. Currency is **league-scoped**, shared across all characters in a league.
- **currency inventory** — per league, populated from screenshots (see `poe2-currency-tracker`).
- **active trade context** — the last search + results, for the iterative trade-filter loop.

See `docs/plan.md` in the repo root for the full design.
