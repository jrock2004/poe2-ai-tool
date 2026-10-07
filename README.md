# poe2-ai-tools

A personal **Path of Exile 2 decision assistant** that runs inside Claude. It helps with the
decisions that actually matter while playing: what to trade, whether a drop is an upgrade, how your
character stacks up against a build guide, what to pick in the Trials, and what's worth doing this
patch — with a stated confidence level on every answer.

> **Status:** all planned phases built; now in use-and-refine. See [Build phases](#build-phases) below
> for what was built when, and [`docs/plan.md`](docs/plan.md) for the original design (historical).

---

## What it is (and isn't)

- **For:** one player (me), used conversationally inside Claude. Not a hosted product.
- **Two parts:** a thin **MCP server** that fetches live data, and a set of **skills** that hold the
  decision-making logic. Fetching data is a solved problem; the value is the judgment, so most of the
  work lives in the skills.
- **Not:** an auto-trader. It never buys, sells, or whispers on your behalf, and it never signs in to
  your account. It generates searches and advice; you act.
- **One exception to GGG's documented API:** live rare-item search uses the trade site's own search
  endpoints, which GGG doesn't document. GGG's developer docs say reverse-engineering undocumented
  endpoints is against its Terms of Use (section 7i). The calls are read-only, signed out, cached and
  rate-limited, but they aren't sanctioned. See [Data sources](#data-sources--the-reuse-vs-build-decision).

## Architecture

```
You (in Claude)
   │
   ├── Skills  ── the judgment + confidence
   │     poe2-core, poe2-price-check, poe2-character,
   │     poe2-gear-upgrade, poe2-crafting, poe2-vendor-regex,
   │     poe2-build-picker, poe2-build-review, poe2-build-switch,
   │     poe2-trials-advisor, poe2-currency-tracker,
   │     poe2-meta-strategy, poe2-new-league, poe2-whats-new
   │
   ├── MCP server ── the data plumbing
   │     poe2scout (reuse) + GGG /trade2 adapter + guide fetcher + PoB parser
   │     + vendor search-string builder + game-data snapshot (mod tiers)
   │
   └── Persistent state (saved by the MCP server, per user)
         your characters, currency inventory, league records, knowledge refreshes
```

## Data sources & the reuse-vs-build decision

Findings from the Phase 0 spike (read from source, not guessed):

| Source | Use it for | Notes |
|---|---|---|
| **poe2scout** (`api.poe2scout.com`) | currency rates, unique-item prices, 7-day price history, net worth, market movers | **Reuse.** Its API is a price *reference* for currencies + uniques. **No rare-item-by-affix search** — the `/Items` route returns a flat priced list, no stat filters. |
| **GGG `/trade2`** (undocumented) | rare-gear search, trade-filter generation | **Build a thin adapter.** This is the only source that can search rares by mods. It's the trade site's internal API, not part of GGG's documented one, and GGG's developer docs say using undocumented endpoints is against its Terms of Use (7i). Kept anyway, read-only: signed out, cached hard, rate limits honored, never auto-buy. |
| **Path of Building** (export codes, data files) | your character's and a guide's gear, gems, passive tree; the campaign's permanent rewards | **Build a parser.** Decodes a pasted PoB2 code offline; passive-tree names come from a committed snapshot of PoB2's tree data. The campaign's permanent rewards come from its quest-reward list (`campaign_rewards`), checked against the game data. |
| **Game-data export** ([repoe-fork/poe2](https://github.com/repoe-fork/poe2), [repoe-fork/dat-export](https://github.com/repoe-fork/dat-export)) | which mods a base can roll, and every tier's item-level gate (`mod_tiers`); what each currency, omen, essence or rune does, in the game's own words (`item_text`) | **Generate, don't research.** Exports of GGG's game files, fetched at pinned commits and turned into a per-patch snapshot (`CONTRIBUTING.md` step 9). The game files still carry PoE1 items, so PoE2's own Currency Exchange table picks which ones get text. |
| **Build guides** (Mobalytics/Maxroll/poe-vault) | build targets, leveling/endgame plans | Tiered: PoB code > static fetch > browser-assisted read > paste. poe-vault fetches; Mobalytics fetched too when checked (2026-10-07) but blocks some clients, so a blocked fetch goes to the browser (or paste); Maxroll's license forbids automated/AI use, so it's refused (paste). |
| ~~GGG Character API~~ (OAuth) | your characters' gear/skills/passives | **Blocked** — GGG isn't issuing new API clients. Builds are read from PoB codes or screenshots instead. |
| ~~poe.ninja~~ | economy cross-check, build popularity | **Not integrated.** poe2scout covers prices. Its API docs (checked 2026-10-07) make the economy endpoints the public surface and keep builds data internal, "not available for third-party use" — so the build picker gives you poe.ninja's builds link and never reads it. |

**No PoE2 stash API exists** (confirmed mid-2026), so currency tracking is done by reading
**screenshots** of your currency/crafting tabs into a remembered inventory.

## Skills

| Skill | Does |
|---|---|
| `poe2-core` | Shared game knowledge, the confidence rubric, and the "how do I get that?" how-to reference. Everything else builds on it. |
| `poe2-character` | Roster lifecycle: onboard a new character, list, update, set the active one. |
| `poe2-price-check` | Price an item or currency, with confidence. |
| `poe2-gear-upgrade` | Find your weak slots and rank realistic market upgrades by value-per-currency. |
| `poe2-crafting` | Say whether a crafting currency can get an item to your goal — and stop you wasting it when it can't. |
| `poe2-vendor-regex` | A vendor search string that lights up only the items your character is missing, on bases it can use. |
| `poe2-build-picker` | Help you choose a build: a shortlist of current guides from trusted creators that fit your playstyle, trade or SSF, and starting point. |
| `poe2-build-review` | Compare your character to a guide, stage-aware by your level. |
| `poe2-build-switch` | Say whether you're ready to move from a guide's leveling version to its endgame version, and what's in the way. |
| `poe2-trials-advisor` | Recommend picks in Trial of Sekhemas / Trial of Chaos for your build. |
| `poe2-currency-tracker` | Read currency-tab screenshots into a remembered inventory; answer "can I afford this?" |
| `poe2-meta-strategy` | What's rising/falling this week (in divine terms), sell/hold advice for your currency, and what to farm. |
| `poe2-new-league` | `/poe2:poe2-new-league` at league start: pick the league, save it as the default, refresh what the patch made stale, onboard the first character. |
| `poe2-whats-new` | For a returning player: what changed since they last played, and every patch-note line about their build, quoted from the official notes. |

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

## Install

It installs as a **Claude Code plugin**: the skills plus the local MCP server, in one step. It works in
the Claude Code CLI and in the Claude desktop app's **Code** tab (they share the same install).

### Prerequisites

- **Claude Code** — the CLI, or the desktop app's Code tab.
- **Git**, which Claude Code uses to fetch the plugin from GitHub.
  - **Windows:** `winget install --id Git.Git -e` (keep the installer defaults). GitHub Desktop's
    bundled Git doesn't count — it isn't on your PATH.
  - **macOS:** usually already there; if not, `xcode-select --install`.

  Check with `git --version`, in a new terminal after installing.
- **uv**, which runs the server and fetches Python for it if needed — no separate Python install.
  - **Windows:** `winget install --id=astral-sh.uv -e`
  - **macOS:** `brew install uv`

  Check with `uv --version`.

### Add the plugin (any terminal, once)

```bash
claude plugin marketplace add jrock2004/poe2-ai-tool
```
```bash
claude plugin install poe2@poe2-ai-tool
```

Then start (or restart) Claude Code, from any folder. The first start takes a few seconds longer while
uv sets up the server. On your first question, `poe2-character` onboards your character and saves your
league.

Plugin skills are namespaced, so their commands read `/poe2:<skill>` — e.g. `/poe2:poe2-new-league`, or
`/poe2:poe2-character new` for another character. Typing the bare name (`/poe2-new-league`) works too.

### Updates

Turn on auto-update once, and new versions arrive on their own:

- In a Claude Code terminal session, run `/plugin`, open **Marketplaces**, select **poe2-ai-tool**, and
  choose **Enable auto-update**.
- Or, in `~/.claude/settings.json` (on Windows, `.claude\settings.json` in your user folder), add
  `"autoUpdate": true` to the `poe2-ai-tool` entry under `extraKnownMarketplaces` — adding the
  marketplace created that entry.

Claude Code then checks in the background after your first message in a session; an update loads the
next time you start it, or straight away with `/reload-plugins`. Without auto-update, update by hand:

```bash
claude plugin update poe2@poe2-ai-tool
```

Updates bring new skills, fixes and refreshed game knowledge (trials, farming, crafting). Your own data
— characters, currency, saved league, any knowledge you refreshed — lives outside the install, so
updates never touch it. When a new league starts, run `/poe2:poe2-new-league`.

**Where your data lives:** `%APPDATA%\poe2-ai-tools` (Windows), `~/Library/Application Support/poe2-ai-tools`
(macOS), `~/.local/share/poe2-ai-tools` (Linux). Set `POE2_DATA_DIR` to move it.

## Development

Clone the repo, then build the dev venv for the tests — `scripts\setup.ps1` (Windows, via
`powershell -ExecutionPolicy Bypass -File scripts\setup.ps1`) or `scripts/setup.sh`. That needs
**Python 3.10+** (Windows: `winget install Python.Python.3.13`; macOS: `brew install python`).

To run your working copy in Claude Code, add the clone as a **local marketplace**; it loads in place, so
edits apply after a restart (CLI and desktop Code tab alike):

```bash
claude plugin marketplace add /path/to/poe2-ai-tools
```
```bash
claude plugin install poe2@poe2-ai-tool
```

If you used the pre-plugin setup, delete the old `.mcp.json` and `.claude/skills` in the clone first —
otherwise the server and skills load twice. Check the manifests with `claude plugin validate .`.

## Repo layout

```
poe2-ai-tools/
├── .claude-plugin/        # plugin.json (skills + MCP server) and marketplace.json
├── README.md
├── docs/
│   └── plan.md            # original design doc (historical)
├── mcp/                   # the MCP server (data plumbing)
│   ├── README.md          # modules, tools, trade2 notes, config
│   └── src/
├── scripts/               # dev setup (test venv): setup.ps1 (Windows), setup.sh (macOS/Linux)
└── skills/                # one folder per skill, each with a SKILL.md
    ├── poe2-core/
    │   └── references/    # confidence rubric, currency glossary, how-to
    ├── poe2-price-check/
    ├── poe2-character/
    ├── poe2-gear-upgrade/
    ├── poe2-crafting/
    ├── poe2-vendor-regex/
    ├── poe2-build-picker/
    ├── poe2-build-review/
    ├── poe2-build-switch/
    ├── poe2-trials-advisor/
    ├── poe2-currency-tracker/
    ├── poe2-meta-strategy/
    ├── poe2-new-league/
    └── poe2-whats-new/
```

## Tech choice

The MCP server is written in **Python** (first-class MCP SDK; PoB-code parsing and guide-HTML parsing are materially easier in Python). Ported from an initial TypeScript sketch.

## Contributing

Market data is live, but a few files describe the game itself and go stale each patch (passive-tree
snapshot, trials and farming knowledge, how-to steps). [`CONTRIBUTING.md`](CONTRIBUTING.md) has the
per-patch refresh checklist and the ground rules for changes.

## License & notices

This project's code is MIT-licensed — see [`LICENSE`](LICENSE).

**Third-party data.** `mcp/src/poe2_mcp/data/tree_*.json` is derived from the passive-tree data in
[Path of Building Community (PoE2)](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2)
(`src/TreeData/<version>/tree.lua`), used under its MIT License: Copyright (c) 2016 David Gowor.
`mcp/src/poe2_mcp/data/stash_layouts_*.json` is derived from
[repoe-fork/dat-export](https://github.com/repoe-fork/dat-export), an export of the game's data files
that states no license. `mcp/src/poe2_mcp/data/items_*.json` is generated from
[repoe-fork/poe2](https://github.com/repoe-fork/poe2), a processed export of the game's data files that
also states no license, and from dat-export's Currency Exchange table; the
[RePoE](https://github.com/repoe-fork/repoe) tooling that produces repoe-fork/poe2 is MIT-licensed. The
underlying game data belongs to Grinding Gear Games.

**Not affiliated with Grinding Gear Games.** Path of Exile is a trademark of Grinding Gear Games;
this project is not endorsed by or affiliated with GGG. It reads community price data (poe2scout)
under its terms, and the trade site's undocumented search endpoint read-only and rate-limited (see
[Data sources](#data-sources--the-reuse-vs-build-decision)). No automated trading.
