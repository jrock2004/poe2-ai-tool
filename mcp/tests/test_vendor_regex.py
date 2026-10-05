"""Unit tests for the vendor regex composer.

Tests don't pin exact strings -- fragment choices will change. They run the composed regex through
`highlights`, a model of the in-game search box, against item texts, and check what lights up.
"""
import asyncio
import json
import re
from pathlib import Path

import pytest

from poe2_mcp import server
from poe2_mcp.vendor_regex import (
    LIMIT, MODS, TIERS, VendorRegex, Want, _between, _fixed, build_vendor_regex,
)

_GROUP = re.compile(r'"(!?)([^"]*)"')


def highlights(search: str, item_text: str) -> bool:
    """The search box: every quoted group must hold (AND); a group holds when its pattern matches some
    line of the item, case-insensitively -- or, for a `!` group, when it matches none."""
    groups = _GROUP.findall(search)
    assert groups and _GROUP.sub("", search).strip() == "", f"not a sequence of quoted groups: {search!r}"
    lines = item_text.splitlines()
    for negated, pattern in groups:
        hit = any(re.search(pattern, line, re.IGNORECASE) for line in lines)
        if hit == bool(negated):
            return False
    return True


def item(item_class: str, *lines: str) -> str:
    return "\n".join([f"Item Class: {item_class}", "Rarity: Magic", *lines])


# John's minion build: sceptres and ES gear; never martial weapons or quivers.
MINION = dict(
    want=[
        Want("movement_speed", min_value=25, any_base=True),
        Want("spirit", any_base=True),
        Want("minion_skills", any_base=True),
        Want("charges_per_second", any_base=True),
        Want("minion_life_recovery", any_base=True),
        Want("max_energy_shield"),
        Want("increased_energy_shield"),
        Want("resistance"),
        Want("max_life", min_value=40),
    ],
    want_classes=["sceptre"],
    hide_classes=["one_hand_mace", "two_hand_mace", "staff", "spear", "crossbow", "bow", "quiver", "wand",
                  "quarterstaff"],
    slot_classes=["sceptre", "amulet", "ring", "belt"],
    slot_defences=["energy_shield"],
)

ES_GLOVES = ("Gloves", "Energy Shield: 20")
ARMOUR_GLOVES = ("Gloves", "Armour: 40")


@pytest.mark.parametrize("text, lit", [
    (item("Sceptres", "Spirit: 100"), True),                                  # wanted class, no mods needed
    (item(*ES_GLOVES, "+12% to Fire Resistance"), True),                     # wanted mod on an ES base
    (item(*ARMOUR_GLOVES, "+12% to Fire Resistance"), False),                # wanted mod, wrong base
    (item(*ARMOUR_GLOVES, "+1 to Level of all Minion Skills"), True),        # any-base mod passes the gate
    (item("Boots", "Armour: 40", "25% increased Movement Speed"), True),
    (item("Boots", "Armour: 40", "20% increased Movement Speed"), False),   # under min_value
    (item("Rings", "+45 to maximum Life"), True),
    (item("Rings", "+39 to maximum Life"), False),
    (item("Rings", "+12 to Stun Threshold"), False),                        # "Th-res-hold" isn't a resistance
    (item("Quivers", "+1 to Level of all Minion Skills"), False),            # hidden class beats any wanted mod
    (item("Bows", "+30 to Spirit"), False),
    (item(*ES_GLOVES), False),                                                # right base, nothing wanted
])
def test_minion_build_highlights(text, lit):
    assert highlights(build_vendor_regex(**MINION).regex, text) is lit


def test_fits_and_reports_its_length():
    out = build_vendor_regex(**MINION)
    assert isinstance(out, VendorRegex)
    assert out.length == len(out.regex) <= LIMIT
    assert out.dropped == ()


def test_drops_lowest_priority_wants_to_fit():
    full = build_vendor_regex(**MINION)
    out = build_vendor_regex(**MINION, limit=full.length - 1)
    assert out.length <= full.length - 1
    assert out.dropped[0] == "max_life"
    # what survives still works; what was dropped no longer lights
    assert highlights(out.regex, item("Sceptres"))
    assert not highlights(out.regex, item("Rings", "+45 to maximum Life"))


