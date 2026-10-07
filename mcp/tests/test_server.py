"""Tests for the server's tool functions, with fakes standing in for the poe2scout and trade2 clients
(pure, no network). The tools are thin glue; these pin how they behave when an upstream fails."""
import asyncio
import math
import time

import pytest

from poe2_mcp import gamedata, server
from poe2_mcp._cache import Fetched


@pytest.fixture(autouse=True)
def _isolated_data_dir(monkeypatch, tmp_path):
    """Tools read the saved league; never let a test see the real per-user data dir."""
    monkeypatch.setenv("POE2_DATA_DIR", str(tmp_path))
    return tmp_path


def _entry(amount: float, currency: str) -> dict:
    """One trade2 fetch result, shaped like the real response (trimmed)."""
    return {
        "id": f"listing-{amount}-{currency}",
        "listing": {
            "price": {"type": "~price", "amount": amount, "currency": currency},
            "account": {"name": "seller", "online": {"league": "Forbidden Rites"}},
            "whisper": "@seller Hi, I would like to buy your Gale Stride",
        },
        "item": {"name": "Gale Stride", "baseType": "Leatherbound Boots", "rarity": "Rare", "ilvl": 70,
                 "explicitMods": ["+30% to Fire Resistance", "25% increased Movement Speed"]},
    }


class FakeTrade:
    """trade2 finding three listings, cheapest first: two priced in exalted, one in divine."""

    async def search(self, league: str, query: dict) -> Fetched:
        return Fetched(body={"id": "q123", "result": ["h1", "h2", "h3"], "total": 3}, fetched_at=time.time())

    async def fetch(self, query_id: str, hashes: list[str]) -> Fetched:
        entries = [_entry(40, "exalted"), _entry(55, "exalted"), _entry(1, "divine")]
        return Fetched(body=entries[:len(hashes)], fetched_at=time.time())


class FakeScout:
    """poe2scout. When `down`, the league comes back unchecked (as resolve_league's fallback gives it)
    and the price list can't be fetched."""

    def __init__(self, down: bool = False) -> None:
        self.down = down

    async def resolve_league(self, league: str | None = None, *, strict: bool = False) -> Fetched:
        body = {"Value": "Forbidden Rites", "Unchecked": True} if self.down else {"Value": "Forbidden Rites"}
        return Fetched(body=body, fetched_at=time.time())

    async def get_items(self, league_value: str) -> Fetched:
        if self.down:
            raise RuntimeError("poe2scout /poe2/Leagues/Forbidden%20Rites/Items -> HTTP 503 Service Unavailable")
        items = [{"ApiId": "exalted", "Text": "Exalted Orb", "CurrentPrice": 1},
                 {"ApiId": "divine", "Text": "Divine Orb", "CurrentPrice": 700}]
        return Fetched(body=items, fetched_at=time.time())


def _search(monkeypatch, scout: FakeScout) -> dict:
    monkeypatch.setattr(server, "_scout", scout)
    monkeypatch.setattr(server, "_trade", FakeTrade())
    return asyncio.run(server.search_trade({"query": {}}, limit=10))


def test_search_trade_converts_listing_prices_with_poe2scout_rates(monkeypatch):
    out = _search(monkeypatch, FakeScout())
    stats = out["priceStats"]
    assert out["shown"] == 3
    assert stats["converted"] == 3 and stats["unconvertedCurrencies"] == []
    assert stats["minExalted"] == 40 and stats["maxExalted"] == 700


def test_search_trade_keeps_its_listings_when_poe2scout_is_down(monkeypatch):
    # The listings come from trade2, so they survive; only the conversion to exalted needs poe2scout.
    # Exalted is the base unit -- 1 by definition -- so those listings still price.
    out = _search(monkeypatch, FakeScout(down=True))
    stats = out["priceStats"]
    assert out["url"] and out["matched"] == 3 and out["shown"] == 3
    assert stats["converted"] == 2 and stats["unconvertedCurrencies"] == ["divine"]
    assert stats["minExalted"] == 40 and stats["maxExalted"] == 55
    assert "poe2scout" in out["note"]


