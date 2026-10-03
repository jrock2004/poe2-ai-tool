"""Unit tests for the trade2 adapter: pure helpers, plus the client over an offline mock transport."""
import asyncio
import time
import types

import httpx
import pytest

from poe2_mcp import trade2
from poe2_mcp._cache import Fetched
from poe2_mcp.trade2 import (
    StatFilter,
    Trade2Client,
    Trade2Error,
    human_search_url,
    _mod_texts,
    _normalize_affix,
    _parse_buckets,
    _stat_rank,
    build_query,
    listing_price_stats,
    summarize_listing,
    to_exalted,
)


def test_normalize_affix_wildcards_numbers():
    assert _normalize_affix("+80 to maximum Life") == "# to maximum life"
    assert _normalize_affix("30% increased Cold Damage") == "#% increased cold damage"
    # signed and decimal numbers both collapse to a single placeholder
    assert _normalize_affix("-25.5% to Fire   Resistance") == "#% to fire resistance"


def test_parse_buckets():
    buckets = _parse_buckets("5:10:60,15:60:300")
    assert len(buckets) == 2
    assert (buckets[0].max, buckets[0].period, buckets[0].timeout) == (5, 10, 60)
    assert (buckets[1].max, buckets[1].period, buckets[1].timeout) == (15, 60, 300)
    assert _parse_buckets("") == []
    assert _parse_buckets("garbage") == []


def test_build_query_minimal():
    q = build_query()
    assert q == {"query": {"status": {"option": "online"}}, "sort": {"price": "asc"}}


def test_build_query_full():
    q = build_query(
        stats=[StatFilter("explicit.stat_x", min=70), StatFilter("explicit.stat_y")],
        category="armour.boots",
        max_price=1.5,
        price_currency="divine",
    )
    query = q["query"]
    assert query["filters"]["type_filters"]["filters"]["category"] == {"option": "armour.boots"}
    assert query["filters"]["trade_filters"]["filters"]["price"] == {"max": 1.5, "option": "divine"}
    stat_filters = query["stats"][0]["filters"]
    assert stat_filters[0] == {"id": "explicit.stat_x", "value": {"min": 70}}
    # a stat with no min/max carries no 'value' key (presence-only filter)
    assert stat_filters[1] == {"id": "explicit.stat_y"}


def test_build_query_offline_only_when_requested():
    q = build_query(online_only=False)
    assert q["query"]["status"] == {"option": "any"}


def test_stat_rank_prefers_explicit_over_pseudo():
    explicit = {"type": "explicit", "norm": "#% increased movement speed"}
    pseudo = {"type": "pseudo", "norm": "#% increased movement speed"}
    assert _stat_rank(explicit) < _stat_rank(pseudo)


def test_mod_texts_handles_strings_and_objects():
    assert _mod_texts(["+18 to maximum Life"]) == ["+18 to maximum Life"]
    assert _mod_texts([{"description": "10% increased Movement Speed"}]) == [
        "10% increased Movement Speed"
    ]
    assert _mod_texts(None) == []


def test_summarize_listing_flattens():
    entry = {
        "listing": {
            "price": {"type": "~price", "amount": 1, "currency": "divine"},
            "account": {"name": "SomeSeller", "online": {"status": "online"}},
            "whisper": "@SomeSeller Hi, I'd like to buy your Boots",
        },
        "item": {
            "name": "Atziri's Step",
            "baseType": "Cinched Boots",
            "typeLine": "Cinched Boots",
            "rarity": "Unique",
            "ilvl": 82,
            "explicitMods": [{"description": "30% increased Movement Speed"}],
        },
    }
    s = summarize_listing(entry)
    assert s["name"] == "Atziri's Step"
    assert s["price"] == {"amount": 1, "currency": "divine", "type": "~price"}
    assert s["explicitMods"] == ["30% increased Movement Speed"]
    assert s["seller"] == "SomeSeller"
    assert s["online"] is True
    assert s["whisper"].startswith("@SomeSeller")


def test_human_search_url_encodes_league():
    url = human_search_url("Forbidden Rites", "abc123")
    assert url == "https://www.pathofexile.com/trade2/search/poe2/Forbidden%20Rites/abc123"


RATES = {"exalted": 1, "divine": 500, "chaos": 60}


