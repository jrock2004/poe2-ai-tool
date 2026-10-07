"""poe2-mcp -- thin MCP server exposing live Path of Exile 2 market data to the assistant skills.

Phase 1 surface: poe2scout for currency + unique pricing (get_leagues, get_currency_prices,
price_unique) and a read-only GGG /trade2 adapter for rare-item search + filter generation
(find_stat_filters, build_trade_filter, search_trade). OAuth character reading is deferred -- GGG
is not issuing new API clients (see mcp/README.md).

Run: `poe2-mcp` (installed script) or `python -m poe2_mcp.server` -- stdio transport; register in
your MCP client.
"""
from __future__ import annotations

import asyncio
import math
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from . import knowledge, stashlayout, state, store
from ._cache import Fetched, freshness
from .gamedata import (
    item_text as _item_text, load_items, mod_tiers as _mod_tiers, top_rolls, trial_pool as _trial_pool,
)
from .guides import GuideFetcher
from .pob import PobError, PobSelectionError, parse_pob_code as _parse_pob
from .pob import summarize_tree as _summarize_tree
from .poe2scout import (
    Poe2ScoutClient,
    change_vs_divine,
    exalted_to_divine,
    price_trend,
    rank_movers,
    rates_from_items,
    value_holdings,
)
from .trade2 import (
    StatFilter,
    Trade2Client,
    build_query,
    human_search_url,
    listing_price_stats,
    summarize_listing,
)
from . import vendor_regex

mcp = FastMCP("poe2-mcp")
_scout = Poe2ScoutClient()
_trade = Trade2Client()
_guides = GuideFetcher()


def _round(n: float, places: int) -> float | None:
    if n is None or not math.isfinite(n):
        return None
    return round(n, places)


async def _divine_change(league_value: str) -> tuple[Fetched[Any], float | None]:
    """Divine's own ~7-day change in exalted (for divine-relative moves), and the fetch it came from.

    Fetched on its own (cached) since divine may not be on the page a caller asked for.
    """
    fetched = await _scout.get_currencies_by_category(league_value, "currency", search="divine", per_page=5)
    divine = next((c for c in fetched.body.get("Items", []) if c.get("ApiId") == "divine"), None)
    trend = price_trend(divine.get("PriceLogs")) if divine else None
    return fetched, trend["changePct"] if trend else None


async def _whole_category(league_value: str, category: str) -> tuple[list[dict[str, Any]], list[Fetched[Any]]]:
    """Every item in a currency category -- all of poe2scout's pages, not just the first -- and the
    fetches it took (for freshness)."""
    items: list[dict[str, Any]] = []
    fetches: list[Fetched[Any]] = []
    page, pages = 1, 1
    while page <= pages:
        page_f = await _scout.get_currencies_by_category(league_value, category, page=page, per_page=250)
        fetches.append(page_f)
        items.extend(page_f.body.get("Items", []))
        pages = page_f.body.get("Pages") or 0
        page += 1
    return items, fetches


@mcp.tool()
async def get_leagues() -> list[dict[str, Any]]:
    """List Path of Exile 2 leagues from poe2scout.

    Includes which league is current and the current divine price (in exalted). Use this to
    discover the league name the other tools accept.
    """
    leagues = (await _scout.get_leagues()).body
    return [
        {
            "league": lg.get("Value"),
            "shortName": lg.get("ShortName"),
            "current": lg.get("IsCurrent"),
            "divinePriceInExalted": lg.get("DivinePrice"),
        }
        for lg in leagues
    ]


@mcp.tool()
async def set_league(league: str) -> dict[str, Any]:
    """Save the player's league as the default for every tool, until changed again.

    league: league name or short name, as listed by get_leagues. It's checked against poe2scout first;
    an unknown name raises and nothing is saved, and so does poe2scout being unreachable. Takes effect
    on the next call -- no restart needed.
    """
    resolved = (await _scout.resolve_league(league, strict=True)).body
    root = store.data_dir()
    config = store.read_config(root)
    config["league"] = resolved["Value"]
    store.write_config(root, config)
    return {
        "league": resolved["Value"],
        "shortName": resolved.get("ShortName"),
        "savedTo": str(root / store.CONFIG_FILE),
    }


