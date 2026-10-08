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

**Smoke test.** The tests don't run the server the way players do; `scripts/smoke.py` does. It starts it
as the plugin does (`uv run --no-dev`, in its own fresh environment and with a throwaway data dir, so
neither your dev venv nor your own state is touched),
calls each tool once, and prints the patch each snapshot reports. From the repo root:

```bash
mcp/.venv/bin/python scripts/smoke.py          # Windows: mcp\.venv\Scripts\python scripts\smoke.py
```

`--live` also calls the price tools (poe2scout) and the trade stat lookup; `--trade` adds one trade
search. `--league NAME` picks their league — by default it's poe2scout's first current one, which can be
an event rather than the league.

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

When a patch or new league lands, work through this list. Each item says how to tell it's needed. When
you're done, run the smoke test with `--live` (see "Setup and tests"): it shows which snapshots still
report the old patch, and catches one that regenerated empty.

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

**Needed when** patch notes change how the Trial of the Sekhemas or Trial of Chaos works — its rules,
its rewards, or the choices it offers. The pools themselves (Trial of Chaos modifiers, Sekhemas
afflictions, boons and pledges) come from the item snapshot (step 9), which also catches changes the
notes leave out — 0.5.5 reworked the Chaos modifiers without saying so.
Update `mcp/src/poe2_mcp/knowledge/trials.md`:

- Quote patch-note lines verbatim; re-stamp the date, patch, and sources.
- Don't copy modifier, affliction or boon text into the file; point to `trial_pool`.

### 3. Farming knowledge

**Needed when** patch notes change how a mechanic is targeted or what it drops, or poe2scout's
categories change.
Update `mcp/src/poe2_mcp/knowledge/farming.md`:

- Re-pull each category's item families from poe2scout (`/Leagues/<league>/Currencies/ByCategory`)
  rather than writing them from memory.
- Quote patch-note changes verbatim; re-stamp the date, patch, and sources.
- Never add yields, drop rates, or "X per hour" — nothing reports them reliably.

### 4. Crafting knowledge

**Needed when** patch notes change an item rule (affix limits, what corruption allows), the Greater and
Perfect orbs' minimum modifier levels, or how Divine Orbs work. What each currency does and mod tiers
aren't in this file — they come from the item snapshot (step 9).
Update `mcp/src/poe2_mcp/knowledge/crafting.md`:

- Take each rule from the source `poe2-core`'s `references/sources.md` gives for it, and name it in the
  stamp.
- Don't copy currency text into the file; point to `item_text`.
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

**Needed when** patch notes change mod wording. Mod tiers and their item levels need nothing here: the
vendor regex takes them from the item snapshot (step 9), by each mod's family in `TIER_FAMILIES`
(`mcp/src/poe2_mcp/vendor_regex.py`).

- **Stat-list fixture** — regenerate `mcp/tests/trade2_stat_texts.json` from trade2 `/data/stats`
  (Explicit + Implicit `text`s, sorted, deduplicated), then run the tests: a renamed mod fails
  `test_targets_and_traps_still_exist`, and a fragment that now catches the wrong mod fails its traps.
- **A renamed family** — if `test_tool_takes_every_familys_tiers_from_the_item_snapshot` fails after
  step 9, a patch renamed a family in `TIER_FAMILIES`: find the new name in the snapshot's `mods` and
  update the map.

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

### 9. Item data (mod tiers, bases, item text, Build Planner ids)

