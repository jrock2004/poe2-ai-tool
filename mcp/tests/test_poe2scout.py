import asyncio
import math
import time

import httpx
import pytest

from poe2_mcp import poe2scout
from poe2_mcp._cache import Fetched
from poe2_mcp.store import data_dir, write_config
from poe2_mcp.poe2scout import (
    Poe2ScoutClient,
    change_vs_divine,
    exalted_to_divine,
    price_trend,
    rank_movers,
    rates_from_items,
)


@pytest.fixture(autouse=True)
def _isolated_data_dir(monkeypatch, tmp_path):
    """resolve_league reads the saved league; never let a test see the real per-user data dir."""
    monkeypatch.setenv("POE2_DATA_DIR", str(tmp_path))
    return tmp_path


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


def _resolve(
    monkeypatch,
    leagues: list[dict],
    league: str | None,
    configured: str | None,
    saved: str | None = None,
) -> str:
    """resolve_league(league) with POE2_LEAGUE set to `configured` and `saved` in the data dir's config;
    returns the chosen league's Value."""
    monkeypatch.setattr(poe2scout, "DEFAULT_LEAGUE", configured)
    if saved is not None:
        write_config(data_dir(), {"league": saved})

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


def test_resolve_league_saved_league_beats_configured(monkeypatch):
    assert _resolve(monkeypatch, MULTI, None, configured="Forbidden Rites", saved="Standard") == "Standard"


def test_resolve_league_explicit_argument_beats_saved(monkeypatch):
    assert _resolve(monkeypatch, MULTI, "HCFR", configured=None, saved="Standard") == "HC Forbidden Rites"


def test_resolve_league_unknown_saved_league_names_its_source_and_the_options(monkeypatch):
    with pytest.raises(RuntimeError, match=r"saved league.*Standard, Forbidden Rites, HC Forbidden Rites"):
        _resolve(monkeypatch, MULTI, None, configured="Forbidden Rites", saved="Dawn of the Hunt")


def test_resolve_league_with_no_leagues_raises(monkeypatch):
    with pytest.raises(RuntimeError, match="no leagues"):
        _resolve(monkeypatch, [], None, configured=None)


# poe2scout down: the league list can't be fetched. A named league (argument, saved, POE2_LEAGUE) is
# used unchecked, so tools that don't need poe2scout's data -- trade search -- keep working. A name the
# list doesn't have still raises (tests above): the fallback is only for a list we couldn't get.
def _http_503(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503)


def _unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def _html_page(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="<html>Just a moment...</html>")