def _knowledge_fields(k: knowledge.Knowledge) -> dict[str, Any]:
    return {
        "topic": k.topic,
        "source": k.source,
        "patch": k.stamp.patch,
        "refreshed": k.stamp.refreshed.isoformat(),
    }


@mcp.tool()
async def get_knowledge(topic: str) -> dict[str, Any]:
    """Get the assistant's per-patch game knowledge for a topic: 'trials', 'farming', or 'crafting'.

    Returns the newer of the copy shipped with the assistant and the player's local refresh (see
    save_knowledge): `source` says which, `patch`/`refreshed` say how current it is (a confidence
    input), and `text` is the Markdown itself.
    """
    k = knowledge.load(topic, store.data_dir())
    return {**_knowledge_fields(k), "text": k.text}


@mcp.tool()
async def save_knowledge(topic: str, text: str) -> dict[str, Any]:
    """Save a refreshed copy of a knowledge topic ('trials', 'farming', 'crafting') for this player.

    text: the full Markdown, starting with the header ---, patch: <e.g. 0.6.0>, refreshed: <YYYY-MM-DD>,
    ---. Refused (nothing written) if the header is missing or the copy isn't newer than the one
    shipped with the assistant. The copy lives outside the install, so it survives updates; an update
    that ships newer knowledge takes over from it automatically.
    """
    return _knowledge_fields(knowledge.save(topic, text, store.data_dir()))


@mcp.tool()
async def get_state() -> dict[str, Any]:
    """Get the player's saved state: `player` (profile), `characters` (roster, keyed by name),
    `currency` (inventory as currency[league][trade_mode]), and `leagues` (per-league records such as
    the patch). Shared by every Claude client on this machine; the poe2-core skill defines the shapes.
    """
    return state.load(store.data_dir())


@mcp.tool()
async def update_state(patch: dict[str, Any]) -> dict[str, Any]:
    """Change the player's saved state with a JSON Merge Patch (RFC 7396) and return the new state.

    Send only what changes: objects merge, `null` deletes a key, arrays and plain values replace.
    e.g. {"characters": {"Mandy__Chaos": {"goal": "mapping"}}} changes one field;
    {"characters": {"Old": null}} removes a character. Top-level keys must be player, characters,
    currency, or leagues. Setting `active: true` on a character clears it on all others.
    A rejected patch raises and changes nothing.
    """
    return state.update(store.data_dir(), patch)


