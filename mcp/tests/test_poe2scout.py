import asyncio
import math

import httpx

from poe2_mcp._cache import Fetched
from poe2_mcp.poe2scout import Poe2ScoutClient, exalted_to_divine, rates_from_items


def test_exalted_to_divine_converts():
    assert exalted_to_divine(300, 150) == 2.0   # 300 exalted / 150 exalted-per-divine
    assert exalted_to_divine(75, 150) == 0.5


def test_exalted_to_divine_guards_bad_price():
    assert math.isnan(exalted_to_divine(300, 0))
    assert math.isnan(exalted_to_divine(300, -5))


def test_rates_from_items_maps_currency_apiids_and_skips_uniques_and_unpriced():
    items = [
        {"ApiId": "exalted", "Text": "Exalted Orb", "CurrentPrice": 1},
        {"ApiId": "divine", "Text": "Divine Orb", "CurrentPrice": 504.23},
        {"ApiId": "chaos", "Text": "Chaos Orb", "CurrentPrice": 61.6},
        {"ApiId": None, "Name": "Igniferis", "Text": "Igniferis Crimson Amulet", "CurrentPrice": 1},
        {"ApiId": "mirror", "Text": "Mirror of Kalandra", "CurrentPrice": None},
    ]
    assert rates_from_items(items) == {"exalted": 1, "divine": 504.23, "chaos": 61.6}


LEAGUES = [{"Value": "Forbidden Rites", "ShortName": "FR", "IsCurrent": True, "DivinePrice": 500}]


async def _offline_client(calls: list[str]) -> Poe2ScoutClient:
    """A client whose HTTP goes to an in-memory transport serving LEAGUES; records each request path."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=LEAGUES)

    client = Poe2ScoutClient(min_gap_s=0)
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url="https://scout.test", transport=httpx.MockTransport(handler))
    return client


def test_cache_hit_returns_original_fetched_at_without_refetching():
    calls: list[str] = []

    async def run():
        client = await _offline_client(calls)
        first = await client.get_leagues()
        second = await client.get_leagues()
        await client.aclose()
        return first, second

    first, second = asyncio.run(run())
    assert isinstance(first, Fetched)
    assert first.body == LEAGUES
    assert second.fetched_at == first.fetched_at
    assert calls == ["/poe2/Leagues"]


def test_resolve_league_carries_the_leagues_fetch_time():
    calls: list[str] = []

    async def run():
        client = await _offline_client(calls)
        leagues = await client.get_leagues()
        league = await client.resolve_league("Forbidden Rites")
        await client.aclose()
        return leagues, league

    leagues, league = asyncio.run(run())
    assert isinstance(league, Fetched)
    assert league.body["Value"] == "Forbidden Rites"
    assert league.fetched_at == leagues.fetched_at
