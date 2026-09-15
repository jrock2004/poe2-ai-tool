import math

from poe2_mcp.poe2scout import exalted_to_divine


def test_exalted_to_divine_converts():
    assert exalted_to_divine(300, 150) == 2.0   # 300 exalted / 150 exalted-per-divine
    assert exalted_to_divine(75, 150) == 0.5


def test_exalted_to_divine_guards_bad_price():
    assert math.isnan(exalted_to_divine(300, 0))
    assert math.isnan(exalted_to_divine(300, -5))
