"""Unit tests for the stash-layout reading view and the get_stash_layout core (pure, no network).

reading_view is tested on hand-built slots; stash_layout on the committed 0.5.5 snapshot, whose rows
were checked against real screenshots when it was generated.
"""
from poe2_mcp.stashlayout import Slot, latest_version, load_snapshot, reading_view, stash_layout


def slot(key, item=None, x=0, y=0, *, w=1, h=1, size=78, hidden=False, sub_tab=None, label=None):
    return Slot(key=key, item=item, x=x, y=y, w=w, h=h, size=size,
                hidden_when_empty=hidden, sub_tab=sub_tab, group=None, label=label)


def row_keys(view):
    return [[s["key"] for s in row["slots"]] for row in view["rows"]]


def test_rows_read_top_to_bottom_then_left_to_right():
    view = reading_view([slot("c", "C", 100, 100), slot("b", "B", 100, 0), slot("a", "A", 0, 0)])
    assert row_keys(view) == [["a", "b"], ["c"]]


def test_a_slot_within_half_a_slot_joins_the_row():
    # size 78: half is 39. Measured from the row's first slot, not the previous one.
    view = reading_view([slot("a", "A", 0, 0), slot("b", "B", 100, 39), slot("c", "C", 200, 40)])
    assert row_keys(view) == [["a", "b"], ["c"]]


def test_row_slots_are_ordered_by_x_even_when_lower():
    view = reading_view([slot("lower_left", "L", 0, 30), slot("upper_right", "R", 100, 0)])
    assert row_keys(view) == [["lower_left", "upper_right"]]


def test_crafting_slot_is_left_out_of_rows():
    view = reading_view([slot("CraftingSlot", None, 0, 0, w=2, h=4, size=60), slot("a", "A", 200, 0)])
    assert row_keys(view) == [["a"]]
    assert view["craftingSlot"] is True
    assert reading_view([slot("a", "A")])["craftingSlot"] is False


def test_open_slots_stay_in_rows():
    view = reading_view([slot("a", "A", 0, 0), slot("Generic1", None, 100, 0)])
    assert view["rows"][0]["slots"] == [{"key": "a", "item": "A"}, {"key": "Generic1", "item": None}]


def test_hidden_slots_are_listed_separately():
    view = reading_view([slot("a", "A", 0, 0), slot("h", "H", 10, 90, hidden=True, sub_tab=None)])
    assert row_keys(view) == [["a"]]
    assert view["onlyWhenHeld"] == [{"key": "h", "item": "H", "subTab": None}]


def test_sub_tabs_split_rows_and_come_in_order():
    view = reading_view([slot("p1", "P1", 0, 0, sub_tab=1), slot("p0", "P0", 100, 0, sub_tab=0)])
    assert row_keys(view) == [["p0"], ["p1"]]
    assert [row["subTab"] for row in view["rows"]] == [0, 1]


def test_slot_extras_only_when_set():
    view = reading_view([slot("wide", "W", 0, 0, w=2, h=2), slot("omen", "O", 200, 0, label="Exalted")])
    assert view["rows"][0]["slots"] == [
        {"key": "wide", "item": "W", "w": 2, "h": 2},
        {"key": "omen", "item": "O", "label": "Exalted"},
    ]


def test_overlaps_reported_by_key():
    view = reading_view([slot("big", "B", 0, 0, w=2), slot("under", "U", 40, 0)])
    assert view["overlaps"] == [["big", "under"]]


def test_stacked_hidden_open_slots_are_not_overlaps():
    stacked = [slot(f"Map{i}", None, 0, 0, hidden=True) for i in range(3)]
    assert reading_view(stacked)["overlaps"] == []
    # ...but one of them over a real slot still is.
    assert reading_view([*stacked[:1], slot("real", "R", 0, 0)])["overlaps"] == [["Map0", "real"]]


# --- the committed snapshot ---------------------------------------------------------------------

def items(row):
    return [s["item"] for s in row["slots"]]


def test_latest_version_is_the_committed_snapshot():
    assert latest_version() == "0_5_5"


def test_load_snapshot_rejects_malformed_versions():
    for bad in ("0_5", "../0_5_5", "0_5_5x", ""):
        assert load_snapshot(bad) is None, bad
    assert load_snapshot("9_9_9") is None


def test_currency_layout():
    out = stash_layout("currency")
    assert (out["tab"], out["version"], out["patch"]) == ("currency", "0_5_5", "0.5.5")
    assert "16088913" in out["source"]
    assert out["craftingSlot"] is True
    assert out["overlaps"] == []
    assert items(out["rows"][0]) == [
        "Orb of Transmutation", "Greater Orb of Transmutation", "Perfect Orb of Transmutation",
        "Orb of Alchemy", "Vaal Orb", "Orb of Annulment",
        "Lesser Jeweller's Orb", "Greater Jeweller's Orb", "Perfect Jeweller's Orb",
    ]
    # Etcher/Scrap/Whetstone sit 30px lower than Regal: half-a-slot puts them in the same row.
    assert items(out["rows"][2]) == [
        "Regal Orb", "Greater Regal Orb", "Perfect Regal Orb", "Mirror of Kalandra", "Hinekora's Lock",
        "Arcanist's Etcher", "Armourer's Scrap", "Blacksmith's Whetstone",
    ]
    assert items(out["rows"][-1]) == [None] * 7  # the bottom open row


def test_ritual_layout():
    out = stash_layout("ritual")
    assert [sorted(p) for p in out["overlaps"]] == [["CurrencyRitualShard", "RitualPinnacleKey"]]
    held = {s["item"] for s in out["onlyWhenHeld"]}
    assert "Omen of Sinistral Coronation" in held
    exalt = next(s for row in out["rows"] for s in row["slots"] if s["item"] == "Omen of Sinistral Exaltation")
    assert exalt["label"] == "Exalted"


def test_delirium_stacked_map_slots_are_not_overlaps():
    assert stash_layout("delirium")["overlaps"] == []


def test_socketable_rows_go_page_by_page():
    pages = [row["subTab"] for row in stash_layout("socketable")["rows"]]
    assert pages == sorted(pages)
    assert set(pages) == {0, 1, 2, 3, 4}


def test_unknown_tab_is_an_error_not_a_raise():
    out = stash_layout("maps")
    assert out["valid"] is False
    assert "currency" in out["note"]
