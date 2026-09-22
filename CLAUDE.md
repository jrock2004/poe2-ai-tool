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

## Project

Personal Path of Exile 2 decision assistant. Two parts:

- `mcp/` — Python MCP server (official `mcp` SDK, pinned `<2`; `httpx`; `beautifulsoup4`).
  Data plumbing only.
- `skills/` — one folder per skill. The judgment lives here, not in the server.

Design rules that hold across both:

- **Read-only toward GGG.** Never buy, list, or whisper. Generate searches and advice; John acts.
- **Pure core, thin edges.** Query construction (`build_query`), PoB parsing, and scoring are
  pure and unit-tested. Network calls live only in the client modules — `trade2`, `poe2scout`,
  `guides` — and are cached. Note that `find_stat_filters` *does* hit the network on a cold
  cache (`trade2._stats` fetches `/data/stats`, cached 6h); "offline" in this repo usually means
  "cached," not "never calls out."
- **Every answer carries a grounded confidence level** (see `skills/poe2-core/references/confidence.md`).

## Tests

```bash
cd mcp && pytest -q
```

Tests are pure — no network, no live API. If a change needs a fixture, add it under `mcp/tests/`.
