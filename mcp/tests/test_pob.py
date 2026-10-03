"""Unit tests for the PoB code decoder/parser (pure, no network)."""
import base64
import zlib

import pytest

from poe2_mcp.pob import PobError, decode_pob_code, parse_pob_code, parse_pob_xml

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding2>
  <Build level="92" className="Ranger" ascendClassName="Deadeye">
    <PlayerStat stat="Life" value="3200"/>
    <PlayerStat stat="EnergyShield" value="0"/>
    <PlayerStat stat="FireResist" value="75"/>
    <PlayerStat stat="ColdResist" value="75"/>
    <PlayerStat stat="LightningResist" value="60"/>
    <PlayerStat stat="ChaosResist" value="-20"/>
    <PlayerStat stat="TotalDPS" value="450000.5"/>
  </Build>
  <Skills>
    <Skill label="Main" mainActiveSkill="1">
      <Gem nameSpec="Ice Shot" level="20" quality="20" enabled="true"/>
      <Gem nameSpec="Bad Support" level="1" quality="0" enabled="false"/>
    </Skill>
  </Skills>
  <Items activeItemSet="1">
    <Item id="1">Rarity: RARE
Doom Stride
Stealth Boots
Item Level: 82
LevelReq: 67
+80 to maximum Life
35% to Cold Resistance
25% increased Movement Speed</Item>
    <Item id="2">Rarity: NORMAL
Iron Ring</Item>
    <ItemSet id="1">
      <Slot name="Boots" itemId="1"/>
      <Slot name="Ring 1" itemId="2"/>
      <Slot name="Amulet" itemId="0"/>
    </ItemSet>
  </Items>
</PathOfBuilding2>"""


def _encode(xml: str) -> str:
    return base64.urlsafe_b64encode(zlib.compress(xml.encode("utf-8"))).decode("ascii")


def test_decode_round_trip():
    code = _encode(SAMPLE_XML)
    assert decode_pob_code(code).startswith("<?xml")


def test_decode_accepts_raw_xml_passthrough():
    assert decode_pob_code(SAMPLE_XML).startswith("<?xml")


def test_decode_rejects_a_pobbin_share_link_and_says_so():
    # pobb.in links carry a short id, not the code; resolving one would need a network fetch.
    with pytest.raises(PobError, match="pobb.in"):
        decode_pob_code("https://pobb.in/AbC123xyZ")


def test_decode_rejects_other_links_as_links():
    # PoB codes are URL-safe base64, which never contains '/', so a '/' means a pasted link.
    with pytest.raises(PobError, match="link"):
        decode_pob_code("https://example.com/builds/abc123")


def test_decode_rejects_garbage():
    with pytest.raises(PobError):
        decode_pob_code("this is not a pob code!!!")


def test_parse_character_and_stats():
    r = parse_pob_xml(SAMPLE_XML)
    assert r["valid"] is True
    assert r["character"] == {"level": 92.0, "className": "Ranger", "ascendancy": "Deadeye"}
    assert r["resistances"] == {"fire": 75.0, "cold": 75.0, "lightning": 60.0, "chaos": -20.0}
    assert r["life"] == 3200.0
    assert r["totalDPS"] == 450000.5


def test_parse_skills_including_disabled_flag():
    r = parse_pob_xml(SAMPLE_XML)
    grp = r["skills"][0]
    assert grp["label"] == "Main"
    assert [g["name"] for g in grp["gems"]] == ["Ice Shot", "Bad Support"]
    assert grp["gems"][1]["enabled"] is False


def test_parse_items_skips_empty_slots_and_cleans_mods():
    r = parse_pob_xml(SAMPLE_XML)
    slots = {it["slot"]: it for it in r["items"]}
    assert "Amulet" not in slots  # itemId 0 skipped
    boots = slots["Boots"]
    assert boots["name"] == "Doom Stride"
    assert boots["base"] == "Stealth Boots"
    assert "+80 to maximum Life" in boots["explicitMods"]
    assert "Item Level: 82" not in boots["explicitMods"]  # meta line dropped
    assert boots["implicitMods"] == []  # no Implicits: line -> everything is explicit


def test_parse_code_end_to_end():
    r = parse_pob_code(_encode(SAMPLE_XML))
    assert r["character"]["className"] == "Ranger"


def _skill_sets_xml(active_attr: str) -> str:
    return f"""<PathOfBuilding2>
  <Build level="40" className="Ranger"/>
  <Skills {active_attr}>
    <SkillSet id="1" title="Leveling">
      <Skill label="Old"><Gem nameSpec="Lightning Arrow" level="10"/></Skill>
    </SkillSet>
    <SkillSet id="2" title="Endgame">
      <Skill label="Main"><Gem nameSpec="Ice Shot" level="20"/></Skill>
    </SkillSet>
  </Skills>
