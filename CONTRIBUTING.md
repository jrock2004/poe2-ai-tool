# Contributing

Thanks for helping keep this current. Most of the upkeep is the **per-patch refresh** below: market
data is live, but a few files describe the game itself and go stale when GGG ships a patch.

## Setup and tests

Run the setup script for your platform (see [README → Setup](README.md#setup-per-machine)), then
from `mcp/`:

```bash
.venv/bin/python -m pytest -q          # Windows: .venv\Scripts\python -m pytest -q
```

Tests are pure — no network, no live API. Add fixtures under `mcp/tests/` rather than calling out.

## Ground rules

- **Read-only toward GGG.** Nothing may buy, list, or whisper. Tools generate searches and advice.
- **Respect sources.** Don't fetch from sites that forbid automated/AI use or put up a bot wall:
  Maxroll (license), poe2wiki (bot challenge), game8 (blocks AI crawlers). Prefer GGG's patch notes
  and poe2db. Avoid currency-seller "guide" sites — they're SEO content, not references.
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

### 2. Trials knowledge

**Needed when** patch notes touch the Trial of the Sekhemas or Trial of Chaos.
Update `mcp/src/poe2_mcp/knowledge/trials.md` and re-stamp its date and sources.

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

**Needed when** a new league starts. Each player runs `/poe2-new-league`, which updates `POE2_LEAGUE` in
their own `.mcp.json` (it's git-ignored). In the repo, update the default league in `scripts/setup.sh` and
`scripts/setup.ps1`, and the `POE2_LEAGUE` example in `mcp/README.md`.

## Pull requests

- Say what patch or change prompted it, and link the patch notes.
- For knowledge files: list your sources, and keep the freshness stamp current — both the prose stamp
  and the `patch`/`refreshed` header at the top. The header decides whether a player's local refresh
  or your shipped copy wins (newer patch, then newer date), so bump it on every content change.
- For code: tests pass, and new behaviour has a test.