def test_any_base_want_is_dropped_from_both_groups():
    without = build_vendor_regex(want=[Want("resistance")], slot_classes=["ring"])
    out = build_vendor_regex(
        want=[Want("resistance"), Want("spirit", any_base=True)], slot_classes=["ring"], limit=without.length,
    )
    assert out.dropped == ("spirit",)
    assert not highlights(out.regex, item("Rings", "+30 to Spirit"))                       # want group
    assert not highlights(out.regex, item(*ARMOUR_GLOVES, "+30 to Spirit", "+10% to Fire Resistance"))  # gate


@pytest.mark.parametrize("n, yes, no", [
    (0, ["0", "7"], []),
    (5, ["5", "9", "10", "123"], ["4"]),
    (40, ["40", "99", "100", "139", "140"], ["39", "9"]),
    (25, ["25", "29", "30", "35"], ["24", "20", "5"]),
    (90, ["90", "99", "100"], ["89"]),
    (95, ["95", "100"], ["94"]),
])
def test_min_value_matches_whole_numbers(n, yes, no):
    rx = build_vendor_regex(want=[Want("max_life", min_value=n)]).regex
    for v in yes:
        assert highlights(rx, f"+{v} to maximum Life"), v
    for v in no:
        assert not highlights(rx, f"+{v} to maximum Life"), v


def test_no_gate_without_slots():
    out = build_vendor_regex(want=[Want("spirit")])
    assert highlights(out.regex, item("Body Armours", "Armour: 100", "+30 to Spirit"))


def test_classes_alone_over_limit_raise():
    with pytest.raises(ValueError):
        build_vendor_regex(want=[], hide_classes=["quiver", "bow"], limit=5)


@pytest.mark.parametrize("kwargs", [
    dict(want=[Want("not_a_mod")]),
    dict(want=[Want("spirit", min_value=10)]),       # spirit's fragment has no {n}
    dict(want=[], hide_classes=["not_a_class"]),
    dict(want=[], slot_defences=["not_a_defence"]),
    dict(want=[], avoid=["not_a_mod"]),
])
def test_unknown_keys_raise(kwargs):
    with pytest.raises(ValueError):
        build_vendor_regex(**kwargs)




def test_between_matches_exactly_its_range():
    for lo in range(100):
        for hi in range(lo, 100):
            rx = re.compile(_between(lo, hi))
            got = [v for v in range(100) if rx.fullmatch(str(v))]
            assert got == list(range(lo, hi + 1)), (lo, hi, rx.pattern)



def test_fixed_matches_exactly_its_three_digit_range():
    ranges = [*((lo, hi) for lo in range(100, 1000, 37) for hi in range(lo, 1000, 41)),
              (100, 100), (100, 999), (199, 200), (100, 214), (150, 174), (999, 999)]
    for lo, hi in ranges:
        rx = re.compile("|".join(_fixed(lo, hi, 3)))
        assert [v for v in range(1000) if rx.fullmatch(str(v))] == list(range(lo, hi + 1)), (lo, hi, rx.pattern)


@pytest.mark.parametrize("item_level, yes, no", [
    (None, [100, 149, 214], [99, 50]),
    (60, [100, 149], [99, 50]),          # life tops out at 149 here
    (80, [120, 214], [119, 12]),
])
def test_life_100_and_up(item_level, yes, no):
    min_value = 120 if item_level == 80 else 100
    out = build_vendor_regex(want=[Want("max_life", min_value=min_value)], item_level=item_level)
    assert out.unreachable == ()
    for v in yes:
        assert highlights(out.regex, f"+{v} to maximum Life"), v
    for v in no:
        assert not highlights(out.regex, f"+{v} to maximum Life"), v


def test_life_100_is_unreachable_below_its_tier():
    assert build_vendor_regex(want=[Want("max_life", min_value=100)], item_level=50).unreachable == ("max_life",)


@pytest.mark.parametrize("min_value", [215, 1000])
def test_life_above_its_highest_roll_raises(min_value):
    with pytest.raises(ValueError):
        build_vendor_regex(want=[Want("max_life", min_value=min_value)])


