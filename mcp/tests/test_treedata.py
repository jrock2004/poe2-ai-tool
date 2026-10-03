"""Unit tests for the tree.lua parser and named-node extraction (pure, no network)."""
import pytest

import json

from poe2_mcp.treedata import (
    extract_named_nodes,
    extract_uncounted,
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
