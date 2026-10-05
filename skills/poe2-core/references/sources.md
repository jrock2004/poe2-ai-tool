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

Creators whose guides we trust, chosen by the maintainer and shipped with the plugin. To use it:

- **Match the guide to a creator**, strongest first. The guide's own URL doesn't name the creator
  (Mobalytics guides are `/poe-2/builds/<slug>`), so never match on it.
  1. **Author link** — the guide page links its author's profile, and that link is a listed
     "Build list" URL (Mobalytics: "By <name>" → `/poe-2/profile/<name>/builds`). Confirmed; nothing
     else to open.
  2. **Build list** — no author link, but the author shown on the page is a listed creator: confirm
     the guide's URL is on their build list.
  3. **Author name** — only if the build list can't be read (e.g. poe-vault, where the byline is plain
     text and there's no per-author list).

  No match → the creator is unknown, not untrusted: judge the guide only by what it contains and how
  current its patch is.
- **Trust covers "Good for" only.** A minion creator's bow guide is an unknown.
- **Check the stamp.** If the live patch is newer than "Last verified", say the creator's track record
  is from an older patch.
- Never call a creator untrusted unless they're listed as such here.

| Creator | Good for | Build list | Last verified (league / patch) | Notes |
|---|---|---|---|---|
| GhazzyTV | Minion builds, for every class that has them | poe-vault.com/poe2 — site root, not his list yet (match by author); YouTube @GhazzyTV | The Forbidden Rites / 0.5.5 | Updates guides every patch. Endgame variants are separate guides. |
| Fubgun | Bow builds | mobalytics.gg/poe-2/profile/fubgun/builds; YouTube @Fubgun | The Forbidden Rites / 0.5.5 | Updates guides every patch. Endgame variants are separate guides. |
| deadrabb1t | Plant builds; Energy Drain + Contagion builds | mobalytics.gg/poe-2/profile/deadrabb1t/builds; YouTube @DEADR4BB1T | The Forbidden Rites / 0.5.5 | Updates guides every patch. Endgame variant is usually in the same guide. Some guides are twink builds. |
| misoxshiru | Monk builds | mobalytics.gg/poe-2/profile/misoxshiru/builds; YouTube @MisoxShiru | The Forbidden Rites / 0.5.5 | |
