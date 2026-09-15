"""Thin, read-only client for GGG's unofficial PoE 2 trade API (`/api/trade2`).

This is the ONE source that can search rare items by affix -- poe2scout cannot. It is unofficial,
undocumented, and IP-rate-limited, so this client is deliberately conservative:

* **Read-only.** It searches and fetches listings. It never buys, whispers, or touches an account.
* **Rate-limit aware.** GGG returns its policy in `X-Rate-Limit-*` headers; we parse them, self-throttle
  before we hit a bucket ceiling, and honor `Retry-After` / active timeouts on 429.
* **Cached hard.** Identical searches/fetches inside the TTL never re-hit the network.
* **Offline-first.** Query construction (`build_query`) and stat lookup are pure/cached; only
  `search` and `fetch` make live calls, and callers gate those.

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
class _CacheEntry:
    expires: float
    body: Any


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
    def __init__(self, min_gap_s: float = 1.0, ttl_s: float = 300.0, stats_ttl_s: float = 21600.0):
        self._cache: dict[str, _CacheEntry] = {}
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
        )
        self._stats_index: list[dict[str, str]] | None = None

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
                    ttl: float | None = None) -> Any:
        if cache_key:
            hit = self._cache.get(cache_key)
            if hit and hit.expires > time.monotonic():
                return hit.body
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
        body = resp.json()
        if cache_key:
            self._cache[cache_key] = _CacheEntry(time.monotonic() + (ttl or self._ttl_s), body)
        return body

    async def _stats(self) -> list[dict[str, Any]]:
        body = await self._live("GET", "/api/trade2/data/stats", cache_key="data/stats",
                                ttl=self._stats_ttl_s)
        return body.get("result", [])

    async def stat_index(self) -> list[dict[str, str]]:
        """Flattened, normalized {id, text, type, norm} list of every stat filter, cached."""
        if self._stats_index is not None:
            return self._stats_index
        idx: list[dict[str, str]] = []
        for group in await self._stats():
            for e in group.get("entries", []):
                text = e.get("text", "")
                idx.append({"id": e.get("id", ""), "text": text, "type": e.get("type", ""),
                            "norm": _normalize_affix(text)})
        self._stats_index = idx
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

    async def search(self, league: str, query: dict[str, Any]) -> dict[str, Any]:
        path = f"/api/trade2/search/{REALM}/{quote(league, safe='')}"
        key = f"search:{league}:{_stable(query)}"
        return await self._live("POST", path, json_body=query, cache_key=key)

    async def fetch(self, query_id: str, hashes: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i in range(0, len(hashes), FETCH_BATCH):
            batch = hashes[i : i + FETCH_BATCH]
            path = f"/api/trade2/fetch/{','.join(batch)}?query={query_id}"
            key = f"fetch:{query_id}:{i}"
            body = await self._live("GET", path, cache_key=key)
            out.extend(body.get("result") or [])
        return out


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
