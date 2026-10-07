"""Tests for the server's tool functions, with fakes standing in for the poe2scout and trade2 clients
(pure, no network). The tools are thin glue; these pin how they behave when an upstream fails."""
import asyncio
import time

import pytest

from poe2_mcp import server
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
