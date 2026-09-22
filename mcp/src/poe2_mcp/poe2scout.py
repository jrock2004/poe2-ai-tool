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

from ._cache import CacheEntry, Fetched

BASE = os.environ.get("POE2SCOUT_BASE", "https://api.poe2scout.com")
REALM = os.environ.get("POE2_REALM", "poe2")
# Configured default league. Temp leagues rotate (Forbidden Rites won't last), and poe2scout marks
# *several* leagues IsCurrent at once (SC + HC + event), so "first IsCurrent" is not a safe default.
# Set POE2_LEAGUE to pin the default; an explicit league= arg on any call still overrides it.
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
    def __init__(self, min_gap_s: float = 0.5, ttl_s: float = 300.0) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._last_request = 0.0
        self._min_gap_s = min_gap_s  # ~2 req/s
        self._ttl_s = ttl_s          # 5 min, matches upstream cache
        self._client = httpx.AsyncClient(
            base_url=BASE,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=30.0,
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

        Precedence: explicit ``league`` arg -> configured ``POE2_LEAGUE`` -> first IsCurrent -> first.
        The IsCurrent fallback is last-resort only: poe2scout marks SC/HC/event leagues current at
        once, so relying on array order is unsafe -- prefer setting POE2_LEAGUE.
        """
        fetched = await self.get_leagues()
        leagues = fetched.body
        if not leagues:
            raise RuntimeError("poe2scout returned no leagues")

        wanted = league or DEFAULT_LEAGUE
        if wanted:
            needle = wanted.lower()
            for lg in leagues:
                if lg.get("Value", "").lower() == needle or lg.get("ShortName", "").lower() == needle:
                    return Fetched(body=lg, fetched_at=fetched.fetched_at)
            available = ", ".join(lg.get("Value", "?") for lg in leagues)
            source = "league argument" if league else "POE2_LEAGUE"
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
