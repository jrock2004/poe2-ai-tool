"""Unit tests for the campaign-rewards snapshot: parsing PoB2's QuestRewards.lua, rendering, the CLI, and
loading the committed snapshot (pure, no network).

The entries below are copied verbatim from PathOfBuilding-PoE2@b21d413d (dev, 2026-06-01),
src/Data/QuestRewards.lua: a stat reward, a weapon-set-point reward, a pick-one reward whose options run over
two lines, an interlude and the epilog.
"""
import json

import pytest

from poe2_mcp.campaign import latest_version, load_snapshot, main, parse_quest_rewards, render_snapshot

QUEST_REWARDS_LUA = r'''return {
	{
		["Act"] = 1,
		["Description"] = "Act 1",
		["Area"] = "Clearfell",
		["Info"] = "Beira",
		["Stat"] = "+10% to Cold Resistance",
		["AreaLevel"] = 2,
		["useConfig"] = true
	},
	{
		["Act"] = 1,
		["Description"] = "Act 1",
		["Area"] = "Hunting Grounds",
		["Info"] = "Crowbell",
		["Stat"] = "+2 Weapon Set Passive Skill Points",
		["questPoints"] = 2,
		["AreaLevel"] = 10,
		["useConfig"] = false
	},
	{
		["Act"] = 2,
		["Description"] = "Act 2",
		["Area"] = "Valley of the Titans",
		["Info"] = "Medallion",
		["Options"] = {
			"30% increased Charm Charges Gained\n\t+1 Charm Slot",
			"30% increased Charm Effect Duration\n\t+1 Charm Slot",
		},
		["AreaLevel"] = 26,
		["useConfig"] = true
	},
	{
		["Act"] = 5,
		["Description"] = "Interlude 1",
		["Area"] = "Wolvenhold",
		["Info"] = "Oswin",
		["Stat"] = "+2 Weapon Set Passive Skill Points",
		["questPoints"] = 2,
		["AreaLevel"] = 64,
		["useConfig"] = false
	},
	{
		["Act"] = 6,
		["Description"] = "Epilog",
		["Area"] = "Kingsmarch",
		["Info"] = "Siege Of Oriath",
		["Stat"] = "+2 Weapon Set Passive Skill Points",
		["questPoints"] = 2,
		["AreaLevel"] = 62,
		["useConfig"] = false
	},
}
'''

BEIRA = '''	{
		["Act"] = 1,
		["Description"] = "Act 1",
		["Area"] = "Clearfell",
		["Info"] = "Beira",
		%s
		["AreaLevel"] = 2,
		["useConfig"] = true
	},'''


def rewards() -> list[dict]:
    return parse_quest_rewards(QUEST_REWARDS_LUA)


def by_source(name: str) -> dict:
    return next(r for r in rewards() if r["from"] == name)


def one_entry(fields: str) -> str:
    """A file holding just Beira, with `fields` in place of her Stat line."""
    return "return {\n" + BEIRA % fields + "\n}\n"


def test_every_entry_in_the_files_order():
    # Campaign order, not area level: the epilog (62) comes after the interlude (64).
    assert [r["from"] for r in rewards()] == ["Beira", "Crowbell", "Medallion", "Oswin", "Siege Of Oriath"]


def test_a_stat_reward():
    assert by_source("Beira") == {
        "part": "Act 1", "area": "Clearfell", "from": "Beira", "areaLevel": 2, "stat": "+10% to Cold Resistance"}


def test_a_points_reward_carries_its_weapon_set_points():
    assert by_source("Crowbell") == {
        "part": "Act 1", "area": "Hunting Grounds", "from": "Crowbell", "areaLevel": 10,
        "stat": "+2 Weapon Set Passive Skill Points", "weaponSetPoints": 2}


