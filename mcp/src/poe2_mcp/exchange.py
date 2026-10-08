"""Client for GGG's Currency Exchange API (https://web.poecdn.com/api/currency-exchange), and the rate
math over it.

GGG's own documented, public endpoint (developer docs, "Currency Exchange"): no account, no OAuth.
Each call returns one hour's digest of in-game currency-exchange trades across every league -- per
market (a pair of items, by base item id), the volume each side traded and the ratio range. History
only: the current hour isn't available, and an hour is published a few minutes after it ends.

Here it's a second source of currency rates beside poe2scout, keyed by base item id (poe2scout's items
carry the same id as BaseItemTypeId). Etiquette: descriptive User-Agent, gentle throttling, and a
published hour -- which never changes -- is cached rather than asked for again.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

from ._cache import Fetched

BASE = os.environ.get("POE2_EXCHANGE_BASE", "https://web.poecdn.com")
REALM = os.environ.get("POE2_REALM", "poe2")
USER_AGENT = os.environ.get(
    "POE2_EXCHANGE_USER_AGENT", "poe2-ai-tools (personal; https://github.com/jrock2004/poe2-ai-tool)"
)
EXALTED = "Metadata/Items/Currency/CurrencyAddModToRare"  # the base unit
DIVINE = "Metadata/Items/Currency/CurrencyModValues"


def previous_hour(now: float) -> int:
    """The last complete hour before `now`, as the unix timestamp the API keys hours by. Pure."""
    return int(now) // 3600 * 3600 - 3600


def exalted_rates(markets: list[dict[str, Any]], league: str) -> dict[str, dict[str, Any]]:
    """Exalted per unit for each item traded in `league`, from one hour's `markets`. Pure.

    Returns {base item id: {"exaltedPerUnit", "volume", "via", "lowExalted", "highExalted"}}. The rate is
    volume-weighted -- exalted traded over units traded -- the hour's average across buyers and sellers.
    `lowExalted`/`highExalted` are the ends of the hour's ratio range, in exalted each (None when the
    market has no usable range). The range is what the game shows: John's in-game market ratios sat at its
    high end (2026-10-08), while on cheap bulk items the average sits far below -- buyers and sellers are
    far apart. A stray trade can stretch either end (one hour's divine market had 1:135 beside 1:715).

    An item with a market against exalted uses it (via "exalted"); one traded only against divine goes
    through divine's own average rate (via "divine"), as expensive items often do. `volume` is the units
    of the item traded. Markets that traded nothing are skipped, and exalted itself isn't listed: it's 1
    by definition.
    """
    direct: dict[str, tuple[float, int, tuple[float, float] | None]] = {}
    through_divine: dict[str, tuple[float, int, tuple[float, float] | None]] = {}
    for market in markets:
        pair = market.get("market_pair") or []
        volume = market.get("volume_traded") or {}
        if market.get("league") != league or len(pair) != 2 or not all(volume.get(i) for i in pair):
            continue
        for base, found in ((EXALTED, direct), (DIVINE, through_divine)):
            if base in pair:
                item = pair[1] if pair[0] == base else pair[0]
                found[item] = (volume[base] / volume[item], volume[item], _range(market, item, base))
                break

    rates: dict[str, dict[str, Any]] = {
        item: _rate(rate, units, "exalted", span, 1.0) for item, (rate, units, span) in direct.items()
    }
    divine = rates.get(DIVINE)
    if divine:
        for item, (divine_per_unit, units, span) in through_divine.items():
            rates.setdefault(item, _rate(divine_per_unit, units, "divine", span, divine["exaltedPerUnit"]))
    return rates


def value_on_exchange(
    rates: dict[str, dict[str, Any]], names: dict[str, str], holdings: list[dict[str, Any]]
) -> dict[str, Any]:
    """Value holdings at one hour's exchange `rates` (`exalted_rates`). Pure.

    names: base id -> name, the item snapshot's `exchange` section. holdings: [{name, count}], matched by
    exact name in any case. Each priced line gives its count's worth at both ends of the hour's range and
    at its average (`lowExalted`, `highExalted`, `averageExalted`, exalted) and the hour's `volume`. A
    market with no range values at its average for both ends. Exalted Orb is 1 each (no volume). Totals
    are the sums over priced lines. A name the exchange trades that didn't trade that hour is `untraded`;
    a name it doesn't trade at all (or a typo) is `unknown` -- reported, never guessed.
    """
    by_name: dict[str, str] = {}
    for base_id, name in names.items():
        if base_id in rates or base_id == EXALTED or name.lower() not in by_name:
            by_name[name.lower()] = base_id  # a priced id wins over an unpriced one of the same name

    lines: list[dict[str, Any]] = []
    untraded: list[str] = []
    unknown: list[str] = []
    for holding in holdings:
        asked = (holding.get("name") or "").strip()
        count = holding.get("count") or 0
        base_id = by_name.get(asked.lower())
        if base_id is None:
            unknown.append(asked)
            continue
        if base_id == EXALTED:
            low = high = average = 1.0
            volume = None
        elif base_id in rates:
            rate = rates[base_id]
            average, volume = rate["exaltedPerUnit"], rate["volume"]
            low = average if rate["lowExalted"] is None else rate["lowExalted"]
            high = average if rate["highExalted"] is None else rate["highExalted"]
        else:
            untraded.append(asked)
            continue
        lines.append({"name": names[base_id], "count": count, "lowExalted": count * low,
                      "highExalted": count * high, "averageExalted": count * average, "volume": volume})

    return {"lines": lines, "lowExalted": sum(ln["lowExalted"] for ln in lines),
            "highExalted": sum(ln["highExalted"] for ln in lines),
            "averageExalted": sum(ln["averageExalted"] for ln in lines), "untraded": untraded, "unknown": unknown}


def _range(market: dict[str, Any], item: str, base: str) -> tuple[float, float] | None:
    """The hour's lowest and highest `base` per `item`, from the market's two ratios. Pure. The API's
    names don't say which end is cheaper, so take the lower and higher. None if either is missing or 0."""
    prices = []
    for key in ("lowest_ratio", "highest_ratio"):
        ratio = market.get(key) or {}
        if not ratio.get(item) or not ratio.get(base):
            return None
        prices.append(ratio[base] / ratio[item])
    return min(prices), max(prices)


def _rate(per_unit: float, units: int, via: str, span: tuple[float, float] | None, scale: float) -> dict[str, Any]:
    return {"exaltedPerUnit": per_unit * scale, "volume": units, "via": via,
            "lowExalted": None if span is None else span[0] * scale,
            "highExalted": None if span is None else span[1] * scale}


class ExchangeClient:
    def __init__(
        self,
        min_gap_s: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,  # tests pass an httpx.MockTransport
    ) -> None:
        self._hours: dict[int, Fetched[dict[str, Any]]] = {}
        self._last_request = 0.0
        self._min_gap_s = min_gap_s
        self._client = httpx.AsyncClient(
            base_url=BASE,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=30.0,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _hour(self, hour: int) -> Fetched[dict[str, Any]] | None:
        """One hour's digest, or None if it isn't published yet -- the API says so by answering with
        next_change_id equal to the hour asked for. A published hour is cached; "not yet" isn't."""
        if hour in self._hours:
            return self._hours[hour]

        gap = self._last_request + self._min_gap_s - time.monotonic()
        if gap > 0:
            await asyncio.sleep(gap)
        self._last_request = time.monotonic()

        path = f"/api/currency-exchange/{REALM}/{hour}"
        resp = await self._client.get(path)
        if resp.status_code != 200:
            raise RuntimeError(f"currency exchange {path} -> HTTP {resp.status_code} {resp.reason_phrase}")
        body = resp.json()
        if body.get("next_change_id") == hour:
            return None
        fetched = Fetched(body=body, fetched_at=float(hour + 3600))  # as of the end of its hour
        self._hours[hour] = fetched
        for old in [h for h in self._hours if h < hour - 3600]:  # only the last two are ever asked for
            del self._hours[old]
        return fetched

    async def latest_hour(self, now: float | None = None) -> Fetched[dict[str, Any]]:
        """The newest published hour: the last complete one, or the one before it while that's still
        being published. Stamped with the end of its hour, so freshness is the data's age, not the
        fetch's. Raises if neither is out -- it never walks further back through history."""
        hour = previous_hour(time.time() if now is None else now)
        for candidate in (hour, hour - 3600):
            fetched = await self._hour(candidate)
            if fetched is not None:
                return fetched
        raise RuntimeError(f"currency exchange: the hours from {hour - 3600} and {hour} are not published yet")
