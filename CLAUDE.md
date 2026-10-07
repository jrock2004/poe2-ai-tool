# Working agreement

## Hard rules

- **Never run `git commit`, `git push`, or anything that rewrites history.** Stage nothing
  unless asked. John reviews everything before it is committed.
- **Never add a `Co-Authored-By` trailer or any AI attribution** to commits or PR text.
- **Act as a senior engineer.** Do not assume John's assumptions are right. If a request is
  the wrong move, say so and explain why before doing it.
- **Before touching more than ~3 files, or adding a dependency, stop and ask.**
  This counts **cumulatively across a chain of approvals**, not per step. A sequence of
  small approved follow-ups that together cross the limit still has to stop and re-ask —
  an approval for one step is not an approval for the scope it grew into.

## How work is split

John owns the design:

- interfaces, types, and function signatures
- module boundaries
- the core tricky logic, when he chooses to take it
- the tests that define correctness — written or approved **before** implementation
  (if a slice starts without them, call it out)

Claude implements: the body of the agreed signatures, fixtures, and plumbing.

## How work is sized

Each change must be reviewable in a few minutes. If a step would be bigger than that,
stop and propose how to split it before writing code.

After each step, state briefly what to look for in review.

## How work is reviewed

John reviews in Neovim, never in a chat window. The loop, per slice:

1. **Per change** — read it as a diff in `claudecode.nvim`, while the context is small enough
   to actually reason about.
2. **Whole change** — before committing, read the full diff in `diffview.nvim` or `lazygit`.
3. **John commits.** Claude never does.

What this means for Claude: leave the work in the tree, unstaged, and stop. Do not summarize a
change *instead of* leaving it reviewable — the diff is the artifact, the summary is a pointer
to it. Say what to look for and where; don't restate the diff in prose.

When a slice is ready, hand over the commit as **separate blocks** — `git add <files>` in one,
`git commit -m '...'` in another — with a **single-quoted** message.

This loop is for **development work** on the repo. Files a `poe2-*` skill writes while running for the
player (e.g. `/poe2-new-league` refreshing knowledge files) are not a slice: no review handoff, no `git`
commands. They become one only when John asks for them to be reviewed as a change.

## Project

Personal Path of Exile 2 decision assistant. Two parts:

- `mcp/` — Python MCP server (official `mcp` SDK, pinned `<2`; `httpx`; `beautifulsoup4`).
  Data plumbing, plus storage for the player's own data — no judgment.
  - `store.py` / `state.py` / `knowledge.py` — the per-user data dir (outside the install, survives
    updates): saved league, roster/currency state (JSON merge patch), and local knowledge refreshes.
  - `_cache.py` — every network result is a `Fetched(body, fetched_at)`; tools report freshness
    (`fetchedAt`/`ageSeconds`, oldest input wins) from it.
  - `treedata.py` + `data/tree_<version>.json` — the passive-tree name snapshot. The JSON is
    **generated, never hand-edited**: regenerate it with `python -m poe2_mcp.treedata` (see
    `CONTRIBUTING.md`).
  - `stashlayout.py` + `data/stash_layouts_<version>.json` — which item sits in each special stash-tab
    slot, served by `get_stash_layout` so the currency tracker names items from their slot. Also
    **generated, never hand-edited**: `python -m poe2_mcp.stashlayout` (see `CONTRIBUTING.md`).
  - `gamedata.py` + `data/items_<patch>.json` — mod tiers, item text and both trial pools, from
    repoe-fork's exports at pinned commits, served by `mod_tiers`, `item_text`, `trial_pool` and the
    vendor regex's tiers. Also **generated, never hand-edited**: `python -m poe2_mcp.gamedata items …`
    (see `CONTRIBUTING.md`).
  - `campaign.py` + `data/campaign_<version>.json` — the campaign's permanent rewards, from PoB2's
    `QuestRewards.lua`, served by `campaign_rewards`. Also **generated, never hand-edited**:
    `python -m poe2_mcp.campaign` (see `CONTRIBUTING.md`).
- `skills/` — one folder per skill (fourteen). The judgment lives here, not in the server.
- `scripts/` — dev setup (the test venv): `setup.ps1` (Windows) and `setup.sh` (macOS/Linux).
- `.claude-plugin/` — `plugin.json` (skills + the server, run via `uv`) and `marketplace.json`. Players
  install the repo as a plugin; it is not deployed anywhere else.

Design rules that hold across both:

- **Read-only toward GGG.** Never buy, list, or whisper. Generate searches and advice; John acts.
- **Pure core, thin edges.** Query construction (`build_query`), PoB parsing, and scoring are
  pure and unit-tested. Network calls live only in the client modules — `trade2`, `poe2scout`,
  `guides`, `exchange` — and are cached (the `gamedata` generator also fetches, at build time only).
  Note that `find_stat_filters` *does* hit the network on a cold
  cache (`trade2._stats` fetches `/data/stats`, cached 6h); "offline" in this repo usually means
  "cached," not "never calls out."
- **Every answer carries a grounded confidence level** (see `skills/poe2-core/references/confidence.md`).
  Tools return the signals as fields (`priceStats`, `ageSeconds`, `quantityListed`, `trend`);
  skills score from those fields. The thresholds live **only** in `confidence.md` — skills point
  to it, never restate numbers.
- **Judge market moves in divine, not exalted.** Prices are quoted in exalted, so when exalted
  drifts every raw change moves together. Trends and movers use `changePctVsDivine`.
- **Source rules** (where to look things up, what to avoid, trusted build creators) live **only** in
  `skills/poe2-core/references/sources.md`. **The per-patch refresh** (tree snapshot, stash layouts,
  trials/farming knowledge, how-tos, league) lives in `CONTRIBUTING.md`. Follow them; don't duplicate
  them here.

## Platforms

John plays on **Windows**; development also happens on macOS.

- Keep `scripts/setup.ps1` and `scripts/setup.sh` doing the same thing — change both together.
- Code must run on **Python 3.10** (`requires-python >=3.10`) — e.g. `Traversable.joinpath` takes
  one argument there.
- Write files with an explicit `encoding="utf-8", newline="\n"`; don't rely on shell redirects
  (Windows PowerShell's `>` writes UTF-16).

## Tests

```bash
cd mcp && .venv/bin/python -m pytest -q        # Windows: .venv\Scripts\python -m pytest -q
```

`pytest` is only installed in the venv, so a bare `pytest` won't be found.

Tests are pure — no network, no live API. If a change needs a fixture, add it under `mcp/tests/`.

**Then check against real data when it's cheap** — one live call, or a real PoB export. Fixtures
only test what we thought to model; live checks caught what they couldn't (trade2 capping results
at 100, PoB netting weapon-set points out of the passive count, exalted inflation faking trends).
