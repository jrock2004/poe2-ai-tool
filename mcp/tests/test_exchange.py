"""Unit tests for GGG's Currency Exchange client and its rate math (pure, no network)."""
import asyncio

import httpx
import pytest

from poe2_mcp.exchange import EXALTED, ExchangeClient, exalted_rates, previous_hour

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