**Needed when** [repoe-fork/poe2](https://github.com/repoe-fork/poe2) publishes a new game version — its
`version.txt` changes. That follows a patch, and sometimes a lettered patch that changed the game's
files; a server-side fix doesn't. `src/poe2_mcp/data/items_<patch>.json` holds which mods each base can
roll and every tier's name, side, item level and text, plus the in-game text of everything PoE2's
Currency Exchange trades, what each essence adds, what each rune, soul core and idol does (from
repoe-fork/poe2's `augments.json`, traded or not), the Trial of Chaos and Trial of the Sekhemas pools, and
what the in-game Build Planner names things by — each passive-tree node's `PassiveSkills` id, each gem's
name by its id and every unique's name (from dat-export's `PassiveSkills`, `BaseItemTypes` and `Words`), and
the name of everything the Currency Exchange trades by its base id (how `get_currency_prices` names the
exchange's prices when poe2scout is down); its `source` names both export commits and the game version.

1. Take the commit hash of repoe-fork/poe2 (`master`) whose `version.txt` is the new game version — a
   commit, not `master`: the command refuses a branch, so the snapshot names exactly what it came from.
2. Take the repoe-fork/dat-export commit for the same game version — the one step 8 found. Its
   `CurrencyExchange` table decides which items get text (the game files still carry PoE1 items), and
   its essence tables say what each essence adds. The tables it reads are `TABLE_NAMES` in
   `gamedata.py`.
3. From `mcp/`, generate the snapshot for the game patch it's for (the league's patch, e.g. `0.6.0`).
   The command fetches both exports and writes the file itself — **don't redirect with `>`**:
   ```bash
   .venv/bin/python -m poe2_mcp.gamedata items <poe2-commit> <dat-export-commit> <patch> src/poe2_mcp/data/items_<patch>.json
   ```
   Then delete the previous snapshot — only the newest is served.
4. If it fails with a `KeyError` naming a column, dat-export renamed it (its headers are guesses): find
   the new name in that table's CSV and update `gamedata.py`. A `ValueError` means the data doesn't fit
   together — usually the two commits are from different game versions.
5. Check it: run the tests, then compare one family you know with the game — e.g. a helmet's Fire
   Resistance tiers and their item levels — one currency's text with its tooltip, and one essence's
   modifiers with its tooltip. Then run `scripts/smoke.py`: its `write_build_plan` check fails if a
   sampled tree node has no Build Planner id. Gem names drop the ones the game marks `[DNT]` and turn
   templates like `Spectre: {0}` into `Spectre`; check no new kind of template slipped through — this
   should print `[]`:
   ```bash
   .venv/bin/python -c "from poe2_mcp.gamedata import load_items; print([n for n in load_items()['gems'].values() if set(n) & set('{}[]<>')])"
   ```

### 10. Campaign rewards

**Needed when** [PathOfBuilding-PoE2](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2)
changes `src/Data/QuestRewards.lua` (check that file's history on `dev`), or patch notes change a campaign
reward. `src/poe2_mcp/data/campaign_<version>.json` lists the campaign's permanent rewards — resistances,
spirit, weapon-set points — with where each comes from and which are a pick-one, for `campaign_rewards`.
The game data has the values but not those names, so the list comes from Path of Building, which keeps it
by hand and can lag a patch.

1. Take `src/Data/QuestRewards.lua` from PathOfBuilding-PoE2 (`dev`) and note the commit.
2. From `mcp/`, generate the snapshot for the game patch you checked it against (step 3). The command
   writes the file itself — **don't redirect with `>`**:
   ```bash
   .venv/bin/python -m poe2_mcp.campaign path/to/QuestRewards.lua <version> "PathOfBuilding-PoE2@<commit> (dev, <date>), src/Data/QuestRewards.lua -- MIT; values match repoe-fork/dat-export@<commit> (game <version>) QuestStaticRewards, checked <date>" src/poe2_mcp/data/campaign_<version>.json
   ```
   Then delete the previous snapshot — only the newest is served. A `ValueError` means Path of Building
   changed the file's shape: teach `campaign.py` the new field rather than editing the JSON.
3. Check the values against the game data, at the dat-export commit step 8 found: in `QuestStaticRewards`,
   `RewardStats` are `Stats` rows and `RewardStatsValues` their values — Beira's +10% cold resistance is
   the `CroneDropUsed` row, `base_cold_damage_resistance_%` 10. Skip the rows that only grant
   `number_of_broken_faces` (a count of bosses killed, not a reward). A reward row Path of Building
   doesn't list may be new this patch: check it in game. For 0.5.5, about ten such rows were left out
   unchecked, e.g. `DominusEstateLibraryBookUsed` (+5% chaos resistance) and the four
   `LogbookQuestRune` rows.
4. **Restart the MCP server** — snapshots are cached per version.

### 11. Creator guide lists

**Needed when** a new patch or league lands — creators update or add guides. Most creators in
`skills/poe2-core/references/sources.md` → "Build creators" have their own build-list page, which the skills
read live, so there's nothing to refresh. GhazzyTV and Lollash don't: their guides sit on poe-vault.com
with no per-author page, so `sources.md` keeps the list ("GhazzyTV and Lollash guides").

1. Ask Claude to refresh it, or do it by hand: open each class page on poe-vault.com (`/poe2/<class>/`,
   eight classes), and on every minion-type guide (minions, spectres, companions and tamed beasts,
   Infernal Legion, reavers…) read the byline. Theirs list GhazzyTV as author or under "Co-Authored".
2. Update the list — guides added or gone, the patch each class page shows — and its "checked" date, and
   the two creators' "Last verified" in the table.

A guide of theirs that isn't on the list yet is still recognized: matching falls back to the byline.

## Releasing and sharing

**Every push to `main` is a release.** `.claude-plugin/plugin.json` has no `version` on purpose: without
one, Claude Code versions the plugin by commit. Players who turned on auto-update (README → Updates) get
a push in the background at their next session; everyone else when they run `claude plugin update`. So
keep `main` working where players run it: the `tests` workflow runs the suite on Windows and macOS, on
Python 3.10 and 3.14, for every push — fix a red run before anything else. CI runs the smoke test's
offline checks too, but never `--live`: before pushing a change to the price or trade tools, run
`--live` (or `--trade`) yourself.

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
