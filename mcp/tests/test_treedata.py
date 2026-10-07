"""Unit tests for the tree.lua parser, the GGG tree-export reader, and named-node extraction (pure,
no network)."""
import pytest

import json

from poe2_mcp.treedata import (
    extract_named_nodes,
    extract_uncounted,
    from_ggg_export,
    load_snapshot,
    main,
    parse_lua_table,
    render_snapshot,
)

# Shaped like real PoB2 src/TreeData/0_5/tree.lua: tab-indented, `[id]=` node keys, `[1]=` lists,
# escaped quotes/newlines in strings, `["string"]` keys, negative/decimal numbers, booleans.
TREE_LUA = r'''return {
	classes={
		[1]={
			["base_dex"]=15,
			name="Ranger"
		}
	},
	constants={
		orbitRadii={
			[1]=0,
			[2]=-82.5
		}
	},
	nodes={
		[4]={
			connections={
				[1]={
					id=11578,
					orbit=0
				}
			},
			name="Shock Chance",
			stats={
				[1]="15% increased chance to Shock"
			}
		},
		[16]={
			ascendancyName="Pathfinder",
			connections={
			},
			name="Life Flask Charges",
			stats={
				[1]="20% increased Life Flask Charges gained"
			}
		},
		[30]={
			ascendancyName="Deadeye",
			isNotable=true,
			name="Gathering Winds",
			stats={
				[1]="Gain Tailwind on Skill use",
				[2]="Lose all Tailwind when Hit"
			}
		},
		[555]={
			flavourText="\"My heart was fractured.\" \n\nNavira confessed.",
			isKeystone=true,
			name="Zealot's Oath",
			stats={
				[1]="Energy Shield does not Recharge"
			}
		},
		[777]={
			isNotable=true,
			name="Heavy Buffer"
		}
	},
	tree="Default"
}'''


def test_parse_lua_scalars_keys_and_escapes():
    t = parse_lua_table(TREE_LUA)
    assert t["tree"] == "Default"
    assert t["classes"] == [{"base_dex": 15, "name": "Ranger"}]  # keys exactly 1..n -> list
    assert t["constants"]["orbitRadii"] == [0, -82.5]
    assert t["nodes"][30]["isNotable"] is True
    assert t["nodes"][555]["flavourText"] == '"My heart was fractured." \n\nNavira confessed.'


def test_parse_lua_sparse_number_keys_stay_a_dict_and_empty_table_is_a_list():
    nodes = parse_lua_table(TREE_LUA)["nodes"]
    assert sorted(nodes) == [4, 16, 30, 555, 777]
    assert nodes[16]["connections"] == []


@pytest.mark.parametrize("bad", ["return { name= }", 'return { name="unterminated }', "return { x=1", "nil"])
def test_parse_lua_rejects_malformed_or_unsupported_input(bad):
    with pytest.raises(ValueError):
        parse_lua_table(bad)


def test_extract_named_nodes_keeps_keystones_notables_and_ascendancy_only():
    named = extract_named_nodes(parse_lua_table(TREE_LUA))
    assert sorted(named) == ["16", "30", "555", "777"]  # plain small node 4 is excluded
    assert named["555"] == {"name": "Zealot's Oath", "kind": "keystone", "ascendancy": None,
                            "stats": ["Energy Shield does not Recharge"]}
    assert named["30"]["kind"] == "notable" and named["30"]["ascendancy"] == "Deadeye"
    assert named["16"]["kind"] == "small" and named["16"]["ascendancy"] == "Pathfinder"


def test_extract_named_nodes_defaults_missing_stats_to_empty():
    assert extract_named_nodes(parse_lua_table(TREE_LUA))["777"]["stats"] == []


# Nodes PoB allocates for free (and so excludes from its point count), shaped like real tree.lua.
STARTS_LUA = r'''return {
	nodes={
		[5]={
			classesStart={
				[1]="Ranger",
				[2]="Huntress"
			},
			name="RANGER"
		},
		[31]={
			ascendancyName="Deadeye",
			isAscendancyStart=true,
			name="Deadeye"
		},
		[32]={
			ascendancyName="Deadeye",
			isMultipleChoiceOption=true,
			name="Choice Option"
		},
		[33]={
			isFreeAllocate=true,
			name="Free Node"
		},
		[40]={
			ascendancyName="Deadeye",
			isNotable=true,
			name="Gathering Winds"
		},
		[41]={
			name="Shock Chance"
		}
	}
}'''


