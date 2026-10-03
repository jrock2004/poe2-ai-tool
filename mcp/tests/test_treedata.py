"""Unit tests for the tree.lua parser and named-node extraction (pure, no network)."""
import pytest

from poe2_mcp.treedata import extract_named_nodes, load_named_nodes, parse_lua_table

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


def test_load_named_nodes_reads_the_committed_snapshot():
    named = load_named_nodes("0_5")
    assert named  # non-empty
    sample = next(iter(named.values()))
    assert set(sample) == {"name", "kind", "ascendancy", "stats"}
    assert {v["kind"] for v in named.values()} == {"keystone", "notable", "small"}


def test_load_named_nodes_is_cached():
    assert load_named_nodes("0_5") is load_named_nodes("0_5")


@pytest.mark.parametrize("version", ["9_99", None, "", "0_5_ruthless", "../data/tree_0_5", "0_5/../0_5"])
def test_load_named_nodes_returns_none_for_unknown_or_unsafe_versions(version):
    assert load_named_nodes(version) is None