@mcp.tool()
async def get_currency_prices(
    category: str,
    search: str | None = None,
    league: str | None = None,
    per_page: int = 25,
) -> dict[str, Any]:
    """Get current Path of Exile 2 currency prices for a category.

    category: poe2scout currency category apiId, e.g. 'currency', 'essences', 'runes', 'fragments'
      (catalysts are under 'breach'; market_movers' description lists every category).
    search: optional; part of an item's name or apiId, any case (e.g. 'divine', 'haste'). It's matched
      across the whole category: `total` counts every match, and up to per_page come back.
    league: league value; defaults to the saved league (set_league).
    Prices are returned in both exalted and divine. Each item also carries `trend` -- its daily price
    history (usually ~7 days): min/max in exalted, the oldest -> newest change in percent, and
    `changePctVsDivine`, the same change measured in divine. Prices are quoted in exalted, so when
    exalted itself weakens everything looks like it rose; the divine-relative number is the item's
    real move and the one to judge volatility by. (Both windows are the endpoint's ~7 days, compared
    first-to-last point; a gap in one series can shift its window by a day.) Currency/uniques only.
    If nothing comes back and poe2scout has no such category, `unknownCategory` is true and
    `validCategories` lists the ones it has.
    """
    resolved_f = await _scout.resolve_league(league)
    resolved = resolved_f.body
    divine_price = resolved.get("DivinePrice") or 0
    sources: list[Fetched[Any]] = [resolved_f]
    if search:
        # poe2scout's own search takes only an exact, case-sensitive name or apiId ("Divine" finds
        # nothing), so match part of either, in any case, over the whole category instead.
        everything, fetches = await _whole_category(resolved["Value"], category)
        sources.extend(fetches)
        needle = search.lower()
        found = [c for c in everything
                 if needle in (c.get("Text") or "").lower() or needle in (c.get("ApiId") or "").lower()]
        listed, total, page, pages = found[:per_page], len(found), 1, (1 if found else 0)
    else:
        resp_f = await _scout.get_currencies_by_category(resolved["Value"], category, per_page=per_page)
        sources.append(resp_f)
        resp = resp_f.body
        listed, total, page, pages = resp.get("Items", []), resp.get("Total"), resp.get("CurrentPage"), resp.get("Pages")
    divine_f, divine_change = await _divine_change(resolved["Value"])
    sources.append(divine_f)
    items = []
    for c in listed:
        price_ex = c.get("CurrentPrice")
        trend = price_trend(c.get("PriceLogs"))
        items.append(
            {
                "name": c.get("Text"),
                "apiId": c.get("ApiId"),
                "priceExalted": price_ex,
                "priceDivine": None
                if price_ex is None
                else _round(exalted_to_divine(price_ex, divine_price), 4),
                "quantityListed": c.get("CurrentQuantity"),
                "trend": None if trend is None else {
                    "days": trend["days"],
                    "minExalted": _round(trend["minExalted"], 2),
                    "maxExalted": _round(trend["maxExalted"], 2),
                    "changePct": _round(trend["changePct"], 1),
                    "changePctVsDivine": _round(change_vs_divine(trend["changePct"], divine_change), 1),
                },
            }
        )

    unknown: dict[str, Any] = {}
    note = "poe2scout reference prices (cached ~5 min). Currency/uniques only; no rare-affix search here."
    if not items:  # a real category with no match, or a name poe2scout doesn't have
        try:
            categories_f = await _scout.get_categories(resolved["Value"])
        except (RuntimeError, httpx.HTTPError, ValueError):
            categories_f = None  # the check is a nicety: answer as before
        if categories_f is not None:
            valid = [c.get("ApiId") for c in categories_f.body.get("CurrencyCategories") or []]
            if valid and category not in valid:
                sources.append(categories_f)
                unknown = {"unknownCategory": True, "validCategories": valid}
                note = f'poe2scout has no currency category "{category}" -- use one of validCategories.'

    return {
        "league": resolved["Value"],
        "divinePriceInExalted": divine_price,
        "total": total,
        "page": page,
        "pages": pages,
        **freshness(*sources),
        **unknown,
        "items": items,
        "note": note,
    }


# The farming-relevant categories market_movers scans by default (poe2scout has 17 in all).
DEFAULT_MOVER_CATEGORIES = ["fragments", "essences", "breach", "delirium", "ritual", "expedition", "abyss", "runes"]


@mcp.tool()
async def market_movers(
    categories: list[str] | None = None,
    league: str | None = None,
    top: int = 5,
) -> dict[str, Any]:
    """The biggest 7-day risers and fallers per Path of Exile 2 currency category, measured in divine.

    categories: poe2scout currency category apiIds; defaults to the farming set (fragments, essences,
    breach, delirium, ritual, expedition, abyss, runes). Others include 'currency', 'ultimatum',
    'vaultkeys', 'uncutgems', 'lineagesupportgems', 'idol', 'incursion', 'verisium', 'vaal'.
    Moves are changePctVsDivine -- the item's own move with exalted's drift removed. Items listed
    fewer than 50 times are skipped as too thin to trust (`thin` counts them). Read-only; cached.
    """
    resolved_f = await _scout.resolve_league(league)
    league_value = resolved_f.body["Value"]
    top = max(1, min(top, 20))
    divine_f, divine_change = await _divine_change(league_value)
    sources: list[Fetched[Any]] = [resolved_f, divine_f]

    results: dict[str, Any] = {}
    for category in categories or DEFAULT_MOVER_CATEGORIES:
        items, fetches = await _whole_category(league_value, category)  # a mover list must see it all
        sources.extend(fetches)
        if not items:
            results[category] = {"unknownCategory": True,
                                 "note": "poe2scout returned no items -- check the category apiId."}
            continue
        movers = rank_movers(items, divine_change, top=top)

        def shape(m: dict[str, Any]) -> dict[str, Any]:
            return {
                "name": m["name"], "apiId": m["apiId"],
                "priceExalted": _round(m["priceExalted"], 2) if m["priceExalted"] is not None else None,
                "quantityListed": m["quantityListed"],
                "changePct": _round(m["changePct"], 1),
                "changePctVsDivine": _round(m["changePctVsDivine"], 1),
            }

        results[category] = {
            "risers": [shape(m) for m in movers["risers"]],
            "fallers": [shape(m) for m in movers["fallers"]],
            "thin": movers["thin"],
            "noTrend": movers["noTrend"],
        }

    return {
        "league": league_value,
        "divineChangePct": _round(divine_change, 1),
        **freshness(*sources),
        "categories": results,
        "note": (
            "Moves are ~7-day, in divine terms. A mover is a price signal, not a profit rate -- no "
            "drop rates or run times are known."
            if divine_change is not None else
            "Divine's own price history is unavailable, so no inflation-free moves could be ranked."
        ),
    }


