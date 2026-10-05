# Sources

Where to look things up, per topic. This file is the **only** place source rules live — skills and
`CONTRIBUTING.md` point here instead of restating them.

General web results for PoE2 are mostly stale or SEO filler: guide sites lag a patch or more, and
PoE1 pages mix in under the same names. So:

- **Tools before the web.** If an MCP tool or `get_knowledge` covers it, use that.
- **Search only the listed domains.** When you do search, pass the topic's domains below as
  `allowed_domains`. If they don't have it, say "not researched" — don't widen the search to fill
  the gap.
- **Fetch only what's listed, or what the player gave you.** A guide link the player pasted is fine
  (through `fetch_guide`); a page a search surfaced from an unlisted site is not.
- **Name the source** in the answer, so the player can check it.

## By topic

| Topic | Primary | Fallback | Notes |
|---|---|---|---|
| Patch / hotfix notes | pathofexile.com — forum patch-notes section | poe2db.tw patch-notes page | Quote verbatim. Take the launch patch, not a later hotfix, as the league's patch. |
| Prices — currency, uniques | `get_currency_prices`, `price_unique`, `value_currency` (poe2scout) | — | Never from the web. |
| Prices — rares | `find_stat_filters` → `build_trade_filter` → `search_trade` (trade2) | — | poe2scout has no rares. Never from the web. |
| Market direction | `market_movers` (poe2scout) | — | Judge in divine (`changePctVsDivine`). |
| Passive tree | `parse_pob_code` / `summarize_tree` | github.com — PathOfBuildingCommunity/PathOfBuilding-PoE2 (`dev`) | Snapshot is generated; see `CONTRIBUTING.md`. |
| Mods, tiers, item bases | `get_knowledge('crafting')` | poe2db.tw — the item class page | Tier data is embedded in the page HTML. |
| Currency effects | `get_knowledge('crafting')` | poe2db.tw — `Stackable_Currency` | Quote, don't paraphrase. No odds or "1 in N". |
| Trial of Chaos modifiers | `get_knowledge('trials')` | poe2db.tw — `Ultimatum` (Modifiers list) | Re-check every patch; changes aren't always in the notes. |
| Trial of the Sekhemas | `get_knowledge('trials')` | poe2db.tw | |
| Farming — what a mechanic drops | `get_knowledge('farming')` | poe2scout categories (via the tools) | No yields, drop rates, or "X per hour" from anywhere. |
| Game / PoB UI steps | `references/how-to.md` | *not set* | |
| Build guides | the player's link or PoB code, via `fetch_guide` | — | Follow its `route`. See "Build creators" for whose guides to trust. |

Domains for `allowed_domains`: `pathofexile.com`, `poe2db.tw`, `github.com`.

## Avoid

| Site | Why | Enforced by |
|---|---|---|
| maxroll.gg | License prohibits automated/AI use. Ask the player to paste the PoB code or text. | `guides.PROHIBITED_HOSTS` |
| poe2wiki.net | Bot challenge. Don't solve it. | `fetch_guide` block detection only |
| game8.co | Blocks AI crawlers. | robots check only |
| Currency-seller "guide" sites | SEO content, not references. | nothing — judgment |
| PoE1 references (poewiki.net, poedb.tw) | Different game; same item and skill names. Not poe2db.tw. | nothing — judgment |

## Build creators

*Not filled in yet.* Until it is, don't call any creator trusted or untrusted — judge a guide only by
what it contains and how current its patch is.

| Creator | Good for | Publishes on | Last verified (league / patch) | Notes |
|---|---|---|---|---|
