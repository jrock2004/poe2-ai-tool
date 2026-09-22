"""Cache primitives shared by the network clients: a response body plus when it was fetched.

Freshness is a confidence signal (see skills/poe2-core/references/confidence.md), so a cached answer
has to carry the time *our* copy was fetched, not the time it was served from cache. That age is a
lower bound on how old the data really is -- upstreams like poe2scout cache prices themselves.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Fetched(Generic[T]):
    """A response body and the wall-clock time (epoch seconds, `time.time()`) it was fetched upstream.

    A cache hit returns the original Fetched, so `fetched_at` never moves forward on a hit.
    """

    body: T
    fetched_at: float


@dataclass
class CacheEntry:
    expires: float  # time.monotonic() deadline -- immune to wall-clock jumps
    fetched: Fetched[Any]


def freshness(*sources: Fetched[Any], now: float | None = None) -> dict[str, Any]:
    """Freshness of an answer built from `sources`: {"fetchedAt", "ageSeconds"} of the OLDEST one.

    An answer is only as fresh as its stalest input. fetchedAt is ISO-8601 UTC to the second
    ('2026-09-22T14:03:05Z'); ageSeconds is a whole number, floored, and never negative (clock skew
    clamps to 0). `now` defaults to time.time(). Raises ValueError with no sources.
    """
    if not sources:
        raise ValueError("freshness needs at least one Fetched source")
    oldest = min(s.fetched_at for s in sources)
    now = time.time() if now is None else now
    return {
        "fetchedAt": datetime.fromtimestamp(oldest, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ageSeconds": max(0, math.floor(now - oldest)),
    }