@mcp.tool()
async def price_unique(name: str, league: str | None = None) -> dict[str, Any]:
    """Look up the current price of a Path of Exile 2 unique item (or currency) by name.

    Matches against poe2scout's priced item list. Returns price in exalted and divine, plus
    close-name suggestions when there's no exact match.
    """
    resolved_f = await _scout.resolve_league(league)
    resolved = resolved_f.body
    divine_price = resolved.get("DivinePrice") or 0
    items_f = await _scout.get_items(resolved["Value"])
    items = items_f.body
    fresh = freshness(resolved_f, items_f)
    needle = name.strip().lower()

    def label(i: dict[str, Any]) -> str:
        return (i.get("Name") or i.get("Text") or "").lower()

    for i in items:
        if label(i) == needle:
            return {
                "league": resolved["Value"],
                "match": i.get("Name") or i.get("Text"),
                "type": i.get("Type"),
                "category": i.get("CategoryApiId"),
                "priceExalted": i.get("CurrentPrice"),
                "priceDivine": _round(exalted_to_divine(i.get("CurrentPrice", 0), divine_price), 4),
                **fresh,
                "confidenceHint": "Exact name match against poe2scout reference price.",
            }

    near = [
        {"name": i.get("Name") or i.get("Text"), "priceExalted": i.get("CurrentPrice")}
        for i in items
        if needle in label(i) or (label(i) and label(i) in needle)
    ][:8]
    return {
        "league": resolved["Value"],
        "match": None,
        "suggestions": near,
        **fresh,
        "note": (
            "No exact match; closest names above. poe2scout covers currencies + uniques, not rare gear."
            if near
            else "No match. poe2scout only prices currencies and uniques; rare items need the /trade2 adapter."
        ),
    }


@mcp.tool()
async def value_currency(
    holdings: list[dict[str, Any]],
    league: str | None = None,
) -> dict[str, Any]:
    """Value a Path of Exile 2 currency/item inventory at current poe2scout prices.

    holdings: list of {name, count} -- e.g. [{"name": "Divine Orb", "count": 11}, ...]. Names should
    be canonical (normalize shorthand via poe2-core's currency glossary first). Returns per-line and
    total worth in exalted (the base unit) and divine, plus any names that didn't match a priced item.
    Use it for net worth and "can I afford this?" -- deterministic arithmetic, not estimated.
    """
    resolved_f = await _scout.resolve_league(league)
    resolved = resolved_f.body
    divine_price = resolved.get("DivinePrice") or 0
    items_f = await _scout.get_items(resolved["Value"])
    valued = value_holdings(items_f.body, holdings, divine_price)
    return {
        "league": resolved["Value"],
        "divinePriceInExalted": divine_price,
        "lines": [
            {
                "name": ln["name"],
                "count": ln["count"],
                "unitExalted": _round(ln["unitExalted"], 3),
                "valueExalted": _round(ln["valueExalted"], 2),
                "valueDivine": _round(ln["valueDivine"], 3),
            }
            for ln in valued["lines"]
        ],
        "totalExalted": _round(valued["totalExalted"], 2),
        "totalDivine": _round(valued["totalDivine"], 3),
        "unmatched": valued["unmatched"],
        **freshness(resolved_f, items_f),
        "note": (
            "Valued at current poe2scout prices (cached ~5 min). Unmatched names weren't found as a "
            "priced item -- check spelling or normalize via the currency glossary."
        ),
    }


