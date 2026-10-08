"""Unit tests for GGG's Currency Exchange client and its rate math (pure, no network)."""
import asyncio
import gzip
import json

import httpx
import pytest

from poe2_mcp.exchange import (
    EXALTED, ExchangeClient, exalted_rates, exchange_moves, previous_hour, value_on_exchange,
)

DIVINE = "Metadata/Items/Currency/CurrencyModValues"
CHAOS = "Metadata/Items/Currency/CurrencyRerollRare"
OMEN = "Metadata/Items/Currency/OmenRogueExileSummonsPartyMember"
ESSENCE = "Metadata/Items/Currency/CurrencyEssenceRarity"
THESIS = "Metadata/Items/SoulCores/ThesisOfExperiments"

# Real markets from the hour 2026-10-07 00:00 UTC, trimmed to the fields the rate math reads. The pair
# order is the API's own (sorted by an internal hash), so exalted comes first in some markets.
MARKETS = [
    {"league": "Forbidden Rites", "market_pair": [DIVINE, EXALTED], "volume_traded": {DIVINE: 1081, EXALTED: 747105}},
    {"league": "Forbidden Rites", "market_pair": [CHAOS, EXALTED], "volume_traded": {CHAOS: 2721, EXALTED: 179044}},
    {"league": "Forbidden Rites", "market_pair": [CHAOS, DIVINE], "volume_traded": {CHAOS: 668005, DIVINE: 64139}},
    {"league": "Forbidden Rites", "market_pair": [EXALTED, OMEN], "volume_traded": {EXALTED: 596, OMEN: 11}},
    {"league": "Forbidden Rites", "market_pair": [THESIS, DIVINE], "volume_traded": {THESIS: 1, DIVINE: 3}},
    {"league": "Forbidden Rites", "market_pair": [ESSENCE, EXALTED], "volume_traded": {ESSENCE: 0, EXALTED: 0}},
    {"league": "Runes of Aldur", "market_pair": [DIVINE, EXALTED], "volume_traded": {DIVINE: 136, EXALTED: 70262}},
]


def test_exalted_rates_cover_items_with_a_traded_market_in_the_league():
    # Not exalted itself, not the essence whose market traded nothing (677 of 2,521 markets didn't
    # that hour), and nothing from another league's markets.
    assert set(exalted_rates(MARKETS, "Forbidden Rites")) == {DIVINE, CHAOS, OMEN, THESIS}


def test_exalted_rates_price_an_item_from_its_market_against_exalted():
    # Volume-weighted over the hour: exalted traded / units traded. These markets carry no ratio range.
    rates = exalted_rates(MARKETS, "Forbidden Rites")
    assert rates[DIVINE] == {"exaltedPerUnit": pytest.approx(747105 / 1081), "volume": 1081, "via": "exalted",
                             "lowExalted": None, "highExalted": None}
    assert rates[OMEN] == {"exaltedPerUnit": pytest.approx(596 / 11), "volume": 11, "via": "exalted",
                           "lowExalted": None, "highExalted": None}


def test_exalted_rates_prefer_an_items_exalted_market_to_the_route_through_divine():
    # Chaos trades against both. Its own exalted market wins (through divine it'd be ~66.3, near 65.8).
    assert exalted_rates(MARKETS, "Forbidden Rites")[CHAOS]["exaltedPerUnit"] == pytest.approx(179044 / 2721)


def test_exalted_rates_price_an_item_traded_only_against_divine_through_divine():
    # Expensive items often trade only against divine (100 of them that hour): divine per unit, times
    # divine's own exalted rate.
    thesis = exalted_rates(MARKETS, "Forbidden Rites")[THESIS]
    assert thesis == {"exaltedPerUnit": pytest.approx(3 * 747105 / 1081), "volume": 1, "via": "divine",
                      "lowExalted": None, "highExalted": None}


def test_exalted_rates_read_only_the_given_league():
    assert exalted_rates(MARKETS, "Runes of Aldur") == {
        DIVINE: {"exaltedPerUnit": pytest.approx(70262 / 136), "volume": 136, "via": "exalted",
                 "lowExalted": None, "highExalted": None}}


