"""Unit tests for the shared cache/freshness primitives (pure, no network)."""
import pytest

from poe2_mcp._cache import Fetched, freshness

# 2026-09-22T14:00:00Z
T0 = 1790085600.0


def test_freshness_single_source():
    assert freshness(Fetched(body=[], fetched_at=T0), now=T0 + 90) == {
        "fetchedAt": "2026-09-22T14:00:00Z",
        "ageSeconds": 90,
    }


def test_freshness_reports_the_oldest_source():
    newer = Fetched(body=[], fetched_at=T0 + 200)
    older = Fetched(body=[], fetched_at=T0)
    fr = freshness(newer, older, now=T0 + 300)
    assert fr == {"fetchedAt": "2026-09-22T14:00:00Z", "ageSeconds": 300}


def test_freshness_age_is_floored_to_whole_seconds():
    assert freshness(Fetched(body=[], fetched_at=T0), now=T0 + 59.9)["ageSeconds"] == 59


def test_freshness_clamps_clock_skew_to_zero():
    assert freshness(Fetched(body=[], fetched_at=T0 + 5), now=T0)["ageSeconds"] == 0


def test_freshness_needs_a_source():
    with pytest.raises(ValueError):
        freshness(now=T0)