def test_extract_uncounted_lists_free_nodes_sorted():
    assert extract_uncounted(parse_lua_table(STARTS_LUA)) == [5, 31, 32, 33]


def test_extract_uncounted_with_none_is_empty():
    assert extract_uncounted(parse_lua_table(TREE_LUA)) == []


def test_extract_named_nodes_marks_ascendancy_choice_options():
    # A choice option (e.g. Deadeye's Point Blank / Far Shot) is what the player picked under a
    # choice-parent notable -- named as its own kind so the pick isn't lost among small nodes.
    named = extract_named_nodes(parse_lua_table(STARTS_LUA))
    assert named["32"]["kind"] == "choice"
    assert named["32"]["ascendancy"] == "Deadeye"
    assert named["31"]["kind"] == "small"  # the ascendancy start stays a plain small node


def test_load_snapshot_reads_the_committed_snapshot():
    snapshot = load_snapshot("0_5")
    assert snapshot["nodes"]  # non-empty
    sample = next(iter(snapshot["nodes"].values()))
    assert set(sample) == {"name", "kind", "ascendancy", "stats"}
    assert {v["kind"] for v in snapshot["nodes"].values()} == {"keystone", "notable", "small", "choice"}
    assert snapshot["uncounted"] and all(isinstance(i, int) for i in snapshot["uncounted"])


def test_load_snapshot_is_cached():
    assert load_snapshot("0_5") is load_snapshot("0_5")


@pytest.mark.parametrize("version", ["9_99", None, "", "0_5_ruthless", "../data/tree_0_5", "0_5/../0_5"])
def test_load_snapshot_returns_none_for_unknown_or_unsafe_versions(version):
    assert load_snapshot(version) is None


def test_render_snapshot_is_valid_json_with_one_node_per_line():
    text = render_snapshot(parse_lua_table(STARTS_LUA), "0_5", "fixture")
    snapshot = json.loads(text)
    assert snapshot["treeVersion"] == "0_5" and snapshot["source"] == "fixture"
    assert snapshot["uncounted"] == [5, 31, 32, 33]
    assert set(snapshot["nodes"]) == {"31", "32", "40"}
    node_lines = [ln for ln in text.splitlines() if ln.startswith('  "')]
    assert len(node_lines) == 3
    assert text.endswith("\n")


# Regenerating on Windows must not depend on the shell: PowerShell 5.1's `>` writes UTF-16, and
# Python's text mode on Windows turns "\n" into "\r\n". main writes the file itself.
UNICODE_LUA = r'''return {
	nodes={
		[7]={
			isKeystone=true,
			name="Blåmänn's Oath"
		}
	}
}'''


def test_main_writes_utf8_without_bom_and_with_lf_endings(tmp_path):
    lua = tmp_path / "tree.lua"
    lua.write_text(UNICODE_LUA, encoding="utf-8")
    out = tmp_path / "tree_0_5.json"
    main([str(lua), "0_5", "fixture", str(out)])
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")  # no BOM
    assert b"\r\n" not in raw
    assert json.loads(raw.decode("utf-8"))["nodes"]["7"]["name"] == "Blåmänn's Oath"


def test_main_requires_an_output_path(tmp_path):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "tree.lua"), "0_5", "fixture"])