# Real markets from the hour ending 2026-10-08 14:00 local, with the ratio range the API gives beside the
# volumes. John's in-game market ratios at that time (exalted each): Greater Jeweller's Orb 5, Gemcutter's
# Prism 9, Esh's Catalyst 28, Divine Orb 750 -- the high end of each range, not the volume-weighted rate.
# Gemcutter's pair is flipped to put exalted first, as the API does for some markets.
JEWELLER = "Metadata/Items/Currency/CurrencyAddSkillGemSocket4"
GEMCUTTER = "Metadata/Items/Currency/CurrencyGemQuality"
RANGED = [
    {"league": "Forbidden Rites", "market_pair": [DIVINE, EXALTED], "volume_traded": {DIVINE: 1416, EXALTED: 1077202},
     "lowest_ratio": {DIVINE: 1, EXALTED: 776}, "highest_ratio": {DIVINE: 1, EXALTED: 690}},
    {"league": "Forbidden Rites", "market_pair": [JEWELLER, EXALTED], "volume_traded": {JEWELLER: 926, EXALTED: 1420},
     "lowest_ratio": {JEWELLER: 2, EXALTED: 7}, "highest_ratio": {JEWELLER: 1, EXALTED: 1}},
    {"league": "Forbidden Rites", "market_pair": [EXALTED, GEMCUTTER],
     "volume_traded": {GEMCUTTER: 2104, EXALTED: 17331},
     "lowest_ratio": {GEMCUTTER: 1, EXALTED: 9}, "highest_ratio": {GEMCUTTER: 1, EXALTED: 7}},
    {"league": "Forbidden Rites", "market_pair": [THESIS, DIVINE], "volume_traded": {THESIS: 2, DIVINE: 5},
     "lowest_ratio": {THESIS: 1, DIVINE: 2}, "highest_ratio": {THESIS: 1, DIVINE: 3}},
]


def test_exalted_rates_give_the_hours_range_in_exalted_each():
    # The API's names don't say which end is cheaper (each is a units-to-units pair), so the range is the
    # lower and higher of the two, in exalted per unit, whichever side of the pair exalted is on.
    rates = exalted_rates(RANGED, "Forbidden Rites")
    assert (rates[JEWELLER]["lowExalted"], rates[JEWELLER]["highExalted"]) == (1, 3.5)
    assert (rates[GEMCUTTER]["lowExalted"], rates[GEMCUTTER]["highExalted"]) == (7, 9)
    assert (rates[DIVINE]["lowExalted"], rates[DIVINE]["highExalted"]) == (690, 776)
    assert rates[JEWELLER]["exaltedPerUnit"] == pytest.approx(1420 / 926)  # the average stays beside it


def test_exalted_rates_give_a_divine_only_items_range_through_divines_average():
    # 2-3 divine each, at divine's volume-weighted rate (not its range: that would stack two hours' noise).
    thesis = exalted_rates(RANGED, "Forbidden Rites")[THESIS]
    divine = 1077202 / 1416
    assert thesis["lowExalted"] == pytest.approx(2 * divine)
    assert thesis["highExalted"] == pytest.approx(3 * divine)


def test_exalted_rates_leave_the_range_out_when_a_ratio_is_missing_or_zero():
    market = {**RANGED[1], "highest_ratio": {JEWELLER: 0, EXALTED: 1}}
    rates = exalted_rates([market], "Forbidden Rites")
    assert (rates[JEWELLER]["lowExalted"], rates[JEWELLER]["highExalted"]) == (None, None)


def _market(item: str, base: str, item_units: int, base_units: int, low: float | None = None,
            high: float | None = None, league: str = "Forbidden Rites") -> dict:
    """One market, `base` per `item` traded; `low`/`high` its ratio range in base per item."""
    market = {"league": league, "market_pair": [item, base], "volume_traded": {item: item_units, base: base_units}}
    if low is not None:
        market |= {"lowest_ratio": {item: 1, base: low}, "highest_ratio": {item: 1, base: high}}
    return market


def test_exalted_rates_over_several_hours_weigh_every_hours_trades():
    # A window of hours is their markets together: one average over all the trades, the widest range.
    hours = [_market(GEMCUTTER, EXALTED, 100, 800, 7, 9), _market(GEMCUTTER, EXALTED, 300, 3000, 9, 11)]
    rate = exalted_rates(hours, "Forbidden Rites")[GEMCUTTER]
    assert rate["exaltedPerUnit"] == pytest.approx(3800 / 400) and rate["volume"] == 400
    assert (rate["lowExalted"], rate["highExalted"]) == (7, 11)


def test_exalted_rates_over_several_hours_take_the_range_from_the_hours_that_have_one():
    hours = [_market(GEMCUTTER, EXALTED, 100, 800), _market(GEMCUTTER, EXALTED, 300, 3000, 9, 11)]
    rate = exalted_rates(hours, "Forbidden Rites")[GEMCUTTER]
    assert (rate["lowExalted"], rate["highExalted"]) == (9, 11)