@mcp.tool()
async def find_stat_filters(affix: str, limit: int = 6) -> dict[str, Any]:
    """Resolve a human affix line to Path of Exile 2 trade stat-filter ids.

    Feed it what an item mod reads like -- e.g. '+80 to maximum Life', '30% increased Cold Damage',
    'Movement Speed' -- and it returns candidate filter ids (best match first) to use in
    build_trade_filter / search_trade. Numbers are treated as wildcards, so the value never blocks
    the match. Runs no trade search and returns no listings -- it only reads GGG's stat-filter
    reference, which it fetches once and caches for 6h, so the first call after a cold start is
    a live (rate-limited) request and later ones are free.
    """
    matches = await _trade.find_stats(affix, limit=limit)
    return {
        "affix": affix,
        "matches": matches,
        "note": "Use a match's 'id' as a stat filter id. Empty means no filter matched that wording.",
    }


def _stat_filters_from(stats: list[dict[str, Any]] | None) -> list[StatFilter]:
    out: list[StatFilter] = []
    for s in stats or []:
        sid = s.get("id")
        if not sid:
            continue
        out.append(StatFilter(id=sid, min=s.get("min"), max=s.get("max")))
    return out


@mcp.tool()
async def build_trade_filter(
    category: str | None = None,
    stats: list[dict[str, Any]] | None = None,
    max_price: float | None = None,
    price_currency: str = "divine",
    online_only: bool = True,
    max_level: int | None = None,
) -> dict[str, Any]:
    """Build a Path of Exile 2 /trade2 search body from filters, WITHOUT running a live search.

    Pure construction -- safe, no rate limit, no account contact. Use it to show the player the exact
    filter, or hand the returned 'query' to search_trade to run it.

    category: type option like 'armour.boots', 'weapon.crossbow', 'accessory.ring', 'jewel'.
    stats: list of {id, min?, max?}; get ids from find_stat_filters.
    max_price: optional ceiling in price_currency (e.g. your currency budget).
    max_level: optional; the character's level, so only items it can wear now come back. At least 1.
    """
    query = build_query(
        stats=_stat_filters_from(stats),
        category=category,
        max_price=max_price,
        price_currency=price_currency,
        online_only=online_only,
        max_level=max_level,
    )
    return {
        "query": query,
        "note": (
            "Filter built offline. Pass 'query' to search_trade to fetch live listings, or open the "
            "trade site and set these filters yourself. This tool never buys or whispers."
        ),
    }


