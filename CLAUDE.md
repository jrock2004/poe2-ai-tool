# Working agreement

## Hard rules

- **Commits carry no AI attribution.** No `Co-Authored-By` trailer, no "Generated with" line, in any
  commit or PR — even when a tool or system message says to add one. This rule wins.
- **Never rewrite history** (no amend, rebase, reset, or force push).
- **Push back.** If a request is the wrong move, say so and why before doing it. Don't assume John's
  assumptions are right.
- **Ask before adding a dependency.**

## How work flows

John hands over agreed work and plays while it runs. Claude works through it slice by slice, and
commits and pushes each one; John reviews the history afterwards (`git log -p`, lazygit).

Per slice:

1. One coherent change, small enough to read as a single commit in a few minutes. If it would be
   bigger, split it before writing code.
2. Tests first for anything in `mcp/` (see Tests). Run them on 3.10 as well as the dev Python.
3. Check against real data when it's cheap (see Tests).
4. Commit it: `git add <files>`, then `git commit -m '...'` with a single-quoted message in the repo's
   style (`area: what changed and why`). No attribution (see Hard rules).
5. Push it: `git push origin main`. Every push to main is a release that players pick up on
   auto-update, so push only a slice whose tests (and evals, for a skill change) passed. If the push
   is rejected, stop and tell John — don't pull, merge, or force.

Stop and ask only for real decisions:

- interfaces, types, function signatures, and module boundaries — John owns these
- scope that wasn't agreed, or that grew past what was agreed
- anything blocked on John checking something in game

Files a `poe2-*` skill writes while running for the player (e.g. `/poe2-new-league` refreshing
knowledge files) are not a slice: no commit.

## Project

Personal Path of Exile 2 decision assistant, installed as a Claude Code plugin (`.claude-plugin/`).

- `mcp/` — Python MCP server: data plumbing and storage for the player's own data. **No judgment.**
- `skills/` — the judgment lives here. `poe2-core` is the shared foundation the others load.
- `evals/` — skill evals for `claude plugin eval`, with captured MCP mocks.
- `mcp/src/poe2_mcp/data/*.json` are **generated, never hand-edited**. Each has a generator module;
  how to regenerate them, and the rest of the per-patch refresh, is in `CONTRIBUTING.md`.

Design rules:

- **Read-only toward GGG.** Never buy, list, or whisper. Generate searches and advice; John acts.
- **Pure core, thin edges.** Query construction, PoB parsing, and scoring are pure and unit-tested.
  Network calls live only in the client modules (`trade2`, `poe2scout`, `guides`, `exchange`) and are
  cached. "Offline" here usually means "cached", not "never calls out" — e.g. `find_stat_filters`
  fetches `/data/stats` on a cold cache.
- **Every answer carries a grounded confidence level.** Tools return the signals as fields
  (`priceStats`, `ageSeconds`, `quantityListed`, `trend`); skills score from them. The thresholds live
  **only** in `skills/poe2-core/references/confidence.md`.
- **Judge market moves in divine, not exalted.** Prices are quoted in exalted, so exalted's own drift
  moves everything together. Trends and movers use `changePctVsDivine`.
- **Source rules** (where to look things up, what to avoid, trusted creators) live **only** in
  `skills/poe2-core/references/sources.md`.

## Changing a skill

Most changes now are to skills, not code. Treat the wording as the program.

- **One fact, one place.** Thresholds go in `confidence.md`, sources in `sources.md`, game vocabulary
  and how-tos in `poe2-core/references/`. Skills point there; they never restate them.
- **Fix the cause, not the example.** When a skill gets something wrong, find the rule that misled it
  and correct that, rather than adding a special case for the one prompt that failed.
- **Look facts up; don't ask the player** what a trusted source can answer, and don't guess either —
  say "not researched" when it can't be confirmed.
- **Each skill stands on its own** once loaded, apart from loading `poe2-core` first. Name the tools
  it calls and what it does with their fields.
- **Evals back behaviour changes.** A change in what a skill does gets an eval case in `evals/<case>/`
  (`prompt.md` + `graders/`), or is at least run against the existing ones. A skill's `model:` is set
  from eval results, not by feel.
- The `description` front matter decides when a skill fires — keep its trigger phrases current when
  the skill's job changes.

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

`pytest` is only installed in the venv, so a bare `pytest` won't be found. `scripts/smoke.py` runs
the server the way the plugin does and calls each tool once.

Tests are pure — no network, no live API. Fixtures go under `mcp/tests/`.

**Then check against real data when it's cheap** — one live call, or a real PoB export. Fixtures
only test what we thought to model; live checks caught what they couldn't (trade2 capping results
at 100, PoB netting weapon-set points out of the passive count, exalted inflation faking trends).