def test_a_pick_one_reward_has_options_and_no_stat():
    # Each option keeps its line break; PoB's indenting tab after it goes.
    medallion = by_source("Medallion")
    assert "stat" not in medallion
    assert medallion["options"] == [
        "30% increased Charm Charges Gained\n+1 Charm Slot",
        "30% increased Charm Effect Duration\n+1 Charm Slot",
    ]


def test_part_is_the_description_not_the_act_number():
    assert [r["part"] for r in rewards()] == ["Act 1", "Act 1", "Act 2", "Interlude 1", "Epilog"]


def test_pob_only_fields_are_dropped():
    for r in rewards():
        assert not {"Act", "useConfig", "questPoints", "Info", "Description"} & set(r), r["from"]


@pytest.mark.parametrize("fields", [
    '["Stat"] = "+10% to Cold Resistance",\n\t\t["Options"] = { "+5 to Strength", },',  # both
    "",  # neither
])
def test_a_reward_needs_exactly_one_of_stat_and_options(fields):
    with pytest.raises(ValueError, match="Beira"):
        parse_quest_rewards(one_entry(fields))


def test_an_unknown_field_raises():
    # PoB changed the file's shape: fail loudly rather than drop what it added.
    with pytest.raises(ValueError, match="Bonus"):
        parse_quest_rewards(one_entry('["Stat"] = "+10% to Cold Resistance",\n\t\t["Bonus"] = 1,'))


def test_a_missing_field_raises():
    no_area = one_entry('["Stat"] = "+10% to Cold Resistance",').replace('\t\t["Area"] = "Clearfell",\n', "")
    with pytest.raises(ValueError, match="Area"):
        parse_quest_rewards(no_area)


def test_a_file_that_is_not_a_list_raises():
    with pytest.raises(ValueError):
        parse_quest_rewards('return { ["Beira"] = "+10% to Cold Resistance" }')


def test_render_snapshot_is_valid_json_with_one_reward_per_line():
    text = render_snapshot(rewards(), "0_5_5", "fixture")
    snapshot = json.loads(text)
    assert (snapshot["version"], snapshot["source"]) == ("0_5_5", "fixture")
    assert snapshot["rewards"] == rewards()
    reward_lines = [line for line in text.splitlines() if line.startswith('  {"part"')]
    assert len(reward_lines) == len(rewards())
    assert text.endswith("}\n")


def test_main_writes_utf8_without_bom_and_with_lf_endings(tmp_path, capsys):
    lua = tmp_path / "QuestRewards.lua"
    lua.write_text(QUEST_REWARDS_LUA, encoding="utf-8")
    out = tmp_path / "campaign_0_5_5.json"
    main([str(lua), "0_5_5", "fixture", str(out)])
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")  # no BOM
    assert b"\r\n" not in raw
    assert json.loads(raw.decode("utf-8"))["rewards"][0]["from"] == "Beira"
    assert "5 rewards, 1 with options, 6 weapon-set points" in capsys.readouterr().out


def test_main_requires_an_output_path(tmp_path):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "QuestRewards.lua"), "0_5_5", "fixture"])


def test_latest_version_is_the_committed_snapshot():
    assert latest_version() == "0_5_5"


def test_load_snapshot_is_cached():
    assert load_snapshot("0_5_5") is load_snapshot("0_5_5")


@pytest.mark.parametrize("version", ["9_9_9", "0_5", "", "../0_5_5", "0_5_5x"])
def test_load_snapshot_returns_none_for_unknown_or_malformed_versions(version):
    assert load_snapshot(version) is None


def test_the_committed_snapshot_has_the_campaign_resistances():
    # What the gear-upgrade resistance reminder leans on (checked against dat-export 16088913, game 4.5.5.2).
    stats = {(r["from"], r.get("stat")) for r in load_snapshot("0_5_5")["rewards"]}
    assert {
        ("Beira", "+10% to Cold Resistance"),
        ("Sisters of Garukhan Shrine", "+10% to Lightning Resistance"),
        ("Blackjaw", "+10% to Fire Resistance"),
    } <= stats
