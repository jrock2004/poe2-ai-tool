# poe2-ai-tools

A personal **Path of Exile 2 decision assistant** that runs inside Claude. It helps with the
decisions that actually matter while playing: what to trade, whether a drop is an upgrade, how your
character stacks up against a build guide, what to pick in the Trials, and what's worth doing this
patch — with a stated confidence level on every answer.

> **Status:** all planned phases built; now in use-and-refine. See [`docs/plan.md`](docs/plan.md)
> for the full design and [Build phases](#build-phases) below for what was built when.

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
   │     poe2-trials-advisor, poe2-currency-tracker,
   │     poe2-meta-strategy
   │
   ├── MCP server ── the data plumbing
   │     poe2scout (reuse) + GGG /trade2 adapter + guide fetcher + PoB parser
   │
   └── Persistent state (Claude memory)
         your characters, currency inventory, active trade context
```

## Data sources & the reuse-vs-build decision

Findings from the Phase 0 spike (read from source, not guessed):

| Source | Use it for | Notes |
|---|---|---|
| **poe2scout** (`api.poe2scout.com`) | currency rates, unique-item prices, 7-day price history, net worth, market movers | **Reuse.** Its API is a price *reference* for currencies + uniques. **No rare-item-by-affix search** — the `/Items` route returns a flat priced list, no stat filters. |
| **GGG `/trade2`** (unofficial) | rare-gear search, trade-filter generation | **Build a thin adapter.** This is the only source that can search rares by mods. Unofficial + rate-limited → cache hard, read-only, never auto-buy. |
| **Path of Building** (export codes) | your character's and a guide's gear, gems, passive tree | **Build a parser.** Decodes a pasted PoB2 code offline; passive-tree names come from a committed snapshot of PoB2's tree data. |
| **Build guides** (Mobalytics/Maxroll/poe-vault) | build targets, leveling/endgame plans | Tiered: PoB code > static fetch > browser-assisted read > paste. poe-vault fetches; Mobalytics bot-blocks server fetches (browser/paste); Maxroll's license forbids automated/AI use, so it's refused (paste). |
| ~~GGG Character API~~ (OAuth) | your characters' gear/skills/passives | **Blocked** — GGG isn't issuing new API clients. Builds are read from PoB codes or screenshots instead. |
| ~~poe.ninja~~ | economy cross-check, build popularity | **Not integrated.** poe2scout covers prices; a meta-builds view would need a check of its undocumented API and terms first. |

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
| `poe2-meta-strategy` | What's rising/falling this week (in divine terms), sell/hold advice for your currency, and what to farm. |

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
- [x] **Phase 1** — `poe2-core` + `poe2-price-check` + `/trade2` trade-filter generation.
- [x] **Phase 2** — `poe2-character` + `poe2-gear-upgrade` + `poe2-currency-tracker`. *(OAuth character read is blocked — GGG isn't issuing API clients — so builds are read from PoB codes / screenshots; see `docs/plan.md` §3.)*
- [x] **Phase 3** — `fetch_guide` + `parse_pob_code` + `poe2-build-review` + `poe2-trials-advisor`.
- [x] **Hardening** — grounded confidence signals (price stats, freshness, 7-day trends), passive-tree parsing, client cache/rate-limit fixes + offline tests.
- [x] **Phase 4** — `market_movers` + `poe2-meta-strategy`.

## Setup (per machine)

Nothing is deployed anywhere: Claude Code starts the MCP server locally and loads the skills from
this folder. Two local files wire them up. They hold machine-specific paths, so they're
**git-ignored** — recreate them once per machine (a few minutes).

### Prerequisites

- **Claude Code** (desktop app or CLI), opened **in this repo's folder** — the skills only load there.
- **Git**, to clone the repo.
- **Python 3.10+.**
  - **Windows:** `winget install Python.Python.3.13`, or the installer from python.org — tick
    **"Add python.exe to PATH"**. Then use the `py` launcher, which avoids Windows' "python opens the
    Microsoft Store" alias. Check with `py --version`.
  - **macOS:** `brew install python`. Check with `python3 --version`.

### Run the setup script (from the repo root)

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```
**macOS / Linux:**
```bash
scripts/setup.sh
```

Add a league to override the default — `-League "Name"` on Windows, or as the first argument on
macOS/Linux. The script is safe to re-run. It:

1. installs the MCP server into `mcp/.venv` (editable, with the dev group — so pulled code changes
   apply without reinstalling);
2. writes `.mcp.json` with the absolute path to `poe2-mcp` — **only if it doesn't exist**, so your
   edits (like `POE2_LEAGUE`) are never overwritten;
3. links every skill into `.claude/skills` — directory junctions on Windows (no admin needed),
   symlinks elsewhere — so each skill still lives in one place under `skills/`;
4. checks the server imports.

It doesn't install Python; it checks for 3.10+ and tells you how if it's missing.
`-ExecutionPolicy Bypass` applies to that one run only and changes no system setting.

### Then

Open the folder in Claude Code, approve the `poe2` server when prompted, and the eight skills load
automatically. Re-run the script whenever a new skill folder is added. After pulling code changes,
restart the session so the MCP server reloads. Update `POE2_LEAGUE` in `.mcp.json` when the temp
league rotates.

## Repo layout

```
poe2-ai-tools/
├── README.md
├── docs/
│   └── plan.md            # full design doc
├── mcp/                   # the MCP server (data plumbing)
│   ├── README.md          # endpoints, source decisions, run notes
│   └── src/
├── scripts/               # per-machine setup: setup.ps1 (Windows), setup.sh (macOS/Linux)
└── skills/                # one folder per skill, each with a SKILL.md
    ├── poe2-core/
    │   └── references/    # confidence rubric, currency glossary, how-to
    ├── poe2-price-check/
    ├── poe2-character/
    ├── poe2-gear-upgrade/
    ├── poe2-build-review/
    ├── poe2-trials-advisor/
    ├── poe2-currency-tracker/
    └── poe2-meta-strategy/
```

## Tech choice

The MCP server is written in **Python** (first-class MCP SDK; and PoB-code parsing and guide-HTML parsing, both upcoming, are materially easier in Python). Ported from an initial TypeScript sketch.

## Disclaimers

Not affiliated with Grinding Gear Games. Uses third-party community data (poe2scout, poe.ninja) under
their terms, and the unofficial trade endpoint read-only and rate-limited. No automated trading.
