"""Unit tests for the game-data snapshot generator (pure, no network)."""
import json

import pytest

from poe2_mcp.gamedata import build_items, clean_text, render_items

HELM = "Metadata/Items/Armours/Helmets/"
BODY = "Metadata/Items/Armours/BodyArmours/"


@pytest.mark.parametrize("raw, clean", [
    ("+(41-45)% to [Resistances|Fire Resistance]", "+(41-45)% to Fire Resistance"),
    ("additional [Rune]-only sockets:", "additional Rune-only sockets:"),
    ("Grants Skill: <underline>{Fire Spell on Hit}", "Grants Skill: Fire Spell on Hit"),
    ("+(10-19) to maximum Life", "+(10-19) to maximum Life"),
])
def test_clean_text_strips_the_games_display_markup(raw, clean):
    assert clean_text(raw) == clean


# Shaped like repoe-fork/poe2's data/mods_by_base.json, mods.json and base_items.json (export 4.5.5.2),
# trimmed: real ids, names, requirements, levels and text. mods_by_base is item class -> base tag group ->
# {bases, mods by kind -> family -> {tier id: item level}}.
MODS_BY_BASE = {
    "Helmets": {
        "str_armour,ezomyte_basetype,helmet,armour,default": {
            "bases": [HELM + "FourHelmetStr1", HELM + "FourHelmetStr2"],
            "mods": {
                "prefix": {"IncreasedLife": {"IncreasedLife2": 6, "IncreasedLife1": 1}},  # out of order
                "suffix": {"FireResistance": {"FireResist1": 1, "FireResist8": 82}},
                "corrupted": {"FireResistance": {"FireResist1": 1}},
                "unique": {"IncreasedLife": {"IncreasedLife1": 1}},
            },
            "conditional_mods": None,
        },
    },
    "Body Armours": {
        "str_dex_armour,body_armour,armour,default": {
            "bases": [BODY + "FourBodyStrDex12a", BODY + "FourBodyStrDex12b"],
            "mods": {"prefix": {"IncreasedLife": {"IncreasedLife1": 1}}, "suffix": {}},
            "conditional_mods": None,
        },
        "dex_int_armour,karui_basetype,body_armour,armour,default": {
            "bases": [BODY + "FourBodyDexInt8"],
            "mods": {"prefix": {"IncreasedLife": {"IncreasedLife1": 1, "IncreasedLife2": 6}}, "suffix": {}},
            "conditional_mods": None,
        },
        "dex_int_armour,body_armour,armour,default": {
            "bases": [BODY + "FourBodyDexInt1Cruel"],
            "mods": {"prefix": {}, "suffix": {"FireResistance": {"FireResist1": 1}}},
            "conditional_mods": None,
        },
    },
    "Two Hand Swords": {
        "sword,two_hand_weapon,default": {
            "bases": ["Metadata/Items/Weapons/TwoHandWeapons/TwoHandSwords/TwoHandSwordDev"],
            "mods": {"prefix": {"IncreasedLife": {"IncreasedLife1": 1}}, "suffix": {}},
            "conditional_mods": None,
        },
    },
    "Stackable Currency": {
        "currency,default": {"bases": ["Metadata/Items/Currency/CurrencyModValues"], "mods": {}, "conditional_mods": None},
    },
}


def _mod(name, side, level, family, text):
    return {"name": name, "generation_type": side, "required_level": level, "type": family, "text": text,
            "domain": "item", "stats": []}


MODS = {
    "IncreasedLife1": _mod("Hale", "prefix", 1, "IncreasedLife", "+(10-19) to maximum Life"),
    "IncreasedLife2": _mod("Healthy", "prefix", 6, "IncreasedLife", "+(20-29) to maximum Life"),
    "FireResist1": _mod("of the Whelpling", "suffix", 1, "FireResistance", "+(6-10)% to [Resistances|Fire Resistance]"),
    "FireResist8": _mod("of Tzteosh", "suffix", 82, "FireResistance", "+(41-45)% to [Resistances|Fire Resistance]"),
    "Strength1": _mod("of the Brute", "suffix", 1, "Strength", "+(5-8) to [Strength|Strength]"),  # no group uses it
}


def _base(name, item_class, level, strength=0, dexterity=0, intelligence=0, release_state="released"):
    return {"name": name, "item_class": item_class, "release_state": release_state, "domain": "item",
            "requirements": {"level": level, "strength": strength, "dexterity": dexterity,
                             "intelligence": intelligence}}