# The backup source for when Path of Building hasn't shipped a new tree yet: GGG's own export
# (grindinggear/poe2-skilltree-export, data.json). Real 0.5.5 nodes (commit bd87e6512c92), trimmed to
# the fields the reader uses. Unlike tree.lua: nodes keyed by id string, a `root` entry with no
# `skill`, ascendancies named only under `classes`, class starts marked by a list of class indexes,
# and stat text carrying the game's display markup, several lines to one string.
GGG_EXPORT = {
    "classes": [
        {"name": "Witch", "ascendancies": [{"id": "Witch3", "name": "Lich"}]},
        {"name": "Ranger", "ascendancies": [{"id": "Ranger2", "name": None}]},
        {"name": "Huntress", "ascendancies": [{"id": "Huntress3", "name": "Ritualist"}]},
        {"name": "Mercenary", "ascendancies": [{"id": "Mercenary3", "name": "Gemling Legionnaire"}]},
        {"name": "Warrior", "ascendancies": [{"id": "Warrior3", "name": "Smith of Kitava"}]},
        {"name": "Monk", "ascendancies": [{"id": "Monk1", "name": "Martial Artist"}]},
        {"name": "Templar", "ascendancies": []},
    ],
    "nodes": {
        "root": {"group": 0, "orbit": 0, "orbitIndex": 0, "out": [], "in": []},
        "21218": {"skill": 21218, "name": "Bow Damage", "stats": ["16% increased Damage with Bows"]},
        "50459": {"skill": 50459, "name": "RANGER", "stats": [], "classStartIndex": [2, 8]},
        "51749": {"skill": 51749, "name": "Blood Magic", "isKeystone": True, "stats": [
            "You have no Mana\nSkill Mana Costs [StatConversion|Converted] to Life Costs"]},
        "23710": {"skill": 23710, "name": "Necromancer", "stats": [], "ascendancyId": "Witch3",
                  "isAscendancyStart": True},
        "60287": {"skill": 60287, "name": "Implanted Gems", "stats": [], "isNotable": True,
                  "ascendancyId": "Mercenary3", "isMultipleChoice": True},
        "32952": {"skill": 32952, "name": "Bolstering Implants", "ascendancyId": "Mercenary3",
                  "isMultipleChoiceOption": True, "multipleChoiceParent": 60287,
                  "stats": ["+2 to Level of all Skills with a [Strength] requirement"]},
        "30996": {"skill": 30996, "name": "Gem Studded", "isNotable": True, "ascendancyId": "Mercenary3",
                  "stats": ["For each colour of Socketed Support Gem that is most numerous, gain:\n"
                            "•Red: [Hit|Hits] against you have no [CriticalDamageBonus|Critical Damage Bonus]\n"
                            "•Blue: Skills have 30% less cost\n"
                            "•Green: 40% less Movement Speed Penalty from using Skills while Moving"]},
        "39552": {"skill": 39552, "name": "Runic Meridians", "isNotable": True, "ascendancyId": "Monk1",
                  "stats": ["Can tattoo [Rune|Runes] onto your body, gaining\n"
                            "additional [Rune]-only sockets:\n• 1 Helmet socket\n• 2 Body Armour sockets\n"
                            "• 1 Gloves socket\n• 1 Boots socket"]},
        "22541": {"skill": 22541, "name": "Heat of the Forge", "isNotable": True, "ascendancyId": "Warrior3",
                  "stats": ["Grants Skill: <underline>{Fire Spell on Hit}"]},
        "9988": {"skill": 9988, "name": "Smith's Masterwork", "isNotable": True, "ascendancyId": "Warrior3",
                 "isFree": True, "stats": [
                     "Can only use a [ItemRarity|Normal] Body Armour",
                     "+200 to [Armour] for each Connected Notable Passive Skill Allocated"]},
        "30100": {"skill": 30100, "name": "", "stats": [], "ascendancyId": "Huntress3"},
        "35715": {"skill": 35715, "name": "", "stats": [], "ascendancyId": "Templar1",
                  "isAscendancyStart": True},
        "24665": {"skill": 24665, "name": "", "stats": [], "ascendancyId": "Ranger2",
                  "isAscendancyStart": True},
    },
}


def test_from_ggg_export_names_the_nodes_pob_names():
    # Not the root entry, the plain small passive, or the class start -- as tree.lua's extraction.
    named = extract_named_nodes(from_ggg_export(GGG_EXPORT))
    assert set(named) == {"51749", "23710", "60287", "32952", "30996", "39552", "22541", "9988", "30100"}


