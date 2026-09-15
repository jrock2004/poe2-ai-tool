# poe2 MCP server (data plumbing)

Thin MCP server that gives the skills live data. **TypeScript / Node** (assumption — see root README).
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

### GGG /trade2 — BUILD a thin adapter for rare search + filters
Unofficial, undocumented, rate-limited (a POESESSID cookie extends it). The ONLY source that searches
rares by mods. Rules: cache hard, read-only, never auto-buy, back off on 429. Powers F6 trade filters
and rare pricing in F1.

### poe.ninja — fallback economy overview
Public poe2 economy endpoints, no auth, ~5 min cache, descriptive User-Agent. Cross-check for prices.

### GGG Character API (OAuth, poe2 realm) — Phase 2
Official; lists characters and returns gear/skills/passives. Powers gear analysis without pasting PoB.
Stash/currency is NOT available (no PoE2 stash API) — currency comes from screenshots instead.

## Planned MCP tools
`get_leagues`, `get_currency_rates`, `price_item` (currency/unique), `build_trade_filter` (/trade2),
`search_trade` (/trade2, read-only), `get_my_characters` (OAuth), `parse_pob_code`, `fetch_guide`.

## Run (once implemented)
`npm install && npm run build && node dist/index.js` — then register as an MCP server in the client.
