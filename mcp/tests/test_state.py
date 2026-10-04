import asyncio
import copy

import pytest

from poe2_mcp import server
from poe2_mcp.state import SECTIONS, STATE_FILE, apply_update, empty_state, load, merge_patch, update


# --- merge_patch (RFC 7396) --------------------------------------------------------------------------

def test_merge_patch_merges_nested_objects():
    target = {"a": {"b": 1, "c": 2}, "d": 3}
    assert merge_patch(target, {"a": {"c": 9}}) == {"a": {"b": 1, "c": 9}, "d": 3}


def test_merge_patch_null_deletes_and_deleting_a_missing_key_is_a_no_op():
    assert merge_patch({"a": 1, "b": 2}, {"a": None, "zzz": None}) == {"b": 2}


def test_merge_patch_arrays_replace():
    assert merge_patch({"a": [1, 2, 3]}, {"a": [4]}) == {"a": [4]}


def test_merge_patch_non_object_patch_replaces_the_target():
    assert merge_patch({"a": 1}, [1, 2]) == [1, 2]
    assert merge_patch({"a": {"b": 1}}, {"a": "flat"}) == {"a": "flat"}


def test_merge_patch_object_patch_on_a_non_object_target_starts_from_empty():
    assert merge_patch("flat", {"a": 1, "b": None}) == {"a": 1}


def test_merge_patch_does_not_mutate_its_inputs():
    target = {"a": {"b": 1}, "l": [1]}
    patch = {"a": {"c": {"d": 2}}, "l": None}
    target_before, patch_before = copy.deepcopy(target), copy.deepcopy(patch)
    merged = merge_patch(target, patch)
    merged["a"]["c"]["d"] = 99
    assert target == target_before
    assert patch == patch_before


# --- apply_update ------------------------------------------------------------------------------------

def _two_characters() -> dict:
    return apply_update(
        empty_state(),
        {"characters": {"A": {"league": "Forbidden Rites", "active": True}, "B": {"league": "Standard"}}},
    )


def test_apply_update_rejects_an_unknown_section_listing_the_allowed_ones():
    with pytest.raises(ValueError, match="player, characters, currency, leagues"):
        apply_update(empty_state(), {"charcters": {"A": {}}})


def test_apply_update_rejects_a_non_object_patch():
    with pytest.raises(ValueError):
        apply_update(empty_state(), ["not", "an", "object"])


def test_apply_update_activating_one_character_clears_the_others():
    state = apply_update(_two_characters(), {"characters": {"B": {"active": True}}})
    assert state["characters"]["B"]["active"] is True
    assert state["characters"]["A"]["active"] is False


def test_apply_update_leaves_active_flags_alone_when_the_patch_does_not_set_one():
    state = apply_update(_two_characters(), {"characters": {"B": {"goal": "mapping"}}})
    assert state["characters"]["A"]["active"] is True
    assert "active" not in state["characters"]["B"]


def test_apply_update_keeps_the_version():
    assert apply_update(empty_state(), {"player": {"experience_level": "experienced"}})["version"] == 1


def test_apply_update_deletes_a_character_with_null():
    state = apply_update(_two_characters(), {"characters": {"A": None}})
    assert list(state["characters"]) == ["B"]


def test_apply_update_rejects_overwriting_the_version():
    with pytest.raises(ValueError, match="version"):
        apply_update(empty_state(), {"version": 2})


# --- load / update -----------------------------------------------------------------------------------

def test_load_missing_file_is_the_empty_state(tmp_path):
    assert load(tmp_path) == empty_state()
    assert set(SECTIONS) <= set(empty_state())


def test_load_fills_in_missing_sections(tmp_path):
    (tmp_path / STATE_FILE).write_text('{"version": 1, "player": {"experience_level": "new"}}', encoding="utf-8")
    state = load(tmp_path)
    assert state["player"] == {"experience_level": "new"}
    assert state["characters"] == {} and state["currency"] == {} and state["leagues"] == {}


def test_update_round_trips_through_load_with_lf_newlines(tmp_path):
    patch = {"currency": {"Forbidden Rites": {"trade": {"tabs": {"currency": {"items": []}}}}}}
    state = update(tmp_path, patch)
    assert load(tmp_path) == state
    assert state["currency"]["Forbidden Rites"]["trade"]["tabs"]["currency"] == {"items": []}
    assert b"\r" not in (tmp_path / STATE_FILE).read_bytes()


def test_update_rejected_patch_leaves_the_file_unchanged(tmp_path):
    update(tmp_path, {"player": {"experience_level": "new"}})
    before = (tmp_path / STATE_FILE).read_bytes()
    with pytest.raises(ValueError):
        update(tmp_path, {"oops": {}})
    assert (tmp_path / STATE_FILE).read_bytes() == before


def test_load_corrupt_file_raises_naming_the_path(tmp_path):
    (tmp_path / STATE_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match=STATE_FILE):
        load(tmp_path)


# --- tools -------------------------------------------------------------------------------------------

def test_update_state_then_get_state_round_trips(monkeypatch, tmp_path):
    monkeypatch.setenv("POE2_DATA_DIR", str(tmp_path))

    async def run():
        updated = await server.update_state({"leagues": {"Forbidden Rites": {"patch": "0.5.5"}}})
        return updated, await server.get_state()

    updated, got = asyncio.run(run())
    assert got == updated
    assert got["leagues"] == {"Forbidden Rites": {"patch": "0.5.5"}}