# poe2scout's live category list (Items/Categories), trimmed: unique categories, then currency ones.
CATEGORIES = {"UniqueCategories": [{"ApiId": "armour"}],
              "CurrencyCategories": [{"ApiId": c} for c in ("currency", "essences", "breach", "runes")]}


def _currency(name: str, api_id: str, price: float) -> dict:
    """One ByCategory item, trimmed to the fields the tool reads."""
    return {"Text": name, "ApiId": api_id, "CurrentPrice": price, "CurrentQuantity": 500, "PriceLogs": None}


# In poe2scout's order. Two to a page, so Greater Essence of Haste is on page 2.
ESSENCES = [_currency("Lesser Essence of Haste", "lesser-essence-of-haste", 1),
            _currency("Essence of Haste", "essence-of-haste", 4),
            _currency("Essence of the Body", "essence-of-the-body", 3),
            _currency("Greater Essence of Haste", "greater-essence-of-haste", 12)]
CURRENCY = [_currency("Divine Orb", "divine", 700), _currency("Gemcutter's Prism", "gcp", 2)]
PAGE_SIZE = 2  # poe2scout pages its answers (live: 82 essences come back as 3 pages of 40)


class PricesScout:
    """poe2scout for get_currency_prices: essences and currency are priced, a page at a time; every
    other category is empty. Records the calls, so a test can see whether the category list was
    fetched."""

    def __init__(self, categories_down: bool = False) -> None:
        self.categories_down = categories_down
        self.calls: list[str] = []

    async def resolve_league(self, league: str | None = None, *, strict: bool = False) -> Fetched:
        return Fetched(body={"Value": "Forbidden Rites", "DivinePrice": 700}, fetched_at=time.time())

    async def get_currencies_by_category(self, league_value, category, search=None, page=1, per_page=25) -> Fetched:
        self.calls.append(f"category {category}")
        pool = {"essences": ESSENCES, "currency": CURRENCY}.get(category, [])
        # As live: search is an exact, case-sensitive match on the name or the apiId, not a substring.
        matched = [i for i in pool if search is None or search in (i["Text"], i["ApiId"])]
        size = min(per_page, PAGE_SIZE)
        return Fetched(body={"Items": matched[(page - 1) * size:page * size], "Total": len(matched),
                             "CurrentPage": page, "Pages": math.ceil(len(matched) / size)},
                       fetched_at=time.time())

    async def get_categories(self, league_value: str) -> Fetched:
        self.calls.append("categories")
        if self.categories_down:
            raise RuntimeError("poe2scout /poe2/Leagues/Forbidden%20Rites/Items/Categories -> HTTP 503")
        return Fetched(body=CATEGORIES, fetched_at=time.time())


def _prices(monkeypatch, category: str, search: str | None = None, per_page: int = 25,
            **scout_kw) -> tuple[dict, PricesScout]:
    scout = PricesScout(**scout_kw)
    monkeypatch.setattr(server, "_scout", scout)
    return asyncio.run(server.get_currency_prices(category, search=search, per_page=per_page)), scout


def test_get_currency_prices_flags_a_category_poe2scout_does_not_have(monkeypatch):
    # 'catalysts' reads like a category, but poe2scout lists catalysts under 'breach'.
    out, _ = _prices(monkeypatch, "catalysts")
    assert out["items"] == [] and out["unknownCategory"] is True
    assert out["validCategories"] == ["currency", "essences", "breach", "runes"]


def test_get_currency_prices_empty_search_in_a_real_category_is_not_flagged(monkeypatch):
    out, _ = _prices(monkeypatch, "essences", search="mirror")
    assert out["items"] == [] and "unknownCategory" not in out


def test_get_currency_prices_checks_the_categories_only_when_nothing_came_back(monkeypatch):
    out, scout = _prices(monkeypatch, "essences", search="Greater Essence of Haste")
    assert [i["name"] for i in out["items"]] == ["Greater Essence of Haste"]
    assert "categories" not in scout.calls


