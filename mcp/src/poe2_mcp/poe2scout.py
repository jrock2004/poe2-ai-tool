"""Typed client for the poe2scout API (https://api.poe2scout.com).

Field shapes are derived from the poe2scout .NET source (handler response records), not guessed.
Coverage: currencies + unique items with prices and history. There is NO rare-item-by-affix search
in this API -- that lives in the separate /trade2 adapter (a later slice).

Etiquette: descriptive User-Agent, in-memory caching (~5 min), gentle throttling (~2 req/s).
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from . import store
from ._cache import CacheEntry, Fetched

BASE = os.environ.get("POE2SCOUT_BASE", "https://api.poe2scout.com")
REALM = os.environ.get("POE2_REALM", "poe2")
# Configured default league. Temp leagues rotate (Forbidden Rites won't last), and poe2scout marks
# *several* leagues IsCurrent at once (SC + HC + event), so "first IsCurrent" is not a safe default.
# The league saved by the set_league tool (store.py) wins over POE2_LEAGUE, so a switch made in chat
# isn't silently overridden by an older env setting; an explicit league= arg still beats both.
DEFAULT_LEAGUE = os.environ.get("POE2_LEAGUE") or None
USER_AGENT = os.environ.get(
    "POE2_USER_AGENT", "poe2-ai-tools (personal; contact: jrock2004@gmail.com)"
)


def exalted_to_divine(exalted: float, divine_price: float) -> float:
    """Convert a price in exalted to divine using divine_price (exalted per divine).

    Returns NaN when divine_price is missing or non-positive so callers can guard on it.
    """
    if not divine_price or divine_price <= 0:
        return float("nan")
    return exalted / divine_price


def rates_from_items(items: list[dict[str, Any]]) -> dict[str, float]:
    """Map currency ApiId -> exalted per unit from a poe2scout /Items list. Pure -- no network.

    ApiIds match the currency ids /trade2 listings are priced in ('divine', 'exalted', 'chaos', ...),
    so this is the conversion table for trade prices. Uniques (ApiId null) and unpriced rows are
    skipped, never guessed.
    """
    return {
        it["ApiId"]: it["CurrentPrice"]
        for it in items
        if it.get("ApiId") and it.get("CurrentPrice") is not None
    }


def price_trend(logs: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Summarize a poe2scout `PriceLogs` series (daily {Price, Time, Quantity}). Pure -- no network.

    Returns {days, minExalted, maxExalted, changePct} over the points that have a Price, or None if
    there are none. Points are ordered by Time (ISO-8601), not by input order. changePct is the
    oldest -> newest change in percent; None with fewer than 2 points or an oldest price <= 0.
    """
    points = sorted(
        (lg for lg in logs or [] if lg.get("Price") is not None),
        key=lambda lg: lg.get("Time") or "",  # one ISO-8601 format per series, so text order works
    )
    if not points:
        return None
    prices = [lg["Price"] for lg in points]
    oldest, newest = prices[0], prices[-1]
    return {
        "days": len(prices),
        "minExalted": min(prices),
        "maxExalted": max(prices),
        "changePct": 100 * (newest - oldest) / oldest if len(prices) >= 2 and oldest > 0 else None,
    }


def change_vs_divine(item_change_pct: float | None, divine_change_pct: float | None) -> float | None:
    """An item's percent change measured in divine rather than exalted. Pure.

    Prices are quoted in exalted, so a raw change mixes "the item moved" with "exalted moved"; when
    exalted weakens, everything looks like it rose. Dividing out divine's own change over the same
    window leaves the item's real move: (1 + item%) / (1 + divine%) - 1. None if either is None or
    divine's change is <= -100%.
    """
    if item_change_pct is None or divine_change_pct is None or divine_change_pct <= -100:
        return None
    return 100 * ((1 + item_change_pct / 100) / (1 + divine_change_pct / 100) - 1)


def rank_movers(
    items: list[dict[str, Any]],
    divine_change_pct: float | None,
    min_quantity: int = 50,
    top: int = 5,
) -> dict[str, Any]:
    """Rank one category's poe2scout items by their 7-day move measured in divine. Pure.

    items: raw ByCategory items (Text, ApiId, CurrentPrice, CurrentQuantity, PriceLogs).
    Items listed fewer than `min_quantity` times (or with unknown quantity) are skipped as thin --
    a thin market's move is noise -- and counted in `thin`. Items with no usable divine-relative
    change (no history, or divine's own change unknown) are counted in `noTrend`. Of the rest,
    `risers` are the `top` biggest positive changePctVsDivine (largest first) and `fallers` the
    `top` biggest negative (most negative first); exactly 0 is neither. Ties break by name.
    Entries: {name, apiId, priceExalted, quantityListed, changePct, changePctVsDivine} (unrounded).
    """
    ranked: list[dict[str, Any]] = []
    thin = no_trend = 0
    for it in items:
        qty = it.get("CurrentQuantity")
        if qty is None or qty < min_quantity:
            thin += 1
            continue
        trend = price_trend(it.get("PriceLogs"))
        vs_divine = change_vs_divine(trend["changePct"] if trend else None, divine_change_pct)
        if vs_divine is None:
            no_trend += 1
            continue
        ranked.append({
            "name": it.get("Text"),
            "apiId": it.get("ApiId"),
            "priceExalted": it.get("CurrentPrice"),
            "quantityListed": qty,
            "changePct": trend["changePct"] if trend else None,
            "changePctVsDivine": vs_divine,
        })
    risers = sorted((m for m in ranked if m["changePctVsDivine"] > 0),
                    key=lambda m: (-m["changePctVsDivine"], m["name"] or ""))
    fallers = sorted((m for m in ranked if m["changePctVsDivine"] < 0),
                     key=lambda m: (m["changePctVsDivine"], m["name"] or ""))
    return {"risers": risers[:top], "fallers": fallers[:top], "thin": thin, "noTrend": no_trend}