def test_exalted_rates_over_several_hours_route_a_divine_only_item_through_the_windows_divine():
    hours = [_market(DIVINE, EXALTED, 10, 7000), _market(DIVINE, EXALTED, 10, 8000),
             _market(THESIS, DIVINE, 1, 2), _market(THESIS, DIVINE, 1, 4)]
    thesis = exalted_rates(hours, "Forbidden Rites")[THESIS]
    assert thesis["exaltedPerUnit"] == pytest.approx(3 * 750) and thesis["via"] == "divine"


# 7-day moves from two windows of hours, a week apart -- measured in divine, like poe2scout's
# changePctVsDivine, so exalted's own drift is taken out.
def _window(divine: float, gemcutter: float, units: int = 500) -> dict:
    return exalted_rates([_market(DIVINE, EXALTED, 1000, round(1000 * divine)),
                          _market(GEMCUTTER, EXALTED, units, round(units * gemcutter))], "Forbidden Rites")


def test_exchange_moves_measure_each_items_move_in_divine():
    # Gemcutter's went 8 -> 9 exalted, but divine went 700 -> 750: in divine it moved 9/750 / (8/700) - 1.
    moved = exchange_moves(_window(750, 9), _window(700, 8), min_volume=100)
    assert moved["moves"][GEMCUTTER] == {"changePctVsDivine": pytest.approx((9 / 750) / (8 / 700) * 100 - 100),
                                         "volumeNow": 500, "volumeThen": 500}
    assert moved["divineChangePct"] == pytest.approx(750 / 700 * 100 - 100)  # divine's own move, in exalted
    assert DIVINE not in moved["moves"] and moved["thin"] == 0


def test_exchange_moves_skip_an_item_too_thin_in_either_window():
    moved = exchange_moves(_window(750, 9, units=50), _window(700, 8), min_volume=100)
    assert moved["moves"] == {} and moved["thin"] == 1


def test_exchange_moves_skip_an_item_traded_in_only_one_window():
    then = exalted_rates([_market(DIVINE, EXALTED, 1000, 700000)], "Forbidden Rites")
    assert exchange_moves(_window(750, 9), then, min_volume=100)["moves"] == {}


def test_exchange_moves_need_divine_in_both_windows():
    no_divine = exalted_rates([_market(GEMCUTTER, EXALTED, 500, 4000)], "Forbidden Rites")
    moved = exchange_moves(_window(750, 9), no_divine, min_volume=100)
    assert moved == {"moves": {}, "thin": 0, "divineChangePct": None}


# The item snapshot's `exchange` section: base id -> name, for everything the exchange trades.
NAMES = {DIVINE: "Divine Orb", JEWELLER: "Greater Jeweller's Orb", GEMCUTTER: "Gemcutter's Prism",
         EXALTED: "Exalted Orb", ESSENCE: "Greater Essence of Enhancement"}


def test_value_on_exchange_values_each_holding_at_both_ends_of_the_hours_range():
    # Selling fast fetches toward the low end; the game's market ratio sits at the high end. Names match
    # in any case, and a line keeps the snapshot's name.
    valued = value_on_exchange(exalted_rates(RANGED, "Forbidden Rites"), NAMES,
                               [{"name": "divine orb", "count": 2}, {"name": "Greater Jeweller's Orb", "count": 10}])
    assert valued["lines"] == [
        {"name": "Divine Orb", "count": 2, "lowExalted": 1380, "highExalted": 1552,
         "averageExalted": pytest.approx(2 * 1077202 / 1416), "volume": 1416},
        {"name": "Greater Jeweller's Orb", "count": 10, "lowExalted": 10, "highExalted": 35,
         "averageExalted": pytest.approx(10 * 1420 / 926), "volume": 926},
    ]
    assert (valued["lowExalted"], valued["highExalted"]) == (1390, 1587)
    assert valued["averageExalted"] == pytest.approx(2 * 1077202 / 1416 + 10 * 1420 / 926)


def test_value_on_exchange_counts_exalted_at_one_each():
    # Exalted is the unit: it has no market of its own against itself.
    valued = value_on_exchange(exalted_rates(RANGED, "Forbidden Rites"), NAMES, [{"name": "Exalted Orb", "count": 40}])
    assert valued["lines"] == [{"name": "Exalted Orb", "count": 40, "lowExalted": 40, "highExalted": 40,
                                "averageExalted": 40, "volume": None}]
    assert valued["highExalted"] == 40