def test_get_currency_prices_without_the_category_list_returns_the_plain_empty_result(monkeypatch):
    # The check is a nicety: if the list can't be fetched, answer as before rather than fail.
    out, _ = _prices(monkeypatch, "catalysts", categories_down=True)
    assert out["items"] == [] and "unknownCategory" not in out


# poe2scout's own search takes only an exact name or apiId (live: "Divine" and "haste" find nothing).
# The tool's search matches part of a name or apiId, in any case, across every page of the category.
def test_get_currency_prices_search_matches_part_of_a_name_in_any_case(monkeypatch):
    out, _ = _prices(monkeypatch, "essences", search="HASTE")
    assert [i["name"] for i in out["items"]] == [
        "Lesser Essence of Haste", "Essence of Haste", "Greater Essence of Haste"]  # the last from page 2


def test_get_currency_prices_search_finds_divine_from_a_partial_name(monkeypatch):
    # The currency glossary's own advice: normalize "div", then search "Divine".
    out, _ = _prices(monkeypatch, "currency", search="Divine")
    assert [i["name"] for i in out["items"]] == ["Divine Orb"]


def test_get_currency_prices_search_still_matches_an_api_id(monkeypatch):
    # Gemcutter's Prism's apiId is "gcp", which its name doesn't contain.
    out, _ = _prices(monkeypatch, "currency", search="gcp")
    assert [i["name"] for i in out["items"]] == ["Gemcutter's Prism"]


def test_get_currency_prices_search_returns_up_to_per_page_and_counts_every_match(monkeypatch):
    out, _ = _prices(monkeypatch, "essences", search="essence", per_page=2)
    assert len(out["items"]) == 2 and out["total"] == 4


# A loaded item snapshot, trimmed to one real row of its texts.
ITEM_SNAPSHOT = {"patch": "0.5.5", "texts": {"Orb of Annulment": {
    "class": "StackableCurrency", "text": "Removes a random modifier from an item",
    "use": "Right click this item then left click on a magic or rare item to apply it."}}}


def test_item_text_looks_the_search_up_in_the_installed_snapshot(monkeypatch):
    monkeypatch.setattr(server, "load_items", lambda: ITEM_SNAPSHOT)
    out = asyncio.run(server.item_text("orb of annulment"))
    assert out == gamedata.item_text(ITEM_SNAPSHOT, "orb of annulment") and out["total"] == 1


def test_item_text_says_when_no_snapshot_is_installed(monkeypatch):
    monkeypatch.setattr(server, "load_items", lambda: None)
    out = asyncio.run(server.item_text("orb of annulment"))
    assert out["valid"] is False and out["error"] == "no item snapshot is installed"


# A loaded snapshot, trimmed to one real entry of each trial's pool.
TRIAL_SNAPSHOT = {
    "patch": "0.5.5",
    "chaos": [{"name": "Time Paradox", "kind": "modifier", "versions": [
        {"name": "Time Paradox", "tier": 1,
         "text": "Buffs on you expire 50% faster and Debuffs on you expire 25% slower"}]}],
    "sekhemas": [{"name": "Iron Manacles", "category": "Minor Afflictions", "text": "You have no Evasion"}],
}


def test_trial_pool_looks_the_search_up_in_the_installed_snapshot(monkeypatch):
    monkeypatch.setattr(server, "load_items", lambda: TRIAL_SNAPSHOT)
    out = asyncio.run(server.trial_pool("sekhemas", "evasion"))
    assert out == gamedata.trial_pool(TRIAL_SNAPSHOT, "sekhemas", "evasion") and out["total"] == 1


def test_trial_pool_says_when_no_snapshot_is_installed(monkeypatch):
    monkeypatch.setattr(server, "load_items", lambda: None)
    out = asyncio.run(server.trial_pool("chaos"))
    assert out["valid"] is False and out["error"] == "no item snapshot is installed"