</PathOfBuilding2>"""


def _gem_names(parsed: dict) -> list[str]:
    return [g["name"] for s in parsed["skills"] for g in s["gems"]]


def test_parse_skills_uses_only_the_active_skill_set():
    assert _gem_names(parse_pob_xml(_skill_sets_xml('activeSkillSet="2"'))) == ["Ice Shot"]


def test_parse_skills_falls_back_to_the_first_skill_set():
    assert _gem_names(parse_pob_xml(_skill_sets_xml(""))) == ["Lightning Arrow"]


def _one_item_xml(item_text: str) -> str:
    return f"""<PathOfBuilding2>
  <Items activeItemSet="1">
    <Item id="1">{item_text}</Item>
    <ItemSet id="1"><Slot name="Ring 1" itemId="1"/></ItemSet>
  </Items>
</PathOfBuilding2>"""


def test_parse_items_splits_implicits_from_explicits():
    ring = parse_pob_xml(_one_item_xml("""Rarity: RARE
Grim Clasp
Ruby Ring
Item Level: 80
Implicits: 1
+12% to Fire Resistance
+60 to maximum Life
{crafted}+20% to Cold Resistance"""))["items"][0]
    assert ring["implicitMods"] == ["+12% to Fire Resistance"]
    assert ring["explicitMods"] == ["+60 to maximum Life", "+20% to Cold Resistance"]
    assert "mods" not in ring


def test_parse_items_with_zero_implicits():
    ring = parse_pob_xml(_one_item_xml("""Rarity: RARE
Grim Clasp
Ruby Ring
Implicits: 0
+60 to maximum Life"""))["items"][0]
    assert ring["implicitMods"] == []
    assert ring["explicitMods"] == ["+60 to maximum Life"]


# --- Passive tree (slice A: ids only) -------------------------------------------------------------
# PoB2 writes <Tree activeSpec="N"> where N is the 1-based POSITION of the active <Spec> (not an id
# attribute). `nodes` lists every allocated node; <WeaponSetN nodes> marks the subset allocated to a
# weapon set; <Sockets> maps a jewel socket's node id to an <Item id>.
TREE_XML = """<PathOfBuilding2>
  <Build level="70" className="Ranger" ascendClassName="Deadeye"/>
  <Tree activeSpec="2">
    <Spec title="Leveling" treeVersion="0_4" nodes="1,2"/>
    <Spec title="Endgame" treeVersion="0_5" nodes="100,200,300,400">
      <WeaponSet1 nodes="300"/>
      <WeaponSet2 nodes="400"/>
      <Sockets>
        <Socket nodeId="200" itemId="3"/>
        <Socket nodeId="500" itemId="0"/>
      </Sockets>
    </Spec>
  </Tree>
  <Items activeItemSet="1">
    <Item id="3">Rarity: RARE
Storm Gaze
Emerald
Implicits: 0
+12% to Cold Resistance</Item>
    <ItemSet id="1"/>
  </Items>
</PathOfBuilding2>"""


def test_tree_reads_the_active_spec_by_position():
    tree = parse_pob_xml(TREE_XML)["tree"]
    assert tree["treeVersion"] == "0_5"
    assert tree["nodes"] == [100, 200, 300, 400]
    assert tree["allocatedCount"] == 4


def test_tree_defaults_to_the_first_spec():
    tree = parse_pob_xml(TREE_XML.replace(' activeSpec="2"', ""))["tree"]
    assert tree["treeVersion"] == "0_4"
    assert tree["nodes"] == [1, 2]


def test_tree_weapon_set_nodes_are_a_subset_of_nodes():
    tree = parse_pob_xml(TREE_XML)["tree"]
    assert tree["weaponSetNodes"] == {"1": [300], "2": [400]}


def test_tree_jewels_link_sockets_to_items_and_skip_empty_sockets():
    tree = parse_pob_xml(TREE_XML)["tree"]
    assert len(tree["jewels"]) == 1
    jewel = tree["jewels"][0]
    assert jewel["nodeId"] == 200
    assert jewel["name"] == "Storm Gaze"
    assert jewel["base"] == "Emerald"
    assert jewel["explicitMods"] == ["+12% to Cold Resistance"]


def test_tree_with_no_allocated_nodes():
    tree = parse_pob_xml(TREE_XML.replace('nodes="100,200,300,400"', 'nodes=""'))["tree"]
    assert tree["nodes"] == []
    assert tree["allocatedCount"] == 0


def test_tree_is_none_without_a_tree_element():
    assert parse_pob_xml(SAMPLE_XML)["tree"] is None
