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
| Patch / hotfix notes | pathofexile.com — PoE2's patch notes are forum 2212, "Early Access Patch Notes" (`/forum/view-forum/2212`) | poe2db.tw patch-notes page | Not `/forum/view-forum/patch-notes`: that one is PoE1's (3.x). Quote verbatim. Take the launch patch, not a later hotfix, as the league's patch. If 2212 stops getting new patches (at 1.0 the game leaves Early Access), find PoE2's patch-notes forum from the forum index and update this row. |
| Prices — currency, uniques | `get_currency_prices`, `price_unique`, `value_currency` (poe2scout) | — | Never from the web. |
| Prices — rares | `find_stat_filters` → `build_trade_filter` → `search_trade` (trade2) | — | poe2scout has no rares. Never from the web. |
| Market direction | `market_movers` (poe2scout) | — | Judge in divine (`changePctVsDivine`). |
| Passive tree | `parse_pob_code` / `summarize_tree` | github.com — PathOfBuildingCommunity/PathOfBuilding-PoE2 (`dev`) | Snapshot is generated; see `CONTRIBUTING.md`. |
| Mods, tiers, item bases | `mod_tiers` — the item snapshot, generated from github.com — repoe-fork/poe2 at a pinned commit (`CONTRIBUTING.md` step 9) | poe2db.tw — the item class page | Game data first; its `patch` says how current it is. poe2db's tier data is embedded in the page HTML. The data is GGG's. |
| Currency effects (currency, omens, essences, runes) | `item_text` — the item snapshot's game text for what PoE2's Currency Exchange trades, generated from github.com — repoe-fork/poe2 and repoe-fork/dat-export at pinned commits (`CONTRIBUTING.md` step 9) | poe2db.tw — `Stackable_Currency` | Quote, don't paraphrase. No odds or "1 in N". `adds` gives what an essence, alloy, rune, soul core or idol adds on each kind of item; a rune's `bonded` effect is Shaman-only (Wisdom of the Maji). The game files still carry PoE1 currency, so if `item_text` doesn't have an item, check poe2db before naming it — it may not be in PoE2, or be newer than the snapshot's `patch`. The data is GGG's. |
| Item rules (affix limits, corruption) | `get_knowledge('crafting')` | github.com — repoe-fork/dat-export (`develop`), `current/poe2/heuristics/csv`: `Rarity`, `ClientStrings` | Game data, not guides. Name the commit you read. Which currencies take corrupted items: search `item_text` for "corrupted" — each one's text or `use` says so. |
| Trial of Chaos modifiers | `trial_pool('chaos')` — the item snapshot, generated from github.com — repoe-fork/dat-export at a pinned commit (`CONTRIBUTING.md` step 9) | poe2db.tw — `Ultimatum` (Modifiers list) | Quote the texts. The snapshot follows the game's files, so changes the patch notes leave out come with it. How to choose: `get_knowledge('trials')`. |
| Trial of the Sekhemas (afflictions, boons, pledges) | `trial_pool('sekhemas')` — the item snapshot, as above | poe2db.tw | Quote the texts; one with `{0}` gets its number in game, so don't state one. How to choose: `get_knowledge('trials')`. |
| Campaign permanent rewards (resistances, spirit, weapon-set points) | `campaign_rewards` — the campaign snapshot, generated from github.com — PathOfBuildingCommunity/PathOfBuilding-PoE2 (`dev`), `src/Data/QuestRewards.lua` at a pinned commit (`CONTRIBUTING.md` step 10) | github.com — repoe-fork/dat-export, `QuestStaticRewards` (values only, no names) | Quote the texts. A reward with `options` is a pick-one: the player got only one of them. Its `patch` is the game patch the values were checked against. |
| Farming — what a mechanic drops | `get_knowledge('farming')` | poe2scout categories (via the tools) | No yields, drop rates, or "X per hour" from anywhere. |
| Stash-tab layouts (which item is in which slot) | `get_stash_layout` | github.com — repoe-fork/dat-export (`develop`), `current/poe2/heuristics/csv` | Snapshot is generated; see `CONTRIBUTING.md`. Column names there are guesses — trust `_COLUMNS` in `stashlayout.py`, not the headers. No license; the data is GGG's. |
| Game / PoB UI steps | `references/how-to.md` | *not set* | |
| Build guides | the player's link or PoB code, via `fetch_guide` | — | Follow its `route`. See "Build creators" for whose guides to trust. To help pick one (`poe2-build-picker`): a matching creator's build list. |
| Build popularity (what people play) | the player, on `poe.ninja/poe2/builds` — give them the link | — | Never read it ourselves; see "Avoid". |

Domains for `allowed_domains`: `pathofexile.com`, `poe2db.tw`, `github.com`.

## Avoid

| Site | Why | Enforced by |
|---|---|---|
| maxroll.gg | License prohibits automated/AI use. Ask the player to paste the PoB code or text. | `guides.PROHIBITED_HOSTS` |
| poe2wiki.net | Bot challenge. Don't solve it. | `fetch_guide` block detection only |
| game8.co | Blocks AI crawlers. | robots check only |
| Currency-seller "guide" sites | SEO content, not references. | nothing — judgment |
| mobalytics.gg, for game facts | Editorial guides lag patches: a corruption rule taken from one was contradicted by game data. A guide link the player pastes is fine, through `fetch_guide`; if Mobalytics blocks the fetch, follow its `route`. | nothing — judgment |
| PoE1 references (poewiki.net, poedb.tw) | Different game; same item and skill names. Not poe2db.tw. | nothing — judgment |
| poe.ninja builds and character pages | Its API docs (poe.ninja/docs/api, checked 2026-10-07) say the builds, character and Path of Building data are internal and "not available for third-party use". Give the player the link; for a character they like, they copy its PoB code. Its economy endpoints are separate and public. | nothing — judgment |

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
