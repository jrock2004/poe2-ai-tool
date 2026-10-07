# poe2 MCP server

The data side of the assistant: a thin Python MCP server (official `mcp` SDK) that fetches live data,
reads the bundled game-data snapshots, and stores the player's own data. No judgment — that lives in the
skills. The plugin starts it (`.claude-plugin/plugin.json`); players never run it by hand.

Which sources it uses and why: the root [README](../README.md#data-sources--the-reuse-vs-build-decision).
Which source the skills use for what: `skills/poe2-core/references/sources.md`.

## Modules

- **Network clients** — the only modules that call out. Every result is cached and carries its fetch
  time (`_cache.py`), so tools report how fresh their data is.
  - `poe2scout.py` — currency and unique prices, price history.
  - `trade2.py` — the trade site's search, the only way to find rares by mods (notes below).
  - `guides.py` — build-guide fetch that respects robots.txt and content licenses.
  - `exchange.py` — GGG's Currency Exchange API, a second source of currency rates. Built and tested,
    not wired to a tool yet.
- **Pure** — `pob.py` (Path of Building codes) and `vendor_regex.py`.
- **Snapshots** — `treedata.py`, `stashlayout.py`, `gamedata.py` and `campaign.py` each load a generated
  `data/*_<version>.json`, and regenerate it when run as a module (`CONTRIBUTING.md`, "Per-patch
  refresh"). Never hand-edit the JSON.
- **The player's data** — `store.py` (the per-user data dir), `state.py` (roster, currency and league
  records), `knowledge.py` (the shipped knowledge files against the player's refreshed copies).
- `server.py` — the tools.

## Tools

The tool descriptions in `server.py` are the reference; this is the map. *Offline* means no network
call at all.

**League and the player's data**
- `get_leagues` — the leagues poe2scout knows.
- `set_league` — save the player's league as every tool's default; an explicit `league=` beats it.
- `get_state` / `update_state` — the saved profile, roster, currency and league records, changed by
  JSON Merge Patch. Offline.
- `get_knowledge` / `save_knowledge` — per-patch knowledge (`trials`, `farming`, `crafting`): the newer
  of the shipped copy and the player's refresh. Offline.

**Prices (poe2scout)**
- `get_currency_prices` — a category's currency prices, in exalted and divine.
- `market_movers` — the biggest 7-day risers and fallers per category, measured in divine.
- `price_unique` — a unique's (or a currency's) price by name, with close-name suggestions.
- `value_currency` — what an inventory is worth, per line and in total.

**Trade (trade2)**
- `find_stat_filters` — an affix line to trade stat ids. Cached 6h, so it calls out on a cold cache.
- `build_trade_filter` — a trade search body, without searching. Offline.
- `search_trade` — a live, read-only search: the cheapest listings, `priceStats` and a link.

**Builds**
- `fetch_guide` — a guide's text, or a `route` (browser or paste) when fetching isn't allowed.
- `parse_pob_code` — a Path of Building 2 code to character, stats, gems, items and tree. Offline.
- `summarize_tree` — the same tree summary from bare node ids. Offline.

**Game data (bundled snapshots, offline)**
- `mod_tiers` — which mods a base can roll, and their tiers.
- `item_text` — what a currency, omen, essence, alloy, rune, soul core or idol does, in the game's words.
- `trial_pool` — the Trial of Chaos modifiers, and the Sekhemas afflictions, boons and pledges.
- `get_stash_layout` — which item sits in each slot of a special stash tab.
- `campaign_rewards` — the campaign's permanent rewards (resistances, spirit, weapon-set points), with
  where each comes from and which are a pick-one.
- `build_vendor_regex` — a vendor search-box string from what the build wants.

## trade2 notes

The trade site's own API: undocumented and IP-rate-limited (the root README covers its Terms of Use).
The client is read-only and signed out, caches hard, and never buys.

- `POST /api/trade2/search/{realm}/{league}` → `{id, complexity, result: [hash…]}`. Works signed out
  with a browser-like User-Agent.
- `GET /api/trade2/fetch/{hashes}?query={id}` → the listings; at most 10 hashes a request.
- `GET /api/trade2/data/stats` → the stat-filter ids, cached 6h. `#` in a stat's text is the number,
  so matching an affix ignores its roll.
- Link for a search: `https://www.pathofexile.com/trade2/search/{realm}/{league}/{id}`.
- **Rate limits** come back in `X-Rate-Limit-Ip` as `hits:period:timeoutSeconds` buckets — seen
  2026-09-15: search `5:10:60,15:60:300,30:300:1800,600:21600:3600`, fetch `12:4:10,16:12:300,…`. The
  client throttles from `X-Rate-Limit-Ip-State` and honours `Retry-After` on a 429.
- A POESESSID cookie would raise the limits. Read-only search doesn't need one, and the client never
  sends one.

## Config (environment)

All optional; the plugin sets none of them.

- `POE2_DATA_DIR` — the per-user data dir (saved league, state, knowledge refreshes). Default:
  `%APPDATA%\poe2-ai-tools` (Windows), `~/Library/Application Support/poe2-ai-tools` (macOS),
  `$XDG_DATA_HOME/poe2-ai-tools` or `~/.local/share/poe2-ai-tools` (Linux).
- `POE2_LEAGUE` — the league when none is saved with `set_league`. Without either, the tools fall back
  to poe2scout's first "current" league, which is a guess: several are current at once.
- `POE2_REALM` — default `poe2`.
- Base URLs: `POE2SCOUT_BASE`, `POE2_TRADE_BASE`, `POE2_EXCHANGE_BASE`.
- User agents: `POE2_USER_AGENT` (poe2scout), `POE2_TRADE_USER_AGENT`, `POE2_GUIDE_USER_AGENT`,
  `POE2_EXCHANGE_USER_AGENT`.

## Run and test

The plugin runs `uv run --no-dev --project mcp poe2-mcp` (stdio). For development, build the test venv
with `scripts/setup.sh` (macOS/Linux) or `scripts/setup.ps1` (Windows), then from `mcp/`:
`.venv/bin/python -m pytest -q` (Windows: `.venv\Scripts\python -m pytest -q`). See `CONTRIBUTING.md`.