def test_movement_speed_stops_at_its_highest_roll():
    rx = build_vendor_regex(want=[Want("movement_speed", min_value=25)]).regex
    assert "\\d{3}" not in rx
    for v, lit in [(25, True), (30, True), (35, True), (24, False), (20, False)]:
        assert highlights(rx, f"{v}% increased Movement Speed") is lit, v
    with pytest.raises(ValueError):
        build_vendor_regex(want=[Want("movement_speed", min_value=40)])     # nothing rolls that high


# --- Item level: what the vendor's items can roll --------------------------------------------------------


def test_tiers_ascend():
    for key, tiers in TIERS.items():
        levels, values = zip(*tiers)
        assert list(levels) == sorted(set(levels)) and list(values) == sorted(set(values)), key
        assert "{n}" in MODS[key], key


def test_item_level_caps_the_pattern():
    rx = build_vendor_regex(want=[Want("max_life", min_value=40)], item_level=50).regex
    assert "\\d{3}" not in rx                                   # life tops out at 99 below item level 54
    for v, lit in [(40, True), (99, True), (39, False)]:
        assert highlights(rx, f"+{v} to maximum Life") is lit, v


def test_item_level_past_100_still_matches_three_digits():
    rx = build_vendor_regex(want=[Want("max_life", min_value=40)], item_level=60).regex
    assert highlights(rx, "+145 to maximum Life")


def test_unreachable_wants_are_left_out():
    out = build_vendor_regex(want=[Want("movement_speed", min_value=30), Want("spirit")], item_level=60)
    assert out.unreachable == ("movement_speed",)
    assert out.dropped == ()
    assert not highlights(out.regex, "30% increased Movement Speed")
    assert highlights(out.regex, "+30 to Spirit")


def test_reachable_at_its_tier():
    out = build_vendor_regex(want=[Want("movement_speed", min_value=25)], item_level=65)
    assert out.unreachable == ()
    for v, lit in [(25, True), (30, True), (20, False)]:
        assert highlights(out.regex, f"{v}% increased Movement Speed") is lit, v


@pytest.mark.parametrize("level", [0, -5])
def test_item_level_must_be_positive(level):
    with pytest.raises(ValueError):
        build_vendor_regex(want=[Want("spirit")], item_level=level)


def test_tool_passes_item_level_through():
    out = asyncio.run(server.build_vendor_regex(
        want=[{"key": "movement_speed", "min_value": 30}, {"key": "spirit"}], item_level=60))
    assert out["valid"] and out["unreachable"] == ["movement_speed"]


# A spectre build that wants flask charges on any base, but never a flask that drains life or mana.
FLASKS = dict(
    want=[Want("charges_per_second", any_base=True), Want("resistance")],
    hide_classes=["quiver"],
    slot_classes=["ring"],
    avoid=["flask_removes_recovery"],
)


@pytest.mark.parametrize("text, lit", [
    (item("Life Flasks", "Gains 0.17 Charges per Second"), True),               # any_base passes the gate
    (item("Life Flasks", "Gains 0.17 Charges per Second",
          "Removes 15% of Mana Recovered from Life when used"), False),          # avoided mod rules it out
    (item("Mana Flasks", "Removes 15% of Life Recovered from Mana when used"), False),
    (item("Life Flasks", "20% increased Charges per use"), False),               # a downside, not charges/sec
    (item("Rings", "+12% to Fire Resistance"), True),                            # avoid doesn't touch the rest
])
def test_flask_wants_and_avoids(text, lit):
    assert highlights(build_vendor_regex(**FLASKS).regex, text) is lit


def test_avoid_is_never_dropped():
    out = build_vendor_regex(**{**FLASKS, "limit": len(build_vendor_regex(**FLASKS).regex) - 1})
    assert out.dropped == ("resistance",)
    assert not highlights(out.regex, item("Life Flasks", "Gains 0.17 Charges per Second",
                                          "Removes 15% of Mana Recovered from Life when used"))


