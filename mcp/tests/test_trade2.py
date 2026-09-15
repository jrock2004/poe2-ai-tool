"""Unit tests for the pure (no-network) parts of the trade2 adapter."""
from poe2_mcp.trade2 import (
    StatFilter,
    human_search_url,
    _mod_texts,
    _normalize_affix,
    _parse_buckets,
    _stat_rank,
    build_query,
    summarize_listing,
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
