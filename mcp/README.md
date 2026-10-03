# poe2 MCP server (data plumbing)

Thin MCP server that gives the skills live data. **Python** (see root README).
Not implemented yet; this documents the endpoints and decisions so Phase 1 can start immediately.

## Sources & split (from the Phase 0 spike)

### poe2scout — REUSE for currencies, uniques, price history
Base: `https://api.poe2scout.com` (legacy proxy: `https://poe2scout.com/api/*`). .NET API.
Realm + league are path params; discover them at runtime via `GET /{realm}/Leagues`.
Real routes (read from source):

- `GET /{realm}/Leagues` — list leagues for a realm (realm is `poe2`).
- `GET /{realm}/Leagues/{league}/Items` — flat list of **currencies + uniques** with `CurrentPrice`.
  Fields: ItemId, CategoryApiId, Text, Name, Type, ApiId, BaseItemTypeId, CurrentPrice, IconUrl.
- `GET /{realm}/Leagues/{league}/Items/{itemId}` — one item.
- `GET /{realm}/Leagues/{league}/Items/{itemId}/History` — price history.
- `GET /{realm}/Leagues/{league}/Items/Categories` — item categories.
- `GET /{realm}/Leagues/{league}/Currencies/ByCategory` — currency prices by category.
- `GET /{realm}/Leagues/{league}/Currencies/{apiId}` — one currency.
- `GET /{realm}/Leagues/{league}/Currencies/Pairs/{id1}/{id2}/History` — pair exchange history.
- `GET /{realm}/Leagues/{league}/Uniques/ByCategory` — unique prices by category.
- `GET /{realm}/Leagues/{league}/ExchangeSnapshot` | `/SnapshotHistory` | `/SnapshotPairs` | `/ReferenceCurrencies`.
- `GET /Realms/{realm}/Filters` — available filters.

**Key limitation:** no rare-item-by-affix search. `/Items` is a priced reference of currencies +
uniques only, no stat filters. Etiquette: descriptive `User-Agent` with contact; cache; ~2 req/s.

### GGG /trade2 — thin adapter BUILT (`trade2.py`)
Unofficial, undocumented, IP-rate-limited. The ONLY source that searches rares by mods. Rules: cache
hard, read-only, never auto-buy, back off on 429. Powers F6 trade filters and rare pricing in F1.

**Live-validated (2026-09-15, Forbidden Rites / poe2 realm):**
- `POST /api/trade2/search/{realm}/{league}` `{query…}` → `{id, complexity, result:[hash,…]}`. Works
  **unauthenticated** from a normal IP with a browser-like `User-Agent` (no POESESSID needed here).
- `GET /api/trade2/fetch/{hashes}?query={id}` → `{result:[{id, listing, item}]}`; ≤10 hashes/request.
  `listing.price` = `{type, amount, currency}`; `item` has name/baseType/rarity/ilvl/explicitMods.
- `GET /api/trade2/data/stats` → stat-filter ids (`explicit.stat_…`), grouped; cached 6h. `#` in the
  text is the numeric placeholder, so affix→id matching ignores the rolled value.
- Clickable link for a search id: `https://www.pathofexile.com/trade2/search/{realm}/{league}/{id}`.
- **Rate limits (from response headers, honor them):** search `X-Rate-Limit-Ip: 5:10:60,15:60:300,
  30:300:1800,600:21600:3600` (5/10s, 15/60s, …); fetch `12:4:10,16:12:300,…`. Format is
  `hits:period:timeoutSeconds`. The client self-throttles from the returned `…-State` header and 429s.
- A POESESSID cookie (env, later) would raise limits and surface online/afk status, but isn't required
  for read-only search.

### poe.ninja — fallback economy overview
Public poe2 economy endpoints, no auth, ~5 min cache, descriptive User-Agent. Cross-check for prices.

### Build guides — robots/license-aware fetch (`guides.py`)
**Re-verified Sep 2026 — this overturns the plan's older Phase-0 spike:**
- **Mobalytics** — now **Cloudflare-403s** server fetches even with a browser UA (was "clean static").
  → route `browser` (assistant reads it in the player's own browser) or paste a PoB code.
- **poe-vault** — static and readable → **fetch works**.
- **Maxroll** — reachable, but its robots.txt (Ziff Davis) **explicitly prohibits automated/AI use** of
  the content. We respect that and refuse → route `paste`.

`fetch_guide` gates on robots.txt (Disallow *and* no-AI/scraping preamble) and a small prohibited-host
list, fetches with an honest descriptive UA where permitted, extracts readable text (BeautifulSoup),
and otherwise returns a `route` (`browser`/`paste`) instead of scraping around the block. Guide
structuring into stages (plan §5.1) is the `poe2-build-review` skill's job, not the tool's.

### GGG Character API (OAuth, poe2 realm) — BLOCKED, deferred
Official; would list characters and return gear/skills/passives. Endpoints exist (`GET /character/poe2`,
`GET /character/poe2/{name}`, scope `account:characters`, public/PKCE client). **But OAuth client
registration is currently closed** — the developer docs say *"We are currently unable to process new
applications."* So this is unobtainable right now; character reading uses **PoB paste / screenshot**
(the design primary until registration reopens). See `docs/ggg-oauth-application.md` (parked draft).
Stash/currency is NOT available at all (no PoE2 stash API) — currency comes from screenshots.

## MCP tools
Implemented (Phase 1):
- `get_leagues` — poe2scout leagues + current divine price.
- `get_currency_prices(category, search, league?)` — currency prices in exalted + divine.
- `price_unique(name, league?)` — unique/currency reference price, with close-name suggestions.
- `value_currency(holdings, league?)` — value an inventory of {name, count} at current prices, in
  exalted + divine, per line and total (net worth / affordability). Powers `poe2-currency-tracker`.
- `find_stat_filters(affix)` — resolve an affix line to /trade2 stat-filter ids (no search; reads
  GGG's stat reference, fetched once and cached 6h).
- `build_trade_filter(category, stats, max_price…)` — construct a /trade2 query (offline, no search).
- `search_trade(query, league?, limit)` — live read-only /trade2 search + top listings + link.
- `fetch_guide(url)` — robots/license-aware guide fetch; returns text, or a `route` (browser/paste)
  when fetching isn't permitted or is bot-blocked. Powers `poe2-build-review`.
- `parse_pob_code(code)` — decode a Path of Building 2 export code into character, computed stats
  (resistances/life/ES/DPS), the active skill set's gems, and equipped items (implicit + explicit
  mods). Offline, so share links (pobb.in) aren't resolved — paste the code itself. Feeds
  gear-upgrade / build-review without a screenshot.

Planned (later phases): `get_my_characters` (OAuth, blocked), `poe2-meta-strategy` data.

## Config (env)
- `POE2_LEAGUE` — default league (e.g. `Forbidden Rites`). **Set this**; temp leagues rotate and
  poe2scout marks several leagues current at once, so the "first current" fallback is unreliable.
- `POE2_REALM` (default `poe2`), `POE2SCOUT_BASE`, `POE2_USER_AGENT`, `POE2_TRADE_USER_AGENT`,
  `POE2_GUIDE_USER_AGENT`.

## Run
`python -m venv .venv && . .venv/bin/activate && pip install -e . --group dev && POE2_LEAGUE="Forbidden Rites" poe2-mcp`
— then register it in your MCP client. Tests: `pytest -q` from `mcp/`. (Windows: `.venv\Scripts\activate`.)
