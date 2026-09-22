"""Thin, read-only client for GGG's unofficial PoE 2 trade API (`/api/trade2`).

This is the ONE source that can search rare items by affix -- poe2scout cannot. It is unofficial,
undocumented, and IP-rate-limited, so this client is deliberately conservative:

* **Read-only.** It searches and fetches listings. It never buys, whispers, or touches an account.
* **Rate-limit aware.** GGG returns its policy in `X-Rate-Limit-*` headers; we parse them, self-throttle
  before we hit a bucket ceiling, and honor `Retry-After` / active timeouts on 429.
* **Cached hard.** Identical searches/fetches inside the TTL never re-hit the network.
* **Offline-first where it can be.** Query construction (`build_query`) is genuinely pure -- it
  never touches the network. Stat lookup is *cached, not offline*: `find_stats`/`stat_index` fetch
  `/data/stats` once on a cold cache (6h TTL, `stats_ttl_s`) before they can resolve anything.
  `search` and `fetch` make live calls on every cache miss, and callers gate those.

Shapes were confirmed against the live API (Forbidden Rites, poe2 realm):
  POST /api/trade2/search/poe2/{league}  {query...} -> {id, complexity, result:[hash,...]}
  GET  /api/trade2/fetch/{hashes}?query={id}        -> {result:[{id, listing, item}, ...]}
  GET  /api/trade2/data/stats                        -> {result:[{id,label,entries:[{id,text,type}]}]}
  GET  /api/trade2/data/leagues                      -> {result:[{id,realm,text}]}
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from ._cache import CacheEntry, Fetched

TRADE_BASE = os.environ.get("POE2_TRADE_BASE", "https://www.pathofexile.com")
REALM = os.environ.get("POE2_REALM", "poe2")
# GGG blocks generic/library User-Agents. A browser-like UA plus a contact is the etiquette here.
TRADE_UA = os.environ.get(
    "POE2_TRADE_USER_AGENT",
    "Mozilla/5.0 (compatible; poe2-ai-tools/0.1; personal; contact jrock2004@gmail.com)",
)
# Fetch accepts at most 10 item hashes per request.
FETCH_BATCH = 10


def human_search_url(league: str, query_id: str) -> str:
    """The clickable trade-site URL for a POSTed search id (what the player opens in a browser)."""
    return f"{TRADE_BASE}/trade2/search/{REALM}/{quote(league, safe='')}/{query_id}"


@dataclass
class _Bucket:
    """One rate-limit rule: `max` hits per `period` seconds, `timeout` s ban if exceeded."""

    max: int
    period: int
    timeout: int


def _parse_buckets(policy: str) -> list[_Bucket]:
    """Parse an `X-Rate-Limit-Ip` value like '5:10:60,15:60:300' into buckets."""
    out: list[_Bucket] = []
    for rule in (policy or "").split(","):
        parts = rule.split(":")
        if len(parts) == 3:
            try:
                out.append(_Bucket(int(parts[0]), int(parts[1]), int(parts[2])))
            except ValueError:
                continue
    return out


class Trade2Error(RuntimeError):
    """Raised for non-retryable trade2 failures (blocked, bad request, etc.)."""


class Trade2Client:
    def __init__(
        self,
        min_gap_s: float = 1.0,
        ttl_s: float = 300.0,
        stats_ttl_s: float = 21600.0,
        transport: httpx.AsyncBaseTransport | None = None,  # tests pass an httpx.MockTransport
    ):
        self._cache: dict[str, CacheEntry] = {}
        self._min_gap_s = min_gap_s
        self._ttl_s = ttl_s
        self._stats_ttl_s = stats_ttl_s  # stat metadata rarely changes; cache 6h
        self._last_live_call = 0.0
        self._live_lock = asyncio.Lock()  # serialize live calls so throttling is coherent
        self._client = httpx.AsyncClient(
            base_url=TRADE_BASE,
            headers={
                "User-Agent": TRADE_UA,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": TRADE_BASE,
            },
            timeout=30.0,
            transport=transport,
        )
        # The flattened stat index, and the /data/stats response it was built from -- rebuilt whenever
        # that response is refreshed (stats_ttl_s), so a long-running server never serves a stale list.
        self._stats_index: list[dict[str, str]] | None = None
        self._stats_source: Fetched[Any] | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _respect_before(self) -> None:
        gap = self._last_live_call + self._min_gap_s - time.monotonic()
        if gap > 0:
            await asyncio.sleep(gap)

    async def _respect_after(self, resp: httpx.Response) -> None:
        """After a live call, if the state header shows we're at a bucket ceiling, wait it out."""
        self._last_live_call = time.monotonic()
        buckets = _parse_buckets(resp.headers.get("X-Rate-Limit-Ip", ""))
        state = _parse_buckets(resp.headers.get("X-Rate-Limit-Ip-State", ""))
        # state pairs with the policy buckets by period; its fields are (current count, _, timeout).
        for pol, st in zip(buckets, state):
            if st.timeout > 0:  # already timed out on this bucket
                await asyncio.sleep(min(st.timeout, 60))
                return
            if pol.max and st.max >= pol.max:  # at the ceiling: wait the window out
                await asyncio.sleep(min(pol.period, 60))
                return

    async def _live(self, method: str, path: str, *, json_body: Any = None, cache_key: str | None = None,
                    ttl: float | None = None) -> Fetched[Any]:
        if cache_key:
            hit = self._cache.get(cache_key)
            if hit and hit.expires > time.monotonic():
                return hit.fetched
        async with self._live_lock:
            await self._respect_before()
            resp = await self._client.request(method, path, json=json_body)
            await self._respect_after(resp)
        if resp.status_code == 429:
            retry = resp.headers.get("Retry-After")
            raise Trade2Error(
                f"trade2 rate-limited (429) on {path}"
                + (f"; retry after {retry}s" if retry else "")
                + ". Backing off -- this is expected; try again shortly."
            )
        if resp.status_code == 403:
            raise Trade2Error(
                f"trade2 blocked (403) on {path}. The unofficial endpoint may require a POESESSID "
                "cookie from a logged-in browser, or is refusing this client."
            )
        if resp.status_code >= 400:
            raise Trade2Error(f"trade2 {path} -> HTTP {resp.status_code} {resp.reason_phrase}: {resp.text[:200]}")
        fetched = Fetched(body=resp.json(), fetched_at=time.time())
        if cache_key:
            lifetime = ttl if ttl is not None else self._ttl_s
            self._cache[cache_key] = CacheEntry(time.monotonic() + lifetime, fetched)
        return fetched

    async def _stats(self) -> Fetched[Any]:
        return await self._live("GET", "/api/trade2/data/stats", cache_key="data/stats",
                                ttl=self._stats_ttl_s)

    async def stat_index(self) -> list[dict[str, str]]:
        """Flattened, normalized {id, text, type, norm} list of every stat filter, cached."""
        source = await self._stats()
        if self._stats_index is not None and source is self._stats_source:
            return self._stats_index
        idx: list[dict[str, str]] = []
        for group in source.body.get("result", []):
            for e in group.get("entries", []):
                text = e.get("text", "")
                idx.append({"id": e.get("id", ""), "text": text, "type": e.get("type", ""),
                            "norm": _normalize_affix(text)})
        self._stats_index = idx
        self._stats_source = source
        return idx

    async def find_stats(self, affix: str, limit: int = 6) -> list[dict[str, str]]:
        """Resolve a human affix line to candidate stat filter ids, best matches first.

        Numbers in the affix are treated as the `#` placeholder, so '+80 to maximum Life' matches
        the '# to maximum Life' filter. Exact normalized matches rank above substring matches, and
        within each tier `explicit` mods rank first (the literal reading of a pasted mod), with
        `pseudo`/aggregate stats last -- but all are returned so the skill can pick an alternative.
        """
        needle = _normalize_affix(affix)
        if not needle:
            return []
        idx = await self.stat_index()
        exact = [e for e in idx if e["norm"] == needle]
        if exact:
            exact.sort(key=_stat_rank)
            return _dedup_stats(exact)[:limit]
        subs = [e for e in idx if needle in e["norm"] or e["norm"] in needle]
        subs.sort(key=_stat_rank)
        return _dedup_stats(subs)[:limit]

    async def search(self, league: str, query: dict[str, Any]) -> Fetched[dict[str, Any]]:
        path = f"/api/trade2/search/{REALM}/{quote(league, safe='')}"
        key = f"search:{league}:{_stable(query)}"
        return await self._live("POST", path, json_body=query, cache_key=key)

    async def fetch(self, query_id: str, hashes: list[str]) -> Fetched[list[dict[str, Any]]]:
        """Fetch listings in batches of FETCH_BATCH; stamped with the OLDEST batch's fetch time."""
        out: list[dict[str, Any]] = []
        times: list[float] = []
        for i in range(0, len(hashes), FETCH_BATCH):
            batch = hashes[i : i + FETCH_BATCH]
            path = f"/api/trade2/fetch/{','.join(batch)}?query={query_id}"
            key = f"fetch:{query_id}:{i}"
            got = await self._live("GET", path, cache_key=key)
            out.extend(got.body.get("result") or [])
            times.append(got.fetched_at)
        return Fetched(body=out, fetched_at=min(times) if times else time.time())