def _no_leagues(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def _resolve_when_down(
    monkeypatch, handler, league: str | None = None, saved: str | None = None,
    configured: str | None = None, strict: bool = False,
) -> Fetched:
    """resolve_league against a poe2scout whose every request goes to `handler`."""
    monkeypatch.setattr(poe2scout, "DEFAULT_LEAGUE", configured)
    if saved is not None:
        write_config(data_dir(), {"league": saved})

    async def run():
        client = Poe2ScoutClient(min_gap_s=0, transport=httpx.MockTransport(handler))
        try:
            return await client.resolve_league(league, strict=strict)
        finally:
            await client.aclose()

    return asyncio.run(run())


@pytest.mark.parametrize("handler", [_http_503, _unreachable, _html_page, _no_leagues])
def test_resolve_league_uses_the_saved_league_unchecked_when_poe2scout_is_down(monkeypatch, handler):
    league = _resolve_when_down(monkeypatch, handler, saved="Forbidden Rites")
    assert league.body == {"Value": "Forbidden Rites", "Unchecked": True}
    assert abs(league.fetched_at - time.time()) < 60  # stamped now, so it doesn't age the answer


def test_resolve_league_down_prefers_the_argument_to_the_saved_league(monkeypatch):
    league = _resolve_when_down(monkeypatch, _http_503, "Standard", saved="Forbidden Rites")
    assert league.body["Value"] == "Standard"


def test_resolve_league_down_falls_back_to_poe2_league(monkeypatch):
    assert _resolve_when_down(monkeypatch, _http_503, configured="HC Forbidden Rites").body["Value"] == "HC Forbidden Rites"


def test_resolve_league_down_with_no_league_named_still_raises(monkeypatch):
    # Nothing to fall back to: picking "the first current league" needs the list itself.
    with pytest.raises(RuntimeError, match="HTTP 503"):
        _resolve_when_down(monkeypatch, _http_503)


def test_resolve_league_strict_raises_when_poe2scout_is_down(monkeypatch):
    # set_league passes strict=True: it must never save a name nothing has checked.
    with pytest.raises(RuntimeError, match="HTTP 503"):
        _resolve_when_down(monkeypatch, _http_503, saved="Forbidden Rites", strict=True)


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


def test_price_trend_skips_null_entries():
    # Live shape since 2026-10-06: poe2scout sends a null first entry, then the logs newest first.
    trend = price_trend([None, _log(22, 510.0), _log(21, 505.0), _log(20, 500.0)])
    assert trend["days"] == 3
    assert trend["changePct"] == pytest.approx(2.0)


def test_price_trend_single_point_has_no_change():
    trend = price_trend([_log(22, 500.0)])
    assert trend == {"days": 1, "minExalted": 500.0, "maxExalted": 500.0, "changePct": None}


def test_price_trend_zero_oldest_price_has_no_change():
    assert price_trend([_log(21, 0.0), _log(22, 5.0)])["changePct"] is None


@pytest.mark.parametrize("logs", [None, [], [_log(22, None)], [None]])
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


def _cat_item(name: str, qty, prices: list[float] | None) -> dict:
    """A ByCategory item; `prices` run oldest -> newest (sent newest-first, as poe2scout does)."""
    logs = None if prices is None else [_log(20 + i, p) for i, p in enumerate(prices)][::-1]
    return {"Text": name, "ApiId": name.lower(), "CurrentPrice": prices[-1] if prices else None,
            "CurrentQuantity": qty, "PriceLogs": logs}


MOVER_ITEMS = [
    _cat_item("Alpha", 500, [100, 150]),   # +50% exalted -> +36.4% vs divine (+10%)
    _cat_item("Bravo", 500, [100, 110]),   # moved exactly with divine -> 0, neither list
    _cat_item("Charlie", 500, [100, 80]),  # -20% exalted -> -27.3% vs divine
    _cat_item("Delta", 500, [100, 121]),   # +21% exalted -> +10% vs divine
    _cat_item("Echo", 10, [100, 300]),     # big move but thin -> skipped
    _cat_item("Foxtrot", None, [100, 300]),  # unknown depth -> skipped as thin
    _cat_item("Golf", 500, None),          # no history -> noTrend
]


def test_rank_movers_orders_risers_and_fallers_by_divine_relative_change():
    movers = rank_movers(MOVER_ITEMS, divine_change_pct=10.0)
    assert [m["name"] for m in movers["risers"]] == ["Alpha", "Delta"]
    assert [m["name"] for m in movers["fallers"]] == ["Charlie"]
    alpha = movers["risers"][0]
    assert alpha["changePct"] == pytest.approx(50.0)
    assert alpha["changePctVsDivine"] == pytest.approx(100 * (1.5 / 1.1 - 1))
    assert alpha["quantityListed"] == 500 and alpha["priceExalted"] == 150


def test_rank_movers_counts_what_it_skipped():
    movers = rank_movers(MOVER_ITEMS, divine_change_pct=10.0)
    assert movers["thin"] == 2      # Echo (10 listed), Foxtrot (unknown)
    assert movers["noTrend"] == 1   # Golf


def test_rank_movers_respects_top():
    movers = rank_movers(MOVER_ITEMS, divine_change_pct=10.0, top=1)
    assert [m["name"] for m in movers["risers"]] == ["Alpha"]


def test_rank_movers_without_divine_change_ranks_nothing():
    # Without divine's own change there's no inflation-free number, and the rubric says not to
    # fall back to raw exalted changes -- so nothing is ranked, and every deep item is noTrend.
    movers = rank_movers(MOVER_ITEMS, divine_change_pct=None)
    assert movers["risers"] == [] and movers["fallers"] == []
    assert movers["noTrend"] == 5 and movers["thin"] == 2
