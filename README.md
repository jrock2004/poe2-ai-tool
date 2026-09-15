# poe2-ai-tools

A personal **Path of Exile 2 decision assistant** that runs inside Claude. It helps with the
decisions that actually matter while playing: what to trade, whether a drop is an upgrade, how your
character stacks up against a build guide, what to pick in the Trials, and what's worth doing this
patch — with a stated confidence level on every answer.

> **Status:** early build. See [`docs/plan.md`](docs/plan.md) for the full design and
> [Build phases](#build-phases) below for what's done vs. pending.

---

## What it is (and isn't)

- **For:** one player (me), used conversationally inside Claude. Not a hosted product.
- **Two parts:** a thin **MCP server** that fetches live data, and a set of **skills** that hold the
  decision-making logic. Fetching data is a solved problem; the value is the judgment, so most of the
  work lives in the skills.
- **Not:** an auto-trader. It never buys, sells, or whispers on your behalf. It generates searches and
  advice; you act. This keeps your account safe and stays on the right side of GGG's rules.

## Architecture

```
You (in Claude)
   │
   ├── Skills  ── the judgment + confidence
   │     poe2-core, poe2-price-check, poe2-character,
   │     poe2-gear-upgrade, poe2-build-review,
   │     poe2-trials-advisor, poe2-currency-tracker
   │
   ├── MCP server ── the data plumbing
   │     poe2scout (reuse) + GGG /trade2 adapter (build) + poe.ninja fallback
   │
   └── Persistent state (Claude memory)
         your characters, currency inventory, active trade context
```

## Data sources & the reuse-vs-build decision

Findings from the Phase 0 spike (read from source, not guessed):

| Source | Use it for | Notes |
|---|---|---|
| **poe2scout** (`api.poe2scout.com`) | currency rates, unique-item prices, price history, net worth | **Reuse.** Its API is a price *reference* for currencies + uniques. **No rare-item-by-affix search** — the `/Items` route returns a flat priced list, no stat filters. |
| **GGG `/trade2`** (unofficial) | rare-gear search, trade-filter generation | **Build a thin adapter.** This is the only source that can search rares by mods. Unofficial + rate-limited → cache hard, read-only, never auto-buy. |
| **poe.ninja** (poe2 economy) | economy overview, cross-check | No auth; respect ~5 min cache + descriptive User-Agent. |
| **GGG Character API** (OAuth, `poe2` realm) | your characters' gear/skills/passives | Official. Powers gear analysis without pasting PoB. |
| **Build guides** (Mobalytics/Maxroll/poe-vault) | build targets, leveling/endgame plans | Tiered: PoB code > static fetch > browser-assisted read > paste. Maxroll is robots-blocked to plain fetch. |

**No PoE2 stash API exists** (confirmed mid-2026), so currency tracking is done by reading
**screenshots** of your currency/crafting tabs into a remembered inventory.

## Skills

| Skill | Does |
|---|---|
| `poe2-core` | Shared game knowledge, the confidence rubric, and the "how do I get that?" how-to reference. Everything else builds on it. |
| `poe2-character` | Roster lifecycle: onboard a new character, list, update, set the active one. |
| `poe2-price-check` | Price an item or currency, with confidence. |
| `poe2-gear-upgrade` | Find your weak slots and rank realistic market upgrades by value-per-currency. |
| `poe2-build-review` | Compare your character to a guide, stage-aware by your level. |
| `poe2-trials-advisor` | Recommend picks in Trial of Sekhemas / Trial of Chaos for your build. |
| `poe2-currency-tracker` | Read currency-tab screenshots into a remembered inventory; answer "can I afford this?" |

Design notes that shape all of them:

- **Confidence is grounded, not vibes.** Every answer carries High/Medium/Low + a one-line why
  ("Medium — only 3 listings, prices ranged 2×"), computed from data freshness, sample size, and how
  certain the inputs are.
- **Beginner-friendly by default.** Plain language first, one-line "how to get this" hints on every
  ask, full step-by-step whenever you ask "how?", and verbosity that tunes to your experience level.
- **Guides are staged.** A guide is modeled as an ordered set of level/act stages with variant links
  (leveling → endgame), so the tool shows you the stage that matches your character's current level.

## Build phases

- [x] **Phase 0** — Reuse-vs-build decision + guide-fetch spike. *(done; see the table above)*
- [ ] **Phase 1** — `poe2-core` + `poe2-price-check` + trade-filter generation.
- [ ] **Phase 2** — GGG OAuth character read + `poe2-character` (roster/onboarding) + `poe2-gear-upgrade` + `poe2-currency-tracker`.
- [ ] **Phase 3** — Guide ingestion + `poe2-build-review` + `poe2-trials-advisor`.
- [ ] **Phase 4** — Custom MCP consolidation + `poe2-meta-strategy`.

## Repo layout

```
poe2-ai-tools/
├── README.md
├── docs/
│   └── plan.md            # full design doc
├── mcp/                   # the MCP server (data plumbing)
│   ├── README.md          # endpoints, source decisions, run notes
│   └── src/
└── skills/                # one folder per skill, each with a SKILL.md
    ├── poe2-core/
    │   └── references/    # confidence rubric, currency glossary, how-to
    ├── poe2-price-check/
    ├── poe2-character/
    ├── poe2-gear-upgrade/
    ├── poe2-build-review/
    ├── poe2-trials-advisor/
    └── poe2-currency-tracker/
```

## Tech choice

The MCP server is written in **Python** (first-class MCP SDK; and PoB-code parsing and guide-HTML parsing, both upcoming, are materially easier in Python). Ported from an initial TypeScript sketch.

## Disclaimers

Not affiliated with Grinding Gear Games. Uses third-party community data (poe2scout, poe.ninja) under
their terms, and the unofficial trade endpoint read-only and rate-limited. No automated trading.