def value_holdings(
    items: list[dict[str, Any]],
    holdings: list[dict[str, Any]],
    divine_price: float,
) -> dict[str, Any]:
    """Value a list of holdings against a poe2scout /Items list. Pure -- no network.

    items: raw scout /Items dicts (uniques + currencies, each with CurrentPrice in exalted;
        Exalted Orb itself is 1). holdings: [{name, count}]. Matched by exact (case-insensitive)
        Name or Text. Unmatched or unpriced names are reported, never guessed. Totals are exalted
        (the base unit) and its divine equivalent.
    """
    index: dict[str, dict[str, Any]] = {}
    for it in items:
        for key in (it.get("Name"), it.get("Text")):
            if key:
                index.setdefault(key.strip().lower(), it)

    lines: list[dict[str, Any]] = []
    unmatched: list[str] = []
    total_ex = 0.0
    for h in holdings:
        name = (h.get("name") or "").strip()
        count = h.get("count") or 0
        hit = index.get(name.lower())
        price = hit.get("CurrentPrice") if hit else None
        if hit is None or price is None:
            unmatched.append(name)
            continue
        value_ex = count * price
        total_ex += value_ex
        lines.append(
            {
                "name": hit.get("Name") or hit.get("Text"),
                "count": count,
                "unitExalted": price,
                "valueExalted": value_ex,
                "valueDivine": exalted_to_divine(value_ex, divine_price),
            }
        )
    return {
        "lines": lines,
        "unmatched": unmatched,
        "totalExalted": total_ex,
        "totalDivine": exalted_to_divine(total_ex, divine_price),
    }


class Poe2ScoutClient:
    def __init__(
        self,
        min_gap_s: float = 0.5,
        ttl_s: float = 300.0,
        transport: httpx.AsyncBaseTransport | None = None,  # tests pass an httpx.MockTransport
    ) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._last_request = 0.0
        self._min_gap_s = min_gap_s  # ~2 req/s
        self._ttl_s = ttl_s          # 5 min, matches upstream cache
        self._client = httpx.AsyncClient(
            base_url=BASE,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=30.0,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str) -> Fetched[Any]:
        hit = self._cache.get(path)
        now = time.monotonic()
        if hit and hit.expires > now:
            return hit.fetched

        gap = self._last_request + self._min_gap_s - now
        if gap > 0:
            await asyncio.sleep(gap)
        self._last_request = time.monotonic()

        resp = await self._client.get(path)
        if resp.status_code != 200:
            raise RuntimeError(f"poe2scout {path} -> HTTP {resp.status_code} {resp.reason_phrase}")
        fetched = Fetched(body=resp.json(), fetched_at=time.time())
        self._cache[path] = CacheEntry(expires=time.monotonic() + self._ttl_s, fetched=fetched)
        return fetched

    async def get_leagues(self) -> Fetched[list[dict[str, Any]]]:
        """GET /{realm}/Leagues -> list of leagues.

        Each has: Value, ShortName, IsCurrent, DivinePrice (exalted per divine), and currency texts.
        """
        return await self._get(f"/{REALM}/Leagues")

    async def resolve_league(self, league: str | None = None) -> Fetched[dict[str, Any]]:
        """Return a league dict, stamped with when the league list was fetched.

        Precedence: explicit ``league`` arg -> saved league (``set_league``, read per call) ->
        configured ``POE2_LEAGUE`` -> first IsCurrent -> first. The IsCurrent fallback is last-resort
        only: poe2scout marks SC/HC/event leagues current at once, so relying on array order is
        unsafe -- prefer saving a league.
        """
        fetched = await self.get_leagues()
        leagues = fetched.body
        if not leagues:
            raise RuntimeError("poe2scout returned no leagues")

        saved = store.read_config(store.data_dir()).get("league")
        if league:
            wanted, source = league, "league argument"
        elif saved:
            wanted, source = saved, "saved league"
        else:
            wanted, source = DEFAULT_LEAGUE, "POE2_LEAGUE"
        if wanted:
            needle = wanted.lower()
            for lg in leagues:
                if lg.get("Value", "").lower() == needle or lg.get("ShortName", "").lower() == needle:
                    return Fetched(body=lg, fetched_at=fetched.fetched_at)
            available = ", ".join(lg.get("Value", "?") for lg in leagues)
            raise RuntimeError(f'League "{wanted}" ({source}) not found. Available: {available}')

        current = next((lg for lg in leagues if lg.get("IsCurrent")), leagues[0])
        return Fetched(body=current, fetched_at=fetched.fetched_at)

    async def get_currencies_by_category(
        self,
        league_value: str,
        category: str,
        search: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> Fetched[dict[str, Any]]:
        params: dict[str, str] = {"category": category, "page": str(page), "perPage": str(per_page)}
        if search:
            params["search"] = search
        league = quote(league_value, safe="")
        return await self._get(
            f"/{REALM}/Leagues/{league}/Currencies/ByCategory?{urlencode(params)}"
        )

    async def get_items(self, league_value: str) -> Fetched[list[dict[str, Any]]]:
        """GET /{realm}/Leagues/{league}/Items -> flat list of uniques + currencies with CurrentPrice."""
        return await self._get(f"/{REALM}/Leagues/{quote(league_value, safe='')}/Items")