def test_value_on_exchange_reports_what_it_could_not_price_never_guessing():
    # An item the exchange trades but didn't that hour is `untraded`; a name it doesn't trade at all
    # (or a typo) is `unknown`. Neither counts toward the totals.
    valued = value_on_exchange(exalted_rates(RANGED, "Forbidden Rites"), NAMES,
                               [{"name": "Greater Essence of Enhancement", "count": 3},
                                {"name": "Mirror of Kalandra?", "count": 1}, {"name": "Divine Orb", "count": 1}])
    assert [ln["name"] for ln in valued["lines"]] == ["Divine Orb"]
    assert valued["untraded"] == ["Greater Essence of Enhancement"] and valued["unknown"] == ["Mirror of Kalandra?"]
    assert valued["highExalted"] == 776


def test_value_on_exchange_uses_the_average_for_both_ends_when_a_market_has_no_range():
    rates = exalted_rates(MARKETS, "Forbidden Rites")  # these markets carry no ratio range
    line = value_on_exchange(rates, NAMES, [{"name": "Divine Orb", "count": 1}])["lines"][0]
    assert line["lowExalted"] == line["highExalted"] == line["averageExalted"] == pytest.approx(747105 / 1081)


HOUR = 1791331200  # 2026-10-07 00:00 UTC
NOW = HOUR + 3600 + 49 * 60  # 01:49 UTC: the 00:00 hour is the last complete one
PUBLISHED = {"next_change_id": HOUR + 3600, "markets": MARKETS}


def test_previous_hour_is_the_last_complete_hour():
    assert previous_hour(NOW) == HOUR
    assert previous_hour(HOUR + 3600) == HOUR  # exactly on the hour


