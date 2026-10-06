"""Unit tests for stash-tab layout normalization (pure, no network).

Every row below is copied verbatim from repoe-fork/dat-export@16088913 (game 4.5.5.2),
current/poe2/heuristics/csv/<Tab>StashTabLayout.csv -- headers included, because the export's
column names are guesses and the tests pin which guess means what.
"""
import csv
import io

import pytest

from poe2_mcp.stashlayout import TABS, Slot, normalize, overlaps

# BaseItemTypes rownum -> Name, for just the items the rows below reference.
NAMES = {
    0: "Blacksmith's Whetstone",
    13: "Orb of Transmutation",
    114: "Greater Essence of Abrasion",
    177: "Breach Splinter",
    193: "Simulacrum Splinter",
    194: "Petition Splinter",
    277: "Flesh Catalyst",
    480: "Head of the King",
    481: "Breachlord Sac",
    634: "Lesser Desert Rune",
    911: "An Audience with the King",
    1459: "Expedition Logbook",
    4254: "Ancient Crisis Fragment",
    4440: "Omen of Sinistral Coronation",
    4444: "Omen of Sinistral Exaltation",
    4469: "Omen of Abyssal Echoes",
    5060: "Verisium",
}

CSV = {
    "currency": '''"rownum","Id","StoredItem","XOffset","YOffset","FirstSlotIndex","Width","Height","ShowIfEmpty","SlotGroup","SlotSize","SlotStyle"
0,"Metadata/Items/Currency/CurrencyUpgradeToMagic",13,29,40,0,1,1,1,0,78,0
14,"Metadata/Items/Currency/CurrencyWeaponQuality",0,829,270,13,1,1,1,0,78,0
26,"CraftingSlot","",408,354,25,2,4,1,2,60,0
27,"Generic1","",159,740,27,1,1,1,2,78,1
''',
    "essence": '''"rownum","Id","StoredItem","XOffset","YOffset","FirstSlotIndex","Width","Height","ShowIfEmpty","SlotSize","SlotStyle"
15,"Metadata/Items/Currency/CurrencyGreaterEssencePhysical",114,738,120,15,1,1,1,70,2
25,"Generic1","",394,480,26,1,1,1,70,1
''',
    "ritual": '''"rownum","Id","StoredItem","XOffset","YOffset","FirstSlotIndex","Width","Height","ShowIfEmpty","SlotSize","SlotStyle","MiniIcon"
0,"Metadata/Items/MapFragments/CurrencyRitualBossFragment",911,280,40,0,1,1,1,78,2,""
1,"Metadata/Items/Currency/OmenOnRegalPrefix",4440,10,90,1,1,1,"",60,0,""
6,"Metadata/Items/Currency/OmenOnExaltAddPrefixes",4444,139,320,6,1,1,1,78,0,"Art/2DArt/UIImages/InGame/MTX/RitualStash/RitualStashIconExalted"
22,"Metadata/Items/Currency/CurrencyRitualShard",194,429,40,22,1,1,1,78,3,""
37,"Metadata/Items/Currency/Ritual/RitualPinnacleKey",480,390,40,38,2,1,1,78,3,""
''',
    # No column names at all: i32_24/28 are X/Y, i32_32 the slot size, i32_44/48 width/height.
    "breach": '''"rownum","Id","BaseItemType","i32_24","i32_28","i32_32","i32_36","i32_40","i32_44","i32_48","bool_52","SlotStyle"
0,"Metadata/Items/Currency/CurrencyJewelleryQualityLife",277,179,450,78,0,0,1,1,"",0
28,"PinnacleKey",481,390,242,78,0,3,2,2,"",3
''',
    # Swapped: the column named "Tab" holds the slot size (always 78), "SlotSize" holds the sub-tab.
    "fragment": '''"rownum","Id","XOffset","YOffset","FirstSlotIndex","Width","Height","HideIfEmpty","Tab","SlotSize","BaseItemType","bool_53","SlotStyle"
0,"Metadata/Items/Pinnacle/BurningMonolithKey1",339,151,0,1,1,"",78,0,4254,"",2
6,"Metadata/Items/Currency/CurrencyBreachShard",101,281,0,1,1,"",78,1,177,"",0
''',
    # Same swap as fragment.
    "expedition": '''"rownum","Id","BaseItemType","XOffset","YOffset","Tab","HideIfEmpty","FirstSlotIndex","SlotSize","Width","Height","SlotStyle"
0,"Metal1",5060,279,408,78,"",0,0,1,1,0
19,"Logbook1",1459,179,78,78,"",0,1,1,1,0
''',
    "abyss": '''"rownum","Id","StoredItem","XOffset","YOffset","SlotSize","SlotStyle","HideIfEmpty","FirstSlotIndex","i32_57","Width","Height"
0,"Metadata/Items/Currency/OmenOnAbyssRerollOptions",4469,86,772,78,0,"",0,0,1,1
''',
    "delirium": '''"rownum","Id","StoredItem","XOffset","YOffset","FirstSlotIndex","Width","Height","SlotSize","i32_48","SlotStyle","ShowIfEmpty"
0,"Metadata/Items/Currency/CurrencyAfflictionShard",193,372,85,0,1,1,78,0,2,1
''',
    "socketable": '''"rownum","Id","StoredItem","XOffset","YOffset","FirstSlotIndex","Width","Height","ShowIfEmpty","SlotSize","SlotStyle","SubGroup"
0,"Metadata/Items/SoulCores/RuneFireLesser",634,29,111,0,1,1,1,78,0,0
''',
}


