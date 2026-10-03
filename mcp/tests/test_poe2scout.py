import asyncio
import math

import httpx
import pytest

from poe2_mcp import poe2scout
from poe2_mcp._cache import Fetched
from poe2_mcp.poe2scout import (
    Poe2ScoutClient,
    change_vs_divine,
    exalted_to_divine,
    price_trend,
    rates_from_items,
)


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


def _offline_client(calls: list[str], leagues: list[dict] = LEAGUES) -> Poe2ScoutClient:
    """A client whose HTTP goes to an in-memory transport serving `leagues`; records each request path."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=leagues)

    return Poe2ScoutClient(min_gap_s=0, transport=httpx.MockTransport(handler))


def test_cache_hit_returns_original_fetched_at_without_refetching():
    calls: list[str] = []

    async def run():
        client = _offline_client(calls)
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
        client = _offline_client(calls)
        leagues = await client.get_leagues()
        league = await client.resolve_league("Forbidden Rites")
        await client.aclose()
        return leagues, league

    leagues, league = asyncio.run(run())
    assert isinstance(league, Fetched)
    assert league.body["Value"] == "Forbidden Rites"
    assert league.fetched_at == leagues.fetched_at


# SC + HC + an old league, as poe2scout really returns them: several marked current at once, and the
# first entry is not current -- so "first league" and "first current league" give different answers.
MULTI = [
    {"Value": "Standard", "ShortName": "Std", "IsCurrent": False},
    {"Value": "Forbidden Rites", "ShortName": "FR", "IsCurrent": True},
    {"Value": "HC Forbidden Rites", "ShortName": "HCFR", "IsCurrent": True},
]


def _resolve(monkeypatch, leagues: list[dict], league: str | None, configured: str | None) -> str:
    """resolve_league(league) with POE2_LEAGUE set to `configured`; returns the chosen league's Value."""
    monkeypatch.setattr(poe2scout, "DEFAULT_LEAGUE", configured)

    async def run():
        client = _offline_client([], leagues)
        try:
            return (await client.resolve_league(league)).body["Value"]
        finally:
            await client.aclose()

    return asyncio.run(run())


def test_resolve_league_explicit_argument_beats_configured(monkeypatch):
    assert _resolve(monkeypatch, MULTI, "Standard", configured="Forbidden Rites") == "Standard"


def test_resolve_league_uses_configured_when_no_argument(monkeypatch):
    assert _resolve(monkeypatch, MULTI, None, configured="HC Forbidden Rites") == "HC Forbidden Rites"


def test_resolve_league_matches_short_name_case_insensitively(monkeypatch):
    assert _resolve(monkeypatch, MULTI, "hcfr", configured=None) == "HC Forbidden Rites"


def test_resolve_league_falls_back_to_first_current_not_first_listed(monkeypatch):
    assert _resolve(monkeypatch, MULTI, None, configured=None) == "Forbidden Rites"


def test_resolve_league_falls_back_to_first_listed_when_none_current(monkeypatch):
    none_current = [dict(lg, IsCurrent=False) for lg in MULTI]
    assert _resolve(monkeypatch, none_current, None, configured=None) == "Standard"


def test_resolve_league_unknown_names_its_source_and_the_options(monkeypatch):
    with pytest.raises(RuntimeError, match=r"POE2_LEAGUE.*Standard, Forbidden Rites, HC Forbidden Rites"):
        _resolve(monkeypatch, MULTI, None, configured="Dawn of the Hunt")
    with pytest.raises(RuntimeError, match="league argument"):
        _resolve(monkeypatch, MULTI, "Dawn of the Hunt", configured=None)


def test_resolve_league_with_no_leagues_raises(monkeypatch):
    with pytest.raises(RuntimeError, match="no leagues"):
        _resolve(monkeypatch, [], None, configured=None)


def _log(day: int, price):
    return {"Price": price, "Time": f"2026-09-{day:02d}T00:00:00.0000000Z", "Quantity": 1000}


def test_price_trend_orders_by_time_not_input_order():
    # poe2scout sends newest first; the trend must still run oldest -> newest.
    trend = price_trend([_log(22, 520.0), _log(21, 500.0), _log(20, 480.0)])
    assert trend["days"] == 3
    assert trend["minExalted"] == 480.0
    assert trend["maxExalted"] == 520.0
    assert trend["changePct"] == pytest.approx(100 * (520 - 480) / 480)


def test_price_trend_skips_points_without_a_price():
    trend = price_trend([_log(22, 510.0), _log(21, None), _log(20, 500.0)])
    assert trend["days"] == 2
    assert trend["changePct"] == pytest.approx(2.0)


def test_price_trend_single_point_has_no_change():
    trend = price_trend([_log(22, 500.0)])
    assert trend == {"days": 1, "minExalted": 500.0, "maxExalted": 500.0, "changePct": None}


def test_price_trend_zero_oldest_price_has_no_change():
    assert price_trend([_log(21, 0.0), _log(22, 5.0)])["changePct"] is None


@pytest.mark.parametrize("logs", [None, [], [_log(22, None)]])
def test_price_trend_with_no_priced_points_is_none(logs):
    assert price_trend(logs) is None


def test_change_vs_divine_removes_exalted_inflation():
    # Mirror +54.5% in exalted while divine rose 12.4% in exalted -> ~+37.5% in divine terms.
    assert change_vs_divine(54.5, 12.4) == pytest.approx(100 * (1.545 / 1.124 - 1))


def test_change_vs_divine_is_zero_when_moving_with_divine():
    assert change_vs_divine(12.4, 12.4) == pytest.approx(0.0)


def test_change_vs_divine_can_turn_a_rise_into_a_fall():
    assert change_vs_divine(5.0, 10.0) == pytest.approx(100 * (1.05 / 1.10 - 1))  # ~ -4.5%


@pytest.mark.parametrize("item, divine", [(None, 10.0), (10.0, None), (None, None), (10.0, -100.0)])
def test_change_vs_divine_is_none_without_both_changes(item, divine):
    assert change_vs_divine(item, divine) is None