def _client(served: dict[int, dict], calls: list[str]) -> ExchangeClient:
    """A client whose hours come from `served` (hour -> body). Any other hour isn't published yet,
    which the API says with next_change_id equal to the hour asked for, and no markets."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        hour = int(request.url.path.rsplit("/", 1)[1])
        return httpx.Response(200, json=served.get(hour, {"next_change_id": hour, "markets": []}))

    return ExchangeClient(min_gap_s=0, transport=httpx.MockTransport(handler))


def _latest(client: ExchangeClient, *nows: float) -> list:
    """latest_hour at each of `nows` in turn, on the one client."""

    async def run():
        try:
            return [await client.latest_hour(now=now) for now in nows]
        finally:
            await client.aclose()

    return asyncio.run(run())


def _path(hour: int) -> str:
    return f"/api/currency-exchange/poe2/{hour}"


def test_latest_hour_asks_for_the_last_complete_hour():
    calls: list[str] = []
    [fetched] = _latest(_client({HOUR: PUBLISHED}, calls), NOW)
    assert calls == [_path(HOUR)]
    assert fetched.body["markets"] == MARKETS


def test_latest_hour_steps_back_when_the_last_hour_is_not_out_yet():
    # Two minutes past the hour, the hour just ended may not be published yet (GGG notes a delay).
    calls: list[str] = []
    [fetched] = _latest(_client({HOUR - 3600: {"next_change_id": HOUR, "markets": MARKETS}}, calls),
                        HOUR + 3600 + 120)
    assert calls == [_path(HOUR), _path(HOUR - 3600)]
    assert fetched.body["markets"] == MARKETS


def test_latest_hour_is_stamped_with_the_end_of_its_hour():
    # The data is as of the end of that hour, so freshness counts from there, not from the fetch.
    [fetched] = _latest(_client({HOUR: PUBLISHED}, []), NOW)
    assert fetched.fetched_at == HOUR + 3600


def test_latest_hour_caches_a_published_hour():
    calls: list[str] = []
    _latest(_client({HOUR: PUBLISHED}, calls), NOW, NOW + 60)
    assert calls == [_path(HOUR)]


def test_latest_hour_asks_again_for_an_hour_that_was_not_out():
    # An unpublished answer isn't cached: ten minutes later the hour is out, and it's fetched.
    calls: list[str] = []
    served = {HOUR - 3600: {"next_change_id": HOUR, "markets": MARKETS}}
    client = _client(served, calls)

    async def run():
        try:
            first = await client.latest_hour(now=HOUR + 3600 + 120)  # 00:00 not out yet -> 23:00
            served[HOUR] = PUBLISHED
            second = await client.latest_hour(now=HOUR + 3600 + 720)
            return first, second
        finally:
            await client.aclose()

    first, second = asyncio.run(run())
    assert first.fetched_at == HOUR and second.fetched_at == HOUR + 3600
    assert calls[-1] == _path(HOUR)


def test_latest_hour_raises_when_neither_hour_is_out():
    # Two tries, then give up -- it never walks back through history.
    calls: list[str] = []
    with pytest.raises(RuntimeError, match="not published"):
        _latest(_client({}, calls), NOW)
    assert calls == [_path(HOUR), _path(HOUR - 3600)]


def test_latest_hour_raises_on_an_http_error():
    client = ExchangeClient(min_gap_s=0, transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    with pytest.raises(RuntimeError, match="HTTP 503"):
        _latest(client, NOW)


# Published hours never change, so they're kept on disk (in the player's data dir): a window of hours a
# week back costs one fetch per hour once, not on every call.
def _cached_client(served: dict[int, dict], calls: list[str], cache) -> ExchangeClient:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        hour = int(request.url.path.rsplit("/", 1)[1])
        return httpx.Response(200, json=served.get(hour, {"next_change_id": hour, "markets": []}))

    return ExchangeClient(min_gap_s=0, transport=httpx.MockTransport(handler), cache_dir=lambda: cache)


def _run(client: ExchangeClient, coro_fn):
    async def run():
        try:
            return await coro_fn(client)
        finally:
            await client.aclose()

    return asyncio.run(run())


def _published(hour: int) -> dict:
    return {"next_change_id": hour + 3600, "markets": [
        {**MARKETS[0], "market_id": "x", "lowest_stock": {DIVINE: 1}, "lowest_ratio": {DIVINE: 1, EXALTED: 700},
         "highest_ratio": {DIVINE: 1, EXALTED: 760}}]}


def test_a_published_hour_is_read_from_disk_by_a_later_client(tmp_path):
    calls: list[str] = []
    _run(_cached_client({HOUR: _published(HOUR)}, calls, tmp_path), lambda c: c.latest_hour(now=NOW))
    later: list[str] = []
    [fetched] = _run(_cached_client({}, later, tmp_path), lambda c: c.recent_hours(1, now=NOW))
    assert calls == [_path(HOUR)] and later == []
    assert exalted_rates(fetched.body["markets"], "Forbidden Rites")[DIVINE]["highExalted"] == 760


def test_the_disk_copy_keeps_only_what_the_rate_math_reads(tmp_path):
    _run(_cached_client({HOUR: _published(HOUR)}, [], tmp_path), lambda c: c.latest_hour(now=NOW))
    [path] = list(tmp_path.rglob("*.json.gz"))
    with gzip.open(path, "rt", encoding="utf-8") as f:
        market = json.load(f)["markets"][0]
    assert set(market) == {"league", "market_pair", "volume_traded", "lowest_ratio", "highest_ratio"}


def test_an_unpublished_hour_is_not_written_to_disk(tmp_path):
    with pytest.raises(RuntimeError):
        _run(_cached_client({}, [], tmp_path), lambda c: c.latest_hour(now=NOW))
    assert list(tmp_path.rglob("*.json.gz")) == []


def test_a_damaged_disk_copy_is_fetched_again(tmp_path):
    _run(_cached_client({HOUR: _published(HOUR)}, [], tmp_path), lambda c: c.latest_hour(now=NOW))
    [path] = list(tmp_path.rglob("*.json.gz"))
    path.write_bytes(b"not gzip")
    calls: list[str] = []
    _run(_cached_client({HOUR: _published(HOUR)}, calls, tmp_path), lambda c: c.latest_hour(now=NOW))
    assert calls == [_path(HOUR)]


def test_hours_more_than_nine_days_older_than_a_new_one_are_removed(tmp_path):
    old = HOUR - 10 * 86400
    _run(_cached_client({old: _published(old)}, [], tmp_path), lambda c: c.recent_hours(1, now=old + 3600 + 60))
    _run(_cached_client({HOUR: _published(HOUR)}, [], tmp_path), lambda c: c.latest_hour(now=NOW))
    assert [p.name for p in tmp_path.rglob("*.json.gz")] == [f"{HOUR}.json.gz"]


def test_recent_hours_gives_a_window_ending_at_the_latest_hour_less_an_offset(tmp_path):
    # Newest first: the latest published hour less `offset_s`, then each hour before it.
    week = 7 * 86400
    served = {h: _published(h) for h in (HOUR, HOUR - week, HOUR - week - 3600)}
    calls: list[str] = []
    window = _run(_cached_client(served, calls, tmp_path), lambda c: c.recent_hours(2, offset_s=week, now=NOW))
    assert [f.fetched_at for f in window] == [HOUR - week + 3600, HOUR - week]
    assert calls == [_path(HOUR), _path(HOUR - week), _path(HOUR - week - 3600)]


def test_recent_hours_raises_when_an_hour_in_the_window_is_missing(tmp_path):
    with pytest.raises(RuntimeError, match=str(HOUR - 3600)):
        _run(_cached_client({HOUR: _published(HOUR)}, [], tmp_path), lambda c: c.recent_hours(2, now=NOW))
