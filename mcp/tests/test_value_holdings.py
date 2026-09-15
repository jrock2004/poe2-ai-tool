"""Unit tests for the pure holdings-valuation logic."""
import math

from poe2_mcp.poe2scout import value_holdings

# Minimal stand-in for a poe2scout /Items slice: Exalted is the base (price 1).
ITEMS = [
    {"Name": None, "Text": "Exalted Orb", "CurrentPrice": 1},
    {"Name": None, "Text": "Divine Orb", "CurrentPrice": 450.0},
    {"Name": None, "Text": "Chaos Orb", "CurrentPrice": 47.0},
    {"Name": "Headhunter", "Text": "Headhunter Heavy Belt", "CurrentPrice": 90000.0},
    {"Name": None, "Text": "Weird Unpriced Orb", "CurrentPrice": None},
]


def test_values_and_totals_in_exalted_and_divine():
    out = value_holdings(
        ITEMS,
        [{"name": "Exalted Orb", "count": 900}, {"name": "Divine Orb", "count": 2}],
        divine_price=450.0,
    )
    # 900 ex + 2*450 ex = 1800 ex = 4 div
    assert out["totalExalted"] == 1800.0
    assert out["totalDivine"] == 4.0
    assert out["unmatched"] == []
    assert len(out["lines"]) == 2


def test_matches_by_short_name_too():
    out = value_holdings(ITEMS, [{"name": "headhunter", "count": 1}], divine_price=450.0)
    assert out["lines"][0]["name"] == "Headhunter"
    assert out["lines"][0]["valueExalted"] == 90000.0


def test_unmatched_and_unpriced_are_reported_not_guessed():
    out = value_holdings(
        ITEMS,
        [{"name": "Nonexistent Orb", "count": 5}, {"name": "Weird Unpriced Orb", "count": 3}],
        divine_price=450.0,
    )
    assert out["totalExalted"] == 0.0
    assert set(out["unmatched"]) == {"Nonexistent Orb", "Weird Unpriced Orb"}
    assert out["lines"] == []


def test_divine_is_nan_when_price_unknown():
    out = value_holdings(ITEMS, [{"name": "Chaos Orb", "count": 1}], divine_price=0)
    assert math.isnan(out["totalDivine"])
    assert out["totalExalted"] == 47.0