def _priced(amount, currency):
    """A listing shaped like summarize_listing output, reduced to what price stats read."""
    return {"price": {"amount": amount, "currency": currency, "type": "~price"}}


def test_to_exalted_converts_known_and_refuses_unknown():
    assert to_exalted(2, "divine", RATES) == 1000
    assert to_exalted(250, "exalted", RATES) == 250
    assert to_exalted(5, "mirror-shard", RATES) is None


def test_price_stats_mixed_currencies():
    stats = listing_price_stats(
        [_priced(1, "divine"), _priced(250, "exalted"), _priced(2, "chaos")], RATES
    )
    assert stats["count"] == 3
    assert stats["converted"] == 3
    assert stats["unconvertedCurrencies"] == []
    assert stats["minExalted"] == 120
    assert stats["medianExalted"] == 250
    assert stats["maxExalted"] == 500
    assert stats["spreadRatio"] == 500 / 120


def test_price_stats_reports_unknown_currency_instead_of_dropping_it():
    stats = listing_price_stats(
        [_priced(100, "exalted"), _priced(5, "mirror-shard"), _priced(1, "mirror-shard")], RATES
    )
    assert stats["count"] == 3
    assert stats["converted"] == 1
    assert stats["unconvertedCurrencies"] == ["mirror-shard"]


def test_price_stats_median_of_even_count_averages_middle_pair():
    stats = listing_price_stats([_priced(n, "exalted") for n in (400, 100, 300, 200)], RATES)
    assert stats["medianExalted"] == 250


def test_price_stats_empty_and_single_have_no_spread():
    empty = listing_price_stats([], RATES)
    assert empty["count"] == 0 and empty["converted"] == 0
    assert empty["minExalted"] is None and empty["medianExalted"] is None
    assert empty["maxExalted"] is None and empty["spreadRatio"] is None

    single = listing_price_stats([_priced(1, "divine")], RATES)
    assert single["minExalted"] == single["medianExalted"] == single["maxExalted"] == 500
    assert single["spreadRatio"] is None


def test_price_stats_spread_is_none_when_min_is_zero():
    stats = listing_price_stats([_priced(0, "exalted"), _priced(50, "exalted")], RATES)
    assert stats["spreadRatio"] is None


def test_price_stats_excludes_unpriced_listings_silently():
    stats = listing_price_stats([{"price": None}, _priced(100, "exalted")], RATES)
    assert stats["count"] == 2
    assert stats["converted"] == 1
    assert stats["unconvertedCurrencies"] == []


def _offline_trade(handler) -> Trade2Client:
    """A Trade2Client whose HTTP goes to an in-memory transport; no throttling gap."""
    return Trade2Client(min_gap_s=0, transport=httpx.MockTransport(handler))


def test_search_returns_fetched_and_cache_hit_keeps_fetched_at():
    posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posts.append(request.url.raw_path.decode())
        return httpx.Response(200, json={"id": "q1", "result": ["h1"], "total": 1})

    async def run():
        client = _offline_trade(handler)
        query = build_query(category="armour.boots")
        first = await client.search("Forbidden Rites", query)
        second = await client.search("Forbidden Rites", query)
        await client.aclose()
        return first, second

    first, second = asyncio.run(run())
    assert isinstance(first, Fetched)
    assert first.body["id"] == "q1"
    assert second.fetched_at == first.fetched_at
    assert posts == ["/api/trade2/search/poe2/Forbidden%20Rites"]


def test_fetch_batches_and_reports_the_oldest_batch_time(monkeypatch):
    clock = iter([100.0, 200.0])
    # Swap only trade2's `time` binding: patching time.time globally also hits httpx (cookie handling).
    fake_time = types.SimpleNamespace(time=lambda: next(clock), monotonic=time.monotonic)
    monkeypatch.setattr(trade2, "time", fake_time)
    batches: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hashes = request.url.path.rsplit("/", 1)[-1].split(",")
        batches.append(len(hashes))
        return httpx.Response(200, json={"result": [{"id": h} for h in hashes]})

    async def run():
        client = _offline_trade(handler)
        got = await client.fetch("q1", [f"h{i}" for i in range(12)])
        await client.aclose()
        return got

    got = asyncio.run(run())
    assert batches == [10, 2]
    assert isinstance(got, Fetched)
    assert [e["id"] for e in got.body] == [f"h{i}" for i in range(12)]
    assert got.fetched_at == 100.0