# --- Fragments against the trade stat list ---------------------------------------------------------------
#
# trade2_stat_texts.json holds the Explicit + Implicit entry texts from trade2 /data/stats. It is broader
# than vendor gear (jewel radius, uniques, monster and map mods), so a fragment isn't required to match
# only its target. Instead: it must match every TARGET, and miss every TRAP -- mods that do roll on gear and
# a looser fragment once caught. Refresh the fixture per patch from /data/stats (Explicit + Implicit
# `text`s, sorted, deduplicated), then rerun: a renamed mod fails test_targets_and_traps_still_exist.

STAT_TEXTS = json.loads((Path(__file__).parent / "trade2_stat_texts.json").read_text(encoding="utf-8"))["texts"]

TARGETS = {
    "movement_speed": ["#% increased Movement Speed"],
    "spirit": ["# to Spirit"],
    "minion_skills": ["# to Level of all Minion Skills"],
    "max_energy_shield": ["# to maximum Energy Shield"],
    "increased_energy_shield": ["#% increased Energy Shield", "#% increased Evasion and Energy Shield"],
    "resistance": ["#% to Fire Resistance", "#% to Cold Resistance", "#% to Lightning Resistance",
                   "#% to Chaos Resistance", "#% to all Elemental Resistances"],
    "max_life": ["# to maximum Life"],
    "minion_life_recovery": ["Grants #% of Life Recovery to Minions"],
    "charges_per_second": ["Gains # Charges per Second"],
    "flask_removes_recovery": ["Removes #% of Life Recovered from Mana when used",
                               "Removes #% of Mana Recovered from Life when used"],
}

TRAPS = {
    "resistance": ["# to Stun Threshold"],                                   # "Th-res-hold"
    "increased_energy_shield": ["#% increased Damage against Immobilised Enemies",
                                "#% increased Endurance Charge Duration"],    # "sed en"
    "charges_per_second": ["# to all Attributes per Level",                  # "es per"
                           "#% increased Charges per use"],                   # "ges per"
    "flask_removes_recovery": ["Remnants can be collected from #% further away"],  # "^rem"
    "max_life": ["Regenerate #% of maximum Life per second"],                # "\d.*m life"
    "movement_speed": ["#% less Movement Speed"],
}


def _lights(key: str, stat_text: str) -> bool:
    rx = build_vendor_regex(want=[Want(key, min_value=1 if "{n}" in MODS[key] else None)]).regex
    return highlights(rx, stat_text.replace("#", "30"))   # a value every mod can roll


def test_every_mod_has_a_target():
    assert set(TARGETS) == set(MODS)


def test_targets_and_traps_still_exist():
    known = set(STAT_TEXTS)
    missing = [t for texts in (*TARGETS.values(), *TRAPS.values()) for t in texts if t not in known]
    assert not missing, f"not in the stat list any more (renamed this patch?): {missing}"


@pytest.mark.parametrize("key", sorted(MODS))
def test_fragment_hits_targets_and_misses_traps(key):
    assert [t for t in TARGETS[key] if not _lights(key, t)] == []
    assert [t for t in TRAPS.get(key, []) if _lights(key, t)] == []


# --- The MCP tool: JSON in, the same string out, errors as {valid: False} -----------------------------------


def test_tool_matches_the_pure_builder():
    out = asyncio.run(server.build_vendor_regex(
        want=[{"key": "movement_speed", "min_value": 25, "any_base": True}, {"key": "resistance"}],
        slot_classes=["ring"], avoid=["flask_removes_recovery"],
    ))
    pure = build_vendor_regex(want=[Want("movement_speed", 25, any_base=True), Want("resistance")],
                              slot_classes=["ring"], avoid=["flask_removes_recovery"])
    assert out == {"valid": True, "regex": pure.regex, "length": pure.length, "limit": LIMIT, "dropped": [],
                   "unreachable": []}


@pytest.mark.parametrize("want", [
    [{"key": "not_a_mod"}],
    [{"min_value": 25}],          # no key
    ["spirit"],                   # not an object
])
def test_tool_reports_bad_input(want):
    out = asyncio.run(server.build_vendor_regex(want=want))
    assert out["valid"] is False and out["error"]


def test_tool_description_lists_every_key():
    tool = next(t for t in asyncio.run(server.mcp.list_tools()) if t.name == "build_vendor_regex")
    for key in (*MODS, "sceptre", "energy_shield"):
        assert key in tool.description
