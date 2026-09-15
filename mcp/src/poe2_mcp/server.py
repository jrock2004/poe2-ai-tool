"""poe2-mcp -- thin MCP server exposing live Path of Exile 2 market data to the assistant skills.

Phase 1 surface: poe2scout for currency + unique pricing (get_leagues, get_currency_prices,
price_unique) and a read-only GGG /trade2 adapter for rare-item search + filter generation
(find_stat_filters, build_trade_filter, search_trade). OAuth character reading is deferred -- GGG
is not issuing new API clients (see mcp/README.md).

Run: `poe2-mcp` (installed script) or `python -m poe2_mcp.server` -- stdio transport; register in
your MCP client.
"""
from __future__ import annotations

import math
from typing import Any

from mcp.server.fastmcp import FastMCP

from .poe2scout import Poe2ScoutClient, exalted_to_divine, value_holdings
from .trade2 import StatFilter, Trade2Client, build_query, summarize_listing, human_search_url

mcp = FastMCP("poe2-mcp")
_scout = Poe2ScoutClient()
_trade = Trade2Client()


def _round(n: float, places: int) -> float | None:
    if n is None or not math.isfinite(n):
        return None
    return round(n, places)


@mcp.tool()
async def get_leagues() -> list[dict[str, Any]]:
    """List Path of Exile 2 leagues from poe2scout.

    Includes which league is current and the current divine price (in exalted). Use this to
    discover the league name the other tools accept.
    """
    leagues = await _scout.get_leagues()
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
async def get_currency_prices(
    category: str,
    search: str | None = None,
    league: str | None = None,
    per_page: int = 25,
) -> dict[str, Any]:
    """Get current Path of Exile 2 currency prices for a category.

    category: currency category apiId, e.g. 'currency', 'essence', 'runes', 'catalysts'.
    search: optional name filter, e.g. 'divine' or 'chaos'.
    league: league value; defaults to the current league.
    Prices are returned in both exalted and divine. Currency/uniques only -- no rare-affix search.
    """
    resolved = await _scout.resolve_league(league)
    divine_price = resolved.get("DivinePrice") or 0
    resp = await _scout.get_currencies_by_category(
        resolved["Value"], category, search=search, per_page=per_page
    )
    items = []
    for c in resp.get("Items", []):
        price_ex = c.get("CurrentPrice")
        items.append(
            {
                "name": c.get("Text"),
                "apiId": c.get("ApiId"),
                "priceExalted": price_ex,
                "priceDivine": None
                if price_ex is None
                else _round(exalted_to_divine(price_ex, divine_price), 4),
                "quantityListed": c.get("CurrentQuantity"),
            }
        )
    return {
        "league": resolved["Value"],
        "divinePriceInExalted": divine_price,
        "total": resp.get("Total"),
        "page": resp.get("CurrentPage"),
        "pages": resp.get("Pages"),
        "items": items,
        "note": "poe2scout reference prices (cached ~5 min). Currency/uniques only; no rare-affix search here.",
    }


@mcp.tool()
async def price_unique(name: str, league: str | None = None) -> dict[str, Any]:
    """Look up the current price of a Path of Exile 2 unique item (or currency) by name.

    Matches against poe2scout's priced item list. Returns price in exalted and divine, plus
    close-name suggestions when there's no exact match.
    """
    resolved = await _scout.resolve_league(league)
    divine_price = resolved.get("DivinePrice") or 0
    items = await _scout.get_items(resolved["Value"])
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
    resolved = await _scout.resolve_league(league)
    divine_price = resolved.get("DivinePrice") or 0
    items = await _scout.get_items(resolved["Value"])
    valued = value_holdings(items, holdings, divine_price)
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
    the match. Offline reference lookup (cached); makes no trade search.
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
) -> dict[str, Any]:
    """Build a Path of Exile 2 /trade2 search body from filters, WITHOUT running a live search.

    Pure construction -- safe, no rate limit, no account contact. Use it to show the player the exact
    filter, or hand the returned 'query' to search_trade to run it.

    category: type option like 'armour.boots', 'weapon.crossbow', 'accessory.ring', 'jewel'.
    stats: list of {id, min?, max?}; get ids from find_stat_filters.
    max_price: optional ceiling in price_currency (e.g. your currency budget).
    """
    query = build_query(
        stats=_stat_filters_from(stats),
        category=category,
        max_price=max_price,
        price_currency=price_currency,
        online_only=online_only,
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
    Rate-limited and cached; it never buys, lists, or whispers on your behalf -- you act.
    """
    resolved = await _scout.resolve_league(league)
    league_id = resolved["Value"]
    limit = max(1, min(limit, 20))

    result = await _trade.search(league_id, query)
    query_id = result.get("id")
    hashes = result.get("result") or []
    total = len(hashes)
    listings: list[dict[str, Any]] = []
    if query_id and hashes:
        entries = await _trade.fetch(query_id, hashes[:limit])
        listings = [summarize_listing(e) for e in entries]

    return {
        "league": league_id,
        "url": human_search_url(league_id, query_id) if query_id else None,
        "matched": total,
        "shown": len(listings),
        "listings": listings,
        "note": (
            "Read-only trade search (cached). Open 'url' to browse/whisper yourself; the tool never "
            "contacts sellers. 0 matches means the filter is too tight -- widen it and search again."
            if total else
            "No listings matched. Loosen the filters (drop a min, allow offline, raise the price cap)."
        ),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
