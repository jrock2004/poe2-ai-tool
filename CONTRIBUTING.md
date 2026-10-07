# Contributing

Thanks for helping keep this current. Most of the upkeep is the **per-patch refresh** below: market
data is live, but a few files describe the game itself and go stale when GGG ships a patch.

## Setup and tests

Run the dev setup script for your platform (see [README → Development](README.md#development)), then
from `mcp/`:

```bash
.venv/bin/python -m pytest -q          # Windows: .venv\Scripts\python -m pytest -q
```

Tests are pure — no network, no live API. Add fixtures under `mcp/tests/` rather than calling out.

## Ground rules

- **Read-only toward GGG.** Nothing may buy, list, or whisper. Tools generate searches and advice.
- **Respect sources.** Where to look things up, and what to avoid, is in
  `skills/poe2-core/references/sources.md` — the only place those rules live. Don't add a site that
  forbids automated/AI use or puts up a bot wall; put it under "Avoid" with the reason.
- **Ground every claim.** Confidence comes from data (see
  `skills/poe2-core/references/confidence.md`). Knowledge files carry a freshness stamp and their
  sources; if you can't confirm something, mark it "not researched" instead of guessing.
- **Small, reviewable changes,** with tests for anything in `mcp/`.

## Per-patch refresh

When a patch or new league lands, work through this list. Each item says how to tell it's needed.

### 1. Passive-tree snapshot

**Needed when** a PoB2 export's `tree.treeVersion` has no snapshot — `parse_pob_code` then returns
node ids only and `tree.note` says so.

1. Get the new `src/TreeData/<version>/tree.lua` from
   [PathOfBuilding-PoE2](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2) (`dev`
   branch) and note the commit it came from.
2. From `mcp/`, generate the snapshot. The command writes the file itself — **don't redirect with
   `>`**, which on Windows PowerShell writes UTF-16 and breaks the JSON:
   ```bash
   .venv/bin/python -m poe2_mcp.treedata path/to/tree.lua <version> "PathOfBuilding-PoE2@<commit> (dev, <date>), src/TreeData/<version>/tree.lua -- MIT; tree data originally from GGG" src/poe2_mcp/data/tree_<version>.json
   ```
3. **Keep the old snapshot.** Characters still on the old tree use it.
   **Restart the MCP server** afterwards — snapshot lookups are cached per version, including
   "not found", so a running server that already saw the new version keeps returning ids only.
4. Check it: run the tests, then parse a real export on the new tree and compare `passiveCount` /
   `ascendancyCount` with the points Path of Building shows. If the parser rejects the file, the
   `tree.lua` format changed — fix `treedata.py` rather than hand-editing the JSON.

**Before Path of Building ships the new tree** — at a league launch, say — generate from GGG's own
export instead, so node names and point counts work from day one:

1. From [grindinggear/poe2-skilltree-export](https://github.com/grindinggear/poe2-skilltree-export),
   take `data.json` at the commit named for the new patch (e.g. `0.5.5`), and note the commit.
2. Pass it where `tree.lua` goes — a `.json` input is read as GGG's export:
   ```bash
   .venv/bin/python -m poe2_mcp.treedata path/to/data.json <version> "grindinggear/poe2-skilltree-export@<commit> (<patch>), data.json -- GGG's official tree export" src/poe2_mcp/data/tree_<version>.json
   ```
3. Ship it, then regenerate from Path of Building's `tree.lua` (steps 1–4 above) once it lands. GGG's
   file leaves a few nodes unnamed, and they stay unnamed until then.

### 2. Trials knowledge

**Needed when** patch notes touch the Trial of the Sekhemas or Trial of Chaos — and re-check the Trial
of Chaos modifiers every patch anyway: 0.5.5 reworked them without saying so in the notes.
Update `mcp/src/poe2_mcp/knowledge/trials.md`:

- Take Trial of Chaos modifier text from poe2db's `Ultimatum` page (its *Modifiers* list is game data
  and matches the in-game tooltips), not from guide sites — they lag a patch or more.
- Quote modifier text verbatim, with every version's values; re-stamp the date, patch, and sources.

### 3. Farming knowledge

**Needed when** patch notes change how a mechanic is targeted or what it drops, or poe2scout's
categories change.
Update `mcp/src/poe2_mcp/knowledge/farming.md`:

- Re-pull each category's item families from poe2scout (`/Leagues/<league>/Currencies/ByCategory`)
  rather than writing them from memory.
- Quote patch-note changes verbatim; re-stamp the date, patch, and sources.
- Never add yields, drop rates, or "X per hour" — nothing reports them reliably.

### 4. Crafting knowledge

**Needed when** patch notes change what a currency does, add or remove a currency, or change mod tiers
or their modifier levels.
Update `mcp/src/poe2_mcp/knowledge/crafting.md`:

- Quote currency descriptions from poe2db's `Stackable_Currency` page rather than paraphrasing.
- Re-check each tier table against the item class's poe2db page; its rendered tables may not load in a
  fetcher, but the mod data is embedded in the page's HTML.
- Never add odds or "1 in N" — mod weights haven't been pulled in. Re-stamp the date, patch, and
  sources.

### 5. How-to steps

**Needed when** the game's or Path of Building's UI changed (menu names, export flow, hotkeys).
Update `skills/poe2-core/references/how-to.md`.

### 6. League

**Needed when** a new league starts. Nothing to change in the repo: each player runs `/poe2-new-league`,
which saves the league in their own data dir (`set_league`). Ship the step 2–4 knowledge refreshes so
players who skip their own refresh still get them on update.

### 7. Vendor regex data

**Needed when** patch notes change mod tiers, their item levels, or mod wording.
In `mcp/src/poe2_mcp/vendor_regex.py`:

- **`TIERS`** — re-pull each mod's (item level, highest value) pairs from the poe2db item-class pages
  named in its source comment. As with crafting, the tier data is embedded in the page's HTML. Use regular
  tiers only, and take the highest value across slots. Re-stamp the patch in the comment.
- **Stat-list fixture** — regenerate `mcp/tests/trade2_stat_texts.json` from trade2 `/data/stats`
  (Explicit + Implicit `text`s, sorted, deduplicated), then run the tests: a renamed mod fails
  `test_targets_and_traps_still_exist`, and a fragment that now catches the wrong mod fails its traps.

### 8. Stash-tab layouts

**Needed every patch** — a patch can add, move, or remove a slot without saying so in the notes.
`get_stash_layout` serves the newest `mcp/src/poe2_mcp/data/stash_layouts_<version>.json`; the
currency tracker names items from it.

1. In [repoe-fork/dat-export](https://github.com/repoe-fork/dat-export) (`develop`), find the commit
   whose message names the new game version, e.g. `export data at version 3.29.3.3 / 4.5.5.2`. The
   second number is PoE2's: `4.5.5.2` is patch 0.5.5, so the snapshot version is `0_5_5`. Note the
   commit.
2. From that commit's `current/poe2/heuristics/csv/`, download `BaseItemTypes.csv` and the nine
   `<Tab>StashTabLayout.csv` files (Abyss, Breach, Currency, Delirium, Essence, Expedition, Fragment,
   Ritual, Socketable) into one folder.
3. From `mcp/`, generate the snapshot. The command writes the file itself — **don't redirect with
   `>`**:
   ```bash
   .venv/bin/python -m poe2_mcp.stashlayout path/to/csv <version> "repoe-fork/dat-export@<commit> (game <4.x.y.z>), current/poe2/heuristics/csv -- data is GGG's" src/poe2_mcp/data/stash_layouts_<version>.json
   ```
   Then delete the previous snapshot — only the newest is served.
4. If it fails:
   - **A missing column** — the export renamed one; its headers are guesses and change between runs.
     Find the new name, update `_COLUMNS` in `stashlayout.py`, and update the matching fixture rows in
     `mcp/tests/test_stashlayout.py`.
   - **A value out of range** — the table changed shape. Look at the rows before widening `_RANGES`.
5. Check it:
   - Run the tests.
   - Read the per-tab summary the command prints. Its overlap counts are raw: Delirium's stacked map
     slots always show hundreds, and `get_stash_layout` drops those. Any **other** new overlap is a
     slot to hover in game.
   - Call `get_stash_layout("currency")` and compare its rows with an in-game screenshot, slot by slot.
6. **Restart the MCP server** — snapshots are cached per version, so a running server keeps serving
   the old one.

## Releasing and sharing

**Every push to `main` is a release.** `.claude-plugin/plugin.json` has no `version` on purpose: without
one, Claude Code versions the plugin by commit. Players who turned on auto-update (README → Updates) get
a push in the background at their next session; everyone else when they run `claude plugin update`. So
keep `main` working where players run it: the `tests` workflow runs the suite on Windows and macOS, on
Python 3.10 and 3.14, for every push — fix a red run before anything else.

**Don't add `version` on its own.** It keeps players on that string however many commits land, until it
changes. Your own install — a local marketplace, loaded in place — ignores it, so a forgotten bump only
shows up as players quietly stuck on an old copy. Add it only together with bumping it on every release.

**If you want a release gate later,** use a branch rather than version strings: players add the
marketplace as `jrock2004/poe2-ai-tool#stable`, and you release by pushing `main` to `stable` once CI is
green (`git push origin main:stable`). `main` keeps taking every slice; players see only `stable`.

### Before sharing more widely

- **Contact in requests.** The poe2scout, trade2 and guide clients' default User-Agents carry the
  maintainer's email, so every player's requests would too. Keep it as the maintainer contact, or use the
  repo URL as the exchange client does. Commits also carry the author's email; GitHub's private
  noreply address covers future commits.
- **README framing.** It still reads as a one-player tool ("For: one player (me)").
- **The trade-search caveat** (README → "One exception to GGG's documented API") should be visible
  wherever you announce it.
- **Anthropic's plugin directory**, if you list it there: the listing reads `icon`, `documentationUrl`,
  `supportUrl`, `privacyPolicyUrl` and `termsOfServiceUrl` from `plugin.json`.
- **Keep the repository public.** Installing and auto-updating from a private repo needs each player's
  own git credentials (updates fail quietly without them), and a private repo's CI draws on a limited
  Actions allowance, while public repos run it free.

## Pull requests

- Say what patch or change prompted it, and link the patch notes.
- For knowledge files: list your sources, and keep the freshness stamp current — both the prose stamp
  and the `patch`/`refreshed` header at the top. The header decides whether a player's local refresh
  or your shipped copy wins (newer patch, then newer date), so bump it on every content change.
- For code: tests pass, and new behaviour has a test.