BASE_ITEMS = {
    HELM + "FourHelmetStr1": _base("Rusted Greathelm", "Helmet", 1),
    HELM + "FourHelmetStr2": _base("Soldier Greathelm", "Helmet", 12, strength=19),
    BODY + "FourBodyStrDex12a": _base("Tournament Mail", "Body Armour", 68, strength=67, dexterity=67),
    BODY + "FourBodyStrDex12b": _base("Tournament Mail", "Body Armour", 68, strength=67, dexterity=67),
    BODY + "FourBodyDexInt8": _base("Ascetic Garb", "Body Armour", 51, dexterity=45, intelligence=45),
    BODY + "FourBodyDexInt1Cruel": _base("Ascetic Garb", "Body Armour", 45, dexterity=41, intelligence=41),
    "Metadata/Items/Weapons/TwoHandWeapons/TwoHandSwords/TwoHandSwordDev":
        _base("Keyblade", "Two Hand Sword", 1, release_state="unreleased"),
    "Metadata/Items/Currency/CurrencyModValues": _base("Divine Orb", "StackableCurrency", 1),
}


def _items():
    return build_items(MODS_BY_BASE, MODS, BASE_ITEMS)


def _pool(items, base, variant=0):
    return items["groups"][items["bases"][base][variant]["group"]]


def test_build_items_gives_a_base_its_pools_tiers_in_item_level_order():
    items = _items()
    assert items["bases"]["Rusted Greathelm"] == [
        {"class": "Helmets", "group": items["bases"]["Rusted Greathelm"][0]["group"],
         "requirements": {"level": 1, "str": 0, "dex": 0, "int": 0}}]
    assert _pool(items, "Rusted Greathelm") == {
        "prefix": {"IncreasedLife": ["IncreasedLife1", "IncreasedLife2"]},
        "suffix": {"FireResistance": ["FireResist1", "FireResist8"]},
    }
    assert _pool(items, "Soldier Greathelm") == _pool(items, "Rusted Greathelm")  # one tag group, one pool


def test_build_items_describes_each_tier_with_its_text_cleaned():
    assert _items()["mods"]["FireResist8"] == {
        "name": "of Tzteosh", "side": "suffix", "level": 82, "family": "FireResistance",
        "text": "+(41-45)% to Fire Resistance"}


def test_build_items_keeps_prefixes_and_suffixes_only():
    # Corruption and unique mods aren't rolled by crafting currency; a later slice can add corruption.
    assert all(set(group) == {"prefix", "suffix"} for group in _items()["groups"])


def test_build_items_lists_only_the_tiers_a_pool_uses():
    assert set(_items()["mods"]) == {"IncreasedLife1", "IncreasedLife2", "FireResist1", "FireResist8"}


def test_build_items_leaves_out_unreleased_bases_and_non_equipment_classes():
    bases = _items()["bases"]
    assert "Keyblade" not in bases and "Divine Orb" not in bases


def test_build_items_merges_same_named_bases_with_the_same_pool():
    assert len(_items()["bases"]["Tournament Mail"]) == 1


def test_build_items_keeps_same_named_variants_that_roll_different_pools():
    # Two "Ascetic Garb" bases (one a Cruel campaign variant) roll different mods: keep both, the
    # lower-level one first, so a lookup can tell them apart by their requirements.
    garb = _items()["bases"]["Ascetic Garb"]
    assert [v["requirements"]["level"] for v in garb] == [45, 51]
    assert garb[0]["group"] != garb[1]["group"]


@pytest.mark.parametrize("drop", ["mods", "base_items"])
def test_build_items_refuses_a_reference_it_cant_resolve(drop):
    # A tier or base the other file doesn't have means the export changed shape: fail, don't guess.
    mods = {k: v for k, v in MODS.items() if k != "FireResist8"} if drop == "mods" else MODS
    base_items = ({k: v for k, v in BASE_ITEMS.items() if not k.endswith("FourHelmetStr2")}
                  if drop == "base_items" else BASE_ITEMS)
    with pytest.raises(ValueError, match="FireResist8" if drop == "mods" else "FourHelmetStr2"):
        build_items(MODS_BY_BASE, mods, base_items)


def test_render_items_is_json_with_one_mod_per_line():
    text = render_items(_items(), "0.5.5", "repoe-fork/poe2@abc123 (game 4.5.5.2)")
    snapshot = json.loads(text)
    assert snapshot["patch"] == "0.5.5" and snapshot["source"] == "repoe-fork/poe2@abc123 (game 4.5.5.2)"
    assert {k: snapshot[k] for k in ("groups", "bases", "mods")} == _items()
    assert sum('"side":' in line for line in text.splitlines()) == len(snapshot["mods"])
    assert text.endswith("\n")