def test_from_ggg_export_takes_ascendancy_names_from_classes():
    named = extract_named_nodes(from_ggg_export(GGG_EXPORT))
    assert named["51749"]["ascendancy"] is None
    assert named["39552"]["ascendancy"] == "Martial Artist"
    assert named["22541"]["ascendancy"] == "Smith of Kitava"


def test_from_ggg_export_names_an_ascendancy_start_after_its_ascendancy():
    # GGG's file carries an internal name on the start node ("Necromancer" on the Lich start).
    named = extract_named_nodes(from_ggg_export(GGG_EXPORT))
    assert named["23710"] == {"name": "Lich", "kind": "small", "ascendancy": "Lich", "stats": []}


def test_from_ggg_export_kinds_match_tree_lua():
    named = extract_named_nodes(from_ggg_export(GGG_EXPORT))
    assert named["51749"]["kind"] == "keystone"
    assert named["60287"]["kind"] == "notable"  # the choice parent costs the point
    assert named["32952"]["kind"] == "choice"


@pytest.mark.parametrize("node_id, stats", [
    ("51749", ["You have no Mana", "Skill Mana Costs Converted to Life Costs"]),
    ("32952", ["+2 to Level of all Skills with a Strength requirement"]),
    ("30996", ["For each colour of Socketed Support Gem that is most numerous, gain:",
               "Red: Hits against you have no Critical Damage Bonus",
               "Blue: Skills have 30% less cost",
               "Green: 40% less Movement Speed Penalty from using Skills while Moving"]),
    ("39552", ["Can tattoo Runes onto your body, gaining", "additional Rune-only sockets:",
               "1 Helmet socket", "2 Body Armour sockets", "1 Gloves socket", "1 Boots socket"]),
    ("22541", ["Grants Skill: Fire Spell on Hit"]),
    ("9988", ["Can only use a Normal Body Armour",
              "+200 to Armour for each Connected Notable Passive Skill Allocated"]),
])
def test_from_ggg_export_strips_display_markup_and_splits_lines(node_id, stats):
    # Expected text is what PoB's tree.lua holds for the same 0.5.5 node.
    assert extract_named_nodes(from_ggg_export(GGG_EXPORT))[node_id]["stats"] == stats


def test_from_ggg_export_keeps_a_blank_name_blank():
    # GGG leaves some nodes unnamed (two Ritualist nodes in 0.5.5). Store that rather than borrowing a
    # name from an older snapshot: GGG can reuse an id for a different node.
    named = extract_named_nodes(from_ggg_export(GGG_EXPORT))
    assert named["30100"] == {"name": "", "kind": "small", "ascendancy": "Ritualist", "stats": []}


def test_from_ggg_export_skips_ascendancies_not_in_the_game():
    # Placeholder starts for ascendancies with no name yet: one not listed under its class at all
    # (Templar1), one listed with a null name (Ranger2). PoB leaves them out too.
    tree = from_ggg_export(GGG_EXPORT)
    assert {"35715", "24665"}.isdisjoint(extract_named_nodes(tree))
    assert {35715, 24665}.isdisjoint(extract_uncounted(tree))


def test_from_ggg_export_uncounted_matches_tree_lua_rules():
    # Class start, ascendancy start, choice option, free node -- int ids in numeric order, as from
    # tree.lua, so a snapshot generated from either source diffs cleanly against the other.
    assert extract_uncounted(from_ggg_export(GGG_EXPORT)) == [9988, 23710, 32952, 50459]


def test_main_reads_a_ggg_export_by_its_json_extension(tmp_path):
    src = tmp_path / "data.json"
    src.write_text(json.dumps(GGG_EXPORT), encoding="utf-8")
    out = tmp_path / "tree_0_5.json"
    main([str(src), "0_5", "fixture", str(out)])
    snapshot = json.loads(out.read_text(encoding="utf-8"))
    assert snapshot["nodes"]["23710"]["name"] == "Lich"
    assert snapshot["uncounted"] == [9988, 23710, 32952, 50459]
    assert list(snapshot["nodes"]) == sorted(snapshot["nodes"], key=int)  # numeric, as from tree.lua