def test_stat_index_rebuilds_after_the_stats_cache_expires():
    texts = iter(["# to maximum Life", "# to maximum Mana"])
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        entry = {"id": "explicit.stat_1", "text": next(texts), "type": "explicit"}
        return httpx.Response(200, json={"result": [{"label": "Explicit", "entries": [entry]}]})

    async def run():
        client = Trade2Client(min_gap_s=0, stats_ttl_s=0.2, transport=httpx.MockTransport(handler))
        first = await client.stat_index()
        within_ttl = await client.stat_index()
        await asyncio.sleep(0.3)
        after_ttl = await client.stat_index()
        await client.aclose()
        return first, within_ttl, after_ttl

    first, within_ttl, after_ttl = asyncio.run(run())
    assert first[0]["text"] == "# to maximum Life"
    assert within_ttl == first
    assert after_ttl[0]["text"] == "# to maximum Mana"
    assert calls == ["/api/trade2/data/stats", "/api/trade2/data/stats"]


def test_fetch_cache_is_keyed_by_the_hashes_not_just_the_batch_offset():
    batches: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hashes = request.url.path.rsplit("/", 1)[-1].split(",")
        batches.append(len(hashes))
        return httpx.Response(200, json={"result": [{"id": h} for h in hashes]})

    hashes = [f"h{i}" for i in range(10)]

    async def run():
        client = _offline_trade(handler)
        five = await client.fetch("q1", hashes[:5])       # search_trade(limit=5)
        ten = await client.fetch("q1", hashes)            # then limit=10 on the same query
        ten_again = await client.fetch("q1", hashes)      # identical call: cache hit
        await client.aclose()
        return five, ten, ten_again

    five, ten, ten_again = asyncio.run(run())
    assert len(five.body) == 5
    assert [e["id"] for e in ten.body] == hashes
    assert ten_again.fetched_at == ten.fetched_at
    assert batches == [5, 10]


# GGG's rate-limit headers: the policy is "max:period:timeout" per bucket, and the state is
# "current:period:active_timeout" per bucket, in the same order.
POLICY = "5:10:60,15:60:300"


def _search_with_headers(monkeypatch, headers: dict[str, str], status: int = 200) -> list[float]:
    """Run one search against a response carrying `headers`; return the sleeps the client asked for.

    Swaps only trade2's `asyncio` binding, so the recorded sleeps are the client's and nothing waits.
    """
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(trade2, "asyncio", types.SimpleNamespace(sleep=fake_sleep, Lock=asyncio.Lock))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers=headers, json={"id": "q1", "result": [], "total": 0})

    async def run():
        client = _offline_trade(handler)
        try:
            await client.search("Forbidden Rites", build_query())
        finally:
            await client.aclose()

    asyncio.run(run())
    return sleeps


def test_rate_limit_under_the_ceiling_does_not_wait(monkeypatch):
    headers = {"X-Rate-Limit-Ip": POLICY, "X-Rate-Limit-Ip-State": "1:10:0,1:60:0"}
    assert _search_with_headers(monkeypatch, headers) == []


def test_rate_limit_at_the_ceiling_waits_out_that_window(monkeypatch):
    headers = {"X-Rate-Limit-Ip": POLICY, "X-Rate-Limit-Ip-State": "5:10:0,5:60:0"}
    assert _search_with_headers(monkeypatch, headers) == [10]


def test_rate_limit_active_timeout_waits_the_timeout(monkeypatch):
    headers = {"X-Rate-Limit-Ip": POLICY, "X-Rate-Limit-Ip-State": "6:10:45,1:60:0"}
    assert _search_with_headers(monkeypatch, headers) == [45]


def test_rate_limit_wait_is_capped_at_a_minute(monkeypatch):
    headers = {"X-Rate-Limit-Ip": "5:10:60,15:600:300", "X-Rate-Limit-Ip-State": "1:10:0,15:600:0"}
    assert _search_with_headers(monkeypatch, headers) == [60]


def test_429_raises_with_the_retry_after(monkeypatch):
    with pytest.raises(Trade2Error, match="retry after 30s"):
        _search_with_headers(monkeypatch, {"Retry-After": "30"}, status=429)