def rows(tab: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(CSV[tab])))


def slots(tab: str) -> dict[str, Slot]:
    return {s.key: s for s in normalize(tab, rows(tab), NAMES)}


def test_tabs_are_the_nine_exported():
    assert sorted(TABS) == sorted(CSV)


def test_every_tab_normalizes():
    for tab in TABS:
        assert len(normalize(tab, rows(tab), NAMES)) == len(rows(tab)), tab


def test_currency_fixed_slot():
    assert slots("currency")["CurrencyUpgradeToMagic"] == Slot(
        key="CurrencyUpgradeToMagic", item="Orb of Transmutation",
        x=29, y=40, w=1, h=1, size=78,
        hidden_when_empty=False, sub_tab=None, group=0, label=None,
    )


def test_item_index_zero_is_an_item_not_an_open_slot():
    assert slots("currency")["CurrencyWeaponQuality"].item == "Blacksmith's Whetstone"


def test_open_and_crafting_slots_have_no_item():
    s = slots("currency")
    assert s["Generic1"].item is None
    assert s["CraftingSlot"].item is None
    assert (s["CraftingSlot"].w, s["CraftingSlot"].h, s["CraftingSlot"].size) == (2, 4, 60)
    assert slots("essence")["Generic1"].item is None


def test_show_if_empty_blank_means_hidden():
    s = slots("ritual")
    assert s["OmenOnRegalPrefix"].hidden_when_empty is True
    assert s["OmenOnRegalPrefix"].size == 60
    assert s["CurrencyRitualBossFragment"].hidden_when_empty is False


def test_hide_if_empty_blank_means_shown():
    assert slots("fragment")["BurningMonolithKey1"].hidden_when_empty is False
    assert slots("abyss")["OmenOnAbyssRerollOptions"].hidden_when_empty is False


def test_ritual_label_is_the_icon_name():
    s = slots("ritual")
    assert s["OmenOnExaltAddPrefixes"].label == "Exalted"
    assert s["CurrencyRitualBossFragment"].label is None


def test_breach_unnamed_columns():
    s = slots("breach")["PinnacleKey"]
    assert (s.item, s.x, s.y, s.w, s.h, s.size) == ("Breachlord Sac", 390, 242, 2, 2, 78)


@pytest.mark.parametrize("tab,key,sub_tab", [
    ("fragment", "BurningMonolithKey1", 0),
    ("fragment", "CurrencyBreachShard", 1),
    ("expedition", "Metal1", 0),
    ("expedition", "Logbook1", 1),
])
def test_swapped_size_and_sub_tab(tab, key, sub_tab):
    s = slots(tab)[key]
    assert (s.size, s.sub_tab) == (78, sub_tab)


def test_socketable_sub_group_is_a_page():
    s = slots("socketable")["RuneFireLesser"]
    assert (s.sub_tab, s.group) == (0, None)


def test_unknown_tab_raises():
    with pytest.raises(ValueError, match="maps"):
        normalize("maps", [], NAMES)


def test_renamed_column_raises():
    # The exporter's guesses change between runs; a rename must fail loudly, not misread.
    renamed = [{("XOffset" if k == "i32_24" else k): v for k, v in r.items()} for r in rows("breach")]
    with pytest.raises(ValueError, match="i32_24"):
        normalize("breach", renamed, NAMES)


def test_unknown_item_raises():
    with pytest.raises(ValueError, match="13"):
        normalize("currency", rows("currency"), {k: v for k, v in NAMES.items() if k != 13})


@pytest.mark.parametrize("column,value", [("XOffset", "5000"), ("SlotSize", "0"), ("Width", "9")])
def test_out_of_range_geometry_raises(column, value):
    bad = rows("currency")
    bad[0][column] = value
    with pytest.raises(ValueError, match="CurrencyUpgradeToMagic"):
        normalize("currency", bad, NAMES)


def test_overlap_found():
    # Head of the King (x 390, two slots wide) covers Petition Splinter (x 429) -- real 0.5.5 data.
    pairs = overlaps(normalize("ritual", rows("ritual"), NAMES))
    assert [{a.key, b.key} for a, b in pairs] == [{"RitualPinnacleKey", "CurrencyRitualShard"}]


def test_touching_slots_do_not_overlap():
    a = Slot(key="a", item=None, x=0, y=0, w=1, h=1, size=78,
             hidden_when_empty=False, sub_tab=None, group=None, label=None)
    b = Slot(key="b", item=None, x=78, y=0, w=1, h=1, size=78,
             hidden_when_empty=False, sub_tab=None, group=None, label=None)
    assert overlaps([a, b]) == []


def test_different_sub_tabs_do_not_overlap():
    a = Slot(key="a", item=None, x=0, y=0, w=1, h=1, size=78,
             hidden_when_empty=False, sub_tab=0, group=None, label=None)
    assert overlaps([a, Slot(**{**a.__dict__, "key": "b", "sub_tab": 1})]) == []