# Default ranking when resolving an affix to a filter id: the literal reading of a pasted mod is an
# explicit mod, so it wins; pseudo/aggregate stats are valid but a deliberate choice, so they trail.
_TYPE_RANK = {"explicit": 0, "implicit": 1, "fractured": 2, "rune": 3, "enchant": 4,
              "crafted": 5, "desecrated": 6, "sanctum": 7, "skill": 8, "pseudo": 9}


def _stat_rank(e: dict[str, str]) -> tuple[int, int]:
    return (_TYPE_RANK.get(e["type"], 50), len(e["norm"]))


def _normalize_affix(text: str) -> str:
    """Lowercase, collapse whitespace, and turn any number into '#' so values don't block matching."""
    t = re.sub(r"[+\-]?\d+(?:\.\d+)?", "#", text.lower())
    return re.sub(r"\s+", " ", t).strip()


def _dedup_stats(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out = []
    for e in entries:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        out.append(e)
    return out


def _stable(obj: Any) -> str:
    import json

    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@dataclass
class StatFilter:
    """One required stat on the item, e.g. explicit.stat_3299347043 with min=80."""

    id: str
    min: float | None = None
    max: float | None = None


def build_query(
    stats: list[StatFilter] | None = None,
    category: str | None = None,
    max_price: float | None = None,
    price_currency: str = "divine",
    online_only: bool = True,
) -> dict[str, Any]:
    """Construct a trade2 search body. Pure -- no network, always safe to call.

    stats: required affix filters (resolve ids via Trade2Client.find_stats first).
    category: type filter option, e.g. 'armour.boots', 'weapon.bow', 'accessory.ring'.
    max_price: optional price ceiling in `price_currency` (e.g. cap by your currency budget).
    """
    query: dict[str, Any] = {"status": {"option": "online" if online_only else "any"}}

    filters: dict[str, Any] = {}
    if category:
        filters["type_filters"] = {"filters": {"category": {"option": category}}}
    if max_price is not None:
        filters["trade_filters"] = {"filters": {"price": {"max": max_price, "option": price_currency}}}
    if filters:
        query["filters"] = filters

    if stats:
        query["stats"] = [
            {
                "type": "and",
                "filters": [
                    {"id": s.id, "value": _minmax(s)} if (s.min is not None or s.max is not None)
                    else {"id": s.id}
                    for s in stats
                ],
            }
        ]

    return {"query": query, "sort": {"price": "asc"}}


def _minmax(s: StatFilter) -> dict[str, float]:
    v: dict[str, float] = {}
    if s.min is not None:
        v["min"] = s.min
    if s.max is not None:
        v["max"] = s.max
    return v


def _mod_texts(mods: Any) -> list[str]:
    """Normalize an explicit/implicit mod list to plain strings.

    The trade API returns mods either as plain strings or as objects carrying a `description`.
    """
    out: list[str] = []
    for m in mods or []:
        if isinstance(m, str):
            out.append(m)
        elif isinstance(m, dict):
            text = m.get("description") or m.get("name")
            if text:
                out.append(text)
    return out


def to_exalted(amount: float, currency: str, rates: dict[str, float]) -> float | None:
    """Convert a listing price to exalted using `rates` (from poe2scout.rates_from_items).

    Returns None when the currency isn't in `rates` -- an unknown currency is never guessed.
    """
    rate = rates.get(currency)
    return None if rate is None else amount * rate


def listing_price_stats(listings: list[dict[str, Any]], rates: dict[str, float]) -> dict[str, Any]:
    """Grounded price signals over summarized listings (from summarize_listing). Pure -- no network.

    Returns {count, converted, unconvertedCurrencies, minExalted, medianExalted, maxExalted,
    spreadRatio}. `count` is every listing passed in; `converted` is how many had a price in a known
    currency. Listings with no price are excluded silently; listings in an unknown currency are
    excluded and their currency ids reported (unique, first-seen order). min/median/max are None when
    nothing converted. spreadRatio = max/min, None with fewer than 2 converted prices or min <= 0.

    Callers pass the cheapest-N page of a price-ascending search, so these describe the cheap end of
    the market, not the whole of it.
    """
    prices: list[float] = []
    unconverted: list[str] = []
    for ls in listings:
        price = ls.get("price")
        if not price or price.get("amount") is None:
            continue
        currency = price.get("currency") or ""
        value = to_exalted(price["amount"], currency, rates)
        if value is None:
            if currency not in unconverted:
                unconverted.append(currency)
            continue
        prices.append(value)

    prices.sort()
    n = len(prices)
    median = None
    if n:
        mid = n // 2
        median = prices[mid] if n % 2 else (prices[mid - 1] + prices[mid]) / 2
    return {
        "count": len(listings),
        "converted": n,
        "unconvertedCurrencies": unconverted,
        "minExalted": prices[0] if n else None,
        "medianExalted": median,
        "maxExalted": prices[-1] if n else None,
        "spreadRatio": prices[-1] / prices[0] if n >= 2 and prices[0] > 0 else None,
    }


def summarize_listing(entry: dict[str, Any]) -> dict[str, Any]:
    """Flatten one fetch result into a compact, skill-friendly listing summary (no whisper auto-send)."""
    listing = entry.get("listing", {}) or {}
    item = entry.get("item", {}) or {}
    price = listing.get("price") or {}
    account = listing.get("account") or {}
    return {
        "name": (item.get("name") or "").strip() or None,
        "baseType": item.get("baseType"),
        "typeLine": item.get("typeLine"),
        "rarity": item.get("rarity"),
        "ilvl": item.get("ilvl"),
        "price": None if not price else {
            "amount": price.get("amount"),
            "currency": price.get("currency"),
            "type": price.get("type"),
        },
        "explicitMods": _mod_texts(item.get("explicitMods")),
        "seller": account.get("name"),
        "online": account.get("online") is not None,
        # whisper text is provided so the PLAYER can copy it themselves; the tool never sends it.
        "whisper": listing.get("whisper"),
    }