@mcp.tool()
async def search_trade(
    query: dict[str, Any],
    league: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Run a live, read-only Path of Exile 2 /trade2 search and return the top listings.

    Pass a 'query' from build_trade_filter. Returns a clickable trade-site link plus up to `limit`
    cheapest matching listings (name, mods, price, seller, and the whisper text for you to copy).
    `priceStats` gives min/median/max in exalted and the max/min spread over the listings shown --
    the cheap end of the market, since results are price-ascending -- for grounding confidence.
    If poe2scout can't be reached, the listings still come back: only exalted prices are converted,
    and `note` says so. Rate-limited and cached; it never buys, lists, or whispers on your behalf --
    you act.
    """
    league_f = await _scout.resolve_league(league)
    league_id = league_f.body["Value"]
    limit = max(1, min(limit, 20))

    search_f = await _trade.search(league_id, query)
    sources = [league_f, search_f]
    result = search_f.body
    query_id = result.get("id")
    hashes = result.get("result") or []
    # `result` holds at most 100 hashes; `total` is the real match count (trade2 caps it at 10000).
    total = result.get("total", len(hashes))
    listings: list[dict[str, Any]] = []
    if query_id and hashes:
        entries_f = await _trade.fetch(query_id, hashes[:limit])
        sources.append(entries_f)
        listings = [summarize_listing(e) for e in entries_f.body]

    rates: dict[str, float] = {}
    scout_down = False
    if listings:
        try:
            items_f = await _scout.get_items(league_id)
            sources.append(items_f)
            rates = rates_from_items(items_f.body)
        except (RuntimeError, httpx.HTTPError, ValueError):
            # The listings come from trade2 and still stand. Exalted is the base unit, so it converts at 1.
            rates, scout_down = {"exalted": 1.0}, True
    stats = listing_price_stats(listings, rates)

    note = (
        "Read-only trade search (cached). Open 'url' to browse/whisper yourself; the tool never "
        "contacts sellers. 0 matches means the filter is too tight -- widen it and search again."
        if total else
        "No listings matched. Loosen the filters (drop a min, allow offline, raise the price cap)."
    )
    if scout_down:
        note = ("poe2scout was unreachable, so only exalted prices were converted; the other currencies "
                "are in priceStats.unconvertedCurrencies. " + note)

    return {
        "league": league_id,
        "url": human_search_url(league_id, query_id) if query_id else None,
        "matched": total,
        "shown": len(listings),
        **freshness(*sources),
        "priceStats": {
            "basis": f"cheapest {stats['count']} listed",
            "count": stats["count"],
            "converted": stats["converted"],
            "unconvertedCurrencies": stats["unconvertedCurrencies"],
            "minExalted": _round(stats["minExalted"], 2),
            "medianExalted": _round(stats["medianExalted"], 2),
            "maxExalted": _round(stats["maxExalted"], 2),
            "spreadRatio": _round(stats["spreadRatio"], 2),
        },
        "listings": listings,
        "note": note,
    }


@mcp.tool()
async def fetch_guide(url: str) -> dict[str, Any]:
    """Fetch a Path of Exile 2 build guide's text, respecting robots.txt and content licenses.

    Returns the readable page text when fetching is permitted and works. When it isn't, returns a
    `route` telling how to get the guide another way instead of scraping around the block:
      - route "paste": the site forbids automated/AI use (e.g. Maxroll/Ziff Davis) or robots blocks it
        -- ask the player for the guide's PoB code or pasted text.
      - route "browser": the site bot-blocked the server fetch (e.g. Mobalytics/Cloudflare) -- the
        assistant opens it in a browser and reads it there; at a bot check it asks the player to open
        it instead, or to paste the PoB code.
    `partial: true` means some content loads client-side and detail may be missing. Never bypasses a
    block or a stated no-AI policy.
    """
    return await asyncio.to_thread(_guides.fetch, url)


@mcp.tool()
async def parse_pob_code(
    code: str,
    tree_spec: int | None = None,
    skill_set: int | None = None,
    item_set: int | None = None,
) -> dict[str, Any]:
    """Decode a Path of Building 2 export code into a structured build summary.

    Accepts a raw PoB code or raw PoB XML -- not a share link (pobb.in links hold an id, not the
    code). Returns the character (level/class/ascendancy), computed stats (resistances, life, energy
    shield, DPS), a skill set's gems, equipped items with implicit and explicit mods, and a passive
    tree: allocated node ids, socketed jewels, named keystones/notables, the ascendancy choices
    taken, and passive/ascendancy point counts (names and counts come from a bundled tree snapshot;
    if the build's tree version has none, `tree.note` says so and only ids are returned) -- so a
    pasted PoB code can feed poe2-gear-upgrade / poe2-build-review without a character screenshot.

    A build can carry several tree specs, skill sets, and item sets -- guides often keep one per
    stage. `sets` lists all three by 1-based position with titles and which is active. By default
    the active ones are parsed; pass `tree_spec` / `skill_set` / `item_set` (a position from `sets`)
    to parse another. Computed stats only exist for the active sets: `statsNote` says so when a
    selector picks a different one. An out-of-range position is an error, never a fallback.
    Offline; no network.
    """
    try:
        return _parse_pob(code, tree_spec, skill_set, item_set)
    except PobSelectionError as e:
        return {"valid": False, "error": str(e), "note": "Pick a position listed in `sets`."}
    except PobError as e:
        return {
            "valid": False,
            "error": str(e),
            "note": "Paste the code from Path of Building: Import/Export -> Generate -> Copy.",
        }


@mcp.tool()
async def summarize_tree(
    main: list[int],
    tree_version: str,
    weapon_set_1: list[int] | None = None,
    weapon_set_2: list[int] | None = None,
    ascendancy: list[int] | None = None,
) -> dict[str, Any]:
    """Name and count a Path of Exile 2 passive tree from bare node ids.

    For guides with no PoB code -- e.g. Mobalytics, whose page data lists each variant's tree as
    `node-<id>` slugs (strip the `node-` prefix). Pass the main tree, each weapon set's nodes, and
    the ascendancy nodes; the lists may be disjoint or overlap. `tree_version` is the snapshot to
    name against, e.g. "0_5" for patch 0.5.x. Returns the same block as `parse_pob_code`'s `tree`
    (node ids, named keystones/notables, ascendancy choices, passive/ascendancy point counts),
    without `jewels`; if there's no snapshot for the version, `note` says so and only ids come back.
    Offline; no network.
    """
    return _summarize_tree(main, tree_version, weapon_set_1, weapon_set_2, ascendancy)


@mcp.tool()
async def get_stash_layout(tab: str) -> dict[str, Any]:
    """Which item sits in each slot of a Path of Exile 2 special stash tab, for reading a screenshot.

    The special tabs are fixed layouts: a slot always holds the same item, held or not -- so name an
    item from its slot, and read only the count from the image. `tab` is one of: abyss, breach,
    currency, delirium, essence, expedition, fragment, ritual, socketable.

    Returns `rows` in reading order (by `subTab` page, then top to bottom, each row left to right),
    each slot {key, item} plus w/h when wider or taller than one slot and `label` for a Ritual group
    icon; `item` null is an open slot that can hold anything. `onlyWhenHeld` lists slots that appear
    only while the player has the item. `craftingSlot` says the tab has one (it's left out of rows
    and never read). `overlaps` names slot pairs the data puts on the same spot -- confirm those
    in game. `patch` is the snapshot's patch; if the league's is newer, the layout may be stale.
    Offline; no network.
    """
    return stashlayout.stash_layout(tab)


# What the item-data tools answer when no item snapshot ships.
_NO_ITEM_SNAPSHOT = {"valid": False, "error": "no item snapshot is installed",
                     "note": "Regenerate one with `python -m poe2_mcp.gamedata` (see CONTRIBUTING.md)."}


@mcp.tool()
async def mod_tiers(base: str, search: str | None = None, item_level: int | None = None) -> dict[str, Any]:
    """Which mods a Path of Exile 2 base can roll, from the game's own data: each mod family with its
    side (prefix/suffix) and every tier's name, text and the item level it needs.

    base: the item's base type as its item text names it, e.g. 'Rusted Greathelm' (any case). An unknown
    name returns `suggestions`; a name with several variants returns each, with its requirements.
    search: optional; part of a tier's text or a family's name, e.g. 'fire resistance' or 'minion'. A
    found base with no matching family means that mod can't roll on it.
    item_level: optional; the item's item level -- each tier then says whether it `canRoll` there.
    `patch` is the game patch the data is from; if the league's is newer, it may be stale. No odds: the
    game data says what can roll, not how likely it is. Offline.
    """
    items = load_items()
    if items is None:
        return {**_NO_ITEM_SNAPSHOT}
    return _mod_tiers(items, base, search, item_level)


@mcp.tool()
async def item_text(search: str) -> dict[str, Any]:
    """What a Path of Exile 2 currency item does, in the game's own words: anything the Currency Exchange
    trades -- orbs, omens, essences, alloys, catalysts, liquid emotions, shards -- and every rune, soul
    core and idol (augments).

    search: an item's name, or words from what it does, in any case. 'Chaos Orb' finds the orb and the
    omens that change it; 'instil' finds what Instils amulets; 'maximum life' finds the essences that add
    it. Each match gives `text` (what it does) and `use` (how it's used, and on what) -- quote them,
    don't paraphrase. An essence, alloy or augment also has `adds`: for each kind of item it fits (`on`),
    what it adds there (`text`). An essence's or alloy's row says whether that's a prefix or suffix
    (`side`). An augment's row may have `bonded`: a Bonded modifier, which the game gives only to a Shaman
    who allocated Wisdom of the Maji (`text` is empty where that's all it has). An augment's `limit` caps
    how many can be socketed ("1 Ancient Augment": one at a time); `level` is its level requirement. An
    exact name comes first. Up to 20 matches; `total` counts them all -- if it's more, narrow the search.
    No match returns `suggestions`. `patch` is the game patch the data is from; if the league's is newer,
    it may be stale. Offline.
    """
    items = load_items()
    if items is None:
        return {**_NO_ITEM_SNAPSHOT}
    return _item_text(items, search)


@mcp.tool()
async def trial_pool(trial: str, search: str | None = None) -> dict[str, Any]:
    """What a Path of Exile 2 Ascendancy trial can throw at you, from the game's own data.

    trial: 'chaos' -- the Trial of Chaos modifiers, each with every version (`name`, `tier` 1-5, `text`) and
    its `kind`: a 'modifier', a room 'hazard', or a 'wager'. Or 'sekhemas' -- the Trial of the Sekhemas
    afflictions, boons and pledges, each with its `category` ('Minor Afflictions', 'Major Boons',
    'Pledges'...) and `text`; a pledge also has a `cost`. search: optional; part of a name, a text, or a
    kind or category ('hazard', 'wager', 'pledges'), any case -- without it, the whole pool. Quote the
    texts, don't paraphrase. A text with {0} gets its number in the game, which the data doesn't show:
    quote it as-is and never state a number from `values`. No match returns `suggestions`. `patch` is the
    game patch the data is from; if the league's is newer, it may be stale. Offline.
    """
    items = load_items()
    if items is None:
        return {**_NO_ITEM_SNAPSHOT}
    return _trial_pool(items, trial, search)


_VENDOR_MODS = ", ".join(k + (" (n)" if "{n}" in v else "") for k, v in vendor_regex.MODS.items())
_VENDOR_REGEX_DOC = f"""Build a Path of Exile 2 vendor search-box regex from what the build wants.

Pure and offline. Paste the returned `regex` into a vendor's search box (Ctrl+F); matching items light
up. It is up to three ANDed groups: hidden classes, wanted mods/classes, and a slot gate.

want: list of {{key, min_value?, any_base?}}, highest priority first. `min_value` is only for mods
  marked (n) below. `any_base: true` lets that mod light up on any base the hide list allows, not just
  the gated slots -- use it for must-haves like movement speed or +minion skill levels.
want_classes: item classes to light up on any roll (e.g. every sceptre for a minion build).
hide_classes: item classes never to light up.
avoid: mod keys that rule an item out whatever else it rolls (e.g. flask_removes_recovery).
item_level: the "Item Level" of the vendor's items (ask the player to hover one). Caps each (n) mod at
  its highest roll there; a want whose min_value can't roll at that level is left out and listed in
  `unreachable`.
slot_classes / slot_defences: the gate -- an item lights only if it is one of these classes or bases,
  or carries an any_base mod. Omit both for no gate.

Over {vendor_regex.LIMIT} characters, the lowest-priority wants are dropped; `dropped` lists them.

Mods: {_VENDOR_MODS}
Classes: {", ".join(vendor_regex.CLASSES)}
Defences: {", ".join(vendor_regex.DEFENCES)}
"""


def _vendor_tiers() -> dict[str, tuple[tuple[int, int], ...]]:
    """Each vendor-regex "{n}" mod's tiers, from the item snapshot; none -- no item-level cap -- without one."""
    items = load_items()
    if items is None:
        return {}
    return {key: top_rolls(items, family) for key, family in vendor_regex.TIER_FAMILIES.items()}


@mcp.tool(description=_VENDOR_REGEX_DOC)
async def build_vendor_regex(
    want: list[dict[str, Any]],
    want_classes: list[str] | None = None,
    hide_classes: list[str] | None = None,
    slot_classes: list[str] | None = None,
    slot_defences: list[str] | None = None,
    avoid: list[str] | None = None,
    item_level: int | None = None,
) -> dict[str, Any]:
    try:
        wants = [
            vendor_regex.Want(key=w["key"], min_value=w.get("min_value"), any_base=bool(w.get("any_base")))
            for w in want
        ]
        out = vendor_regex.build_vendor_regex(
            want=wants,
            want_classes=want_classes or (),
            hide_classes=hide_classes or (),
            slot_classes=slot_classes or (),
            slot_defences=slot_defences or (),
            avoid=avoid or (),
            item_level=item_level,
            tiers=_vendor_tiers(),
        )
    except (KeyError, TypeError) as e:
        return {"valid": False, "error": f"each want needs a 'key': {e!r}"}
    except ValueError as e:
        return {"valid": False, "error": str(e)}
    return {
        "valid": True,
        "regex": out.regex,
        "length": out.length,
        "limit": vendor_regex.LIMIT,
        "dropped": list(out.dropped),
        "unreachable": list(out.unreachable),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
