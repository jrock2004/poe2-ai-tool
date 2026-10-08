"""Unit tests for the PoB code decoder/parser (pure, no network)."""
import base64
import zlib

import pytest

from poe2_mcp import pob
from poe2_mcp.pob import (
    PobError,
    decode_pob_code,
    parse_loadouts,
    parse_pob_code,
    parse_pob_xml,
    summarize_tree,
)

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


def test_parse_skills_leaves_out_a_group_pob_marks_removed():
    # An unequipped item's skill: PoB keeps the group so its supports come back with the item, but it isn't
    # part of the build -- reviews would otherwise count supports the character doesn't have socketed.
    xml = """<PathOfBuilding2>
  <Build level="40" className="Witch"/>
  <Skills>
    <SkillSet id="1" title="Mid Maps">
      <Skill label="Main"><Gem nameSpec="Raging Spirits" level="20"/></Skill>
      <Skill enabled="true" label="" removed="true" removedSkillId="SummonSkeletalWarriorsPlayer"
             removedSlot="Weapon 1" removedSource="Item:36:New Item, Rattling Sceptre">
        <Gem enabled="true" gemId="Metadata/Items/Gems/SupportGemMeatShield" nameSpec="Meat Shield I" level="1"/>
      </Skill>
    </SkillSet>
  </Skills>
</PathOfBuilding2>"""
    assert _gem_names(parse_pob_xml(xml)) == ["Raging Spirits"]


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


# --- Passive tree (slice B3b: names + point counts from the snapshot) -----------------------------
FAKE_SNAPSHOT = {
    "treeVersion": "0_5",
    "uncounted": [1, 300],
    "nodes": {
        "100": {"name": "Heavy Buffer", "kind": "notable", "ascendancy": None, "stats": ["+20 to Strength"]},
        "300": {"name": "Deadeye", "kind": "small", "ascendancy": "Deadeye", "stats": []},
        "400": {"name": "Gathering Winds", "kind": "notable", "ascendancy": "Deadeye",
                "stats": ["Gain Tailwind on Skill use"]},
        "500": {"name": "Zealot's Oath", "kind": "keystone", "ascendancy": None,
                "stats": ["Energy Shield does not Recharge"]},
    },
}
NAMED_TREE_XML = TREE_XML.replace('nodes="100,200,300,400"', 'nodes="100,200,300,400,500"')


def _parse_with_snapshot(monkeypatch, snapshot):
    """parse_pob_xml(NAMED_TREE_XML) with load_snapshot stubbed; returns (tree, versions asked for)."""
    asked: list = []

    def fake_load_snapshot(version):
        asked.append(version)
        return snapshot

    monkeypatch.setattr(pob, "load_snapshot", fake_load_snapshot)
    return parse_pob_xml(NAMED_TREE_XML)["tree"], asked


def test_tree_names_keystones_and_notables_from_the_spec_version(monkeypatch):
    tree, asked = _parse_with_snapshot(monkeypatch, FAKE_SNAPSHOT)
    assert asked == ["0_5"]
    assert tree["treeDataVersion"] == "0_5"
    assert tree["note"] is None
    assert tree["keystones"] == [{"nodeId": 500, "name": "Zealot's Oath", "ascendancy": None,
                                  "stats": ["Energy Shield does not Recharge"]}]
    assert [(n["nodeId"], n["name"], n["ascendancy"]) for n in tree["notables"]] == [
        (100, "Heavy Buffer", None),
        (400, "Gathering Winds", "Deadeye"),
    ]


def test_tree_counts_points_like_pob(monkeypatch):
    tree, _ = _parse_with_snapshot(monkeypatch, FAKE_SNAPSHOT)
    assert tree["passiveCount"] == 3     # 100, 200 (unnamed small/socket), 500; 300 is uncounted
    assert tree["ascendancyCount"] == 1  # 400; the ascendancy start (300) is free
    assert tree["allocatedCount"] == 5   # raw count is unchanged


def test_tree_without_a_snapshot_keeps_ids_and_says_why(monkeypatch):
    tree, _ = _parse_with_snapshot(monkeypatch, None)
    assert tree["nodes"] == [100, 200, 300, 400, 500]
    for field in ("treeDataVersion", "keystones", "notables", "passiveCount", "ascendancyCount"):
        assert tree[field] is None
    assert "0_5" in tree["note"]


CHOICE_SNAPSHOT = {
    **FAKE_SNAPSHOT,
    "uncounted": [*FAKE_SNAPSHOT["uncounted"], 600],
    "nodes": {
        **FAKE_SNAPSHOT["nodes"],
        "600": {"name": "Point Blank", "kind": "choice", "ascendancy": "Deadeye",
                "stats": ["Projectiles deal more damage at close range"]},
    },
}


def test_tree_lists_the_ascendancy_choice_taken_without_counting_it(monkeypatch):
    monkeypatch.setattr(pob, "load_snapshot", lambda version: CHOICE_SNAPSHOT)
    xml = NAMED_TREE_XML.replace('nodes="100,200,300,400,500"', 'nodes="100,200,300,400,500,600"')
    tree = parse_pob_xml(xml)["tree"]
    assert tree["ascendancyChoices"] == [{"nodeId": 600, "name": "Point Blank", "ascendancy": "Deadeye",
                                          "stats": ["Projectiles deal more damage at close range"]}]
    assert 600 not in [n["nodeId"] for n in tree["notables"]]
    assert tree["ascendancyCount"] == 1  # the choice is free; its parent notable costs the point


def test_tree_without_a_snapshot_has_no_choices(monkeypatch):
    monkeypatch.setattr(pob, "load_snapshot", lambda version: None)
    assert parse_pob_xml(NAMED_TREE_XML)["tree"]["ascendancyChoices"] is None


# PoE2 weapon-set passives: nodes allocated to weapon set 1 / 2 are in `nodes`, but PoB counts real
# spent points as used - min(weaponSet1, weaponSet2) (Build.lua `normalPassives`). A real level 90
# export: 136 counted non-ascendancy nodes, weapon sets 23 / 24 -> 113 points (89 levels + 24 quests).
WEAPON_SET_SNAPSHOT = {"treeVersion": "0_5", "uncounted": [1], "nodes": {}}


def _weapon_set_tree(monkeypatch, ws1: str, ws2: str) -> dict:
    monkeypatch.setattr(pob, "load_snapshot", lambda version: WEAPON_SET_SNAPSHOT)
    xml = f"""<PathOfBuilding2>
  <Tree activeSpec="1">
    <Spec treeVersion="0_5" nodes="1,10,11,12,20,21,30,31,32">
      <WeaponSet1 nodes="{ws1}"/>
      <WeaponSet2 nodes="{ws2}"/>
    </Spec>
  </Tree>
</PathOfBuilding2>"""
    return parse_pob_xml(xml)["tree"]


def test_passive_count_nets_out_the_smaller_weapon_set(monkeypatch):
    tree = _weapon_set_tree(monkeypatch, ws1="20,21", ws2="30,31,32")
    assert tree["passiveCount"] == 8 - 2  # 8 counted nodes (1 is a free start), minus min(2, 3)


def test_passive_count_ignores_uncounted_nodes_in_a_weapon_set(monkeypatch):
    # Node 1 is free, so it doesn't count toward weapon set 1: min(1, 3) = 1, not min(2, 3) = 2.
    tree = _weapon_set_tree(monkeypatch, ws1="1,20", ws2="30,31,32")
    assert tree["passiveCount"] == 8 - 1


# --- Every set, not just the active one (guides carry one set per stage) --------------------------
# PoB keeps tree specs, skill sets, and item sets as three independent lists. The parser indexes all
# three by 1-based document POSITION (PoB itself uses positions for specs but ids for skill/item
# sets); selectors pick which set is parsed in full. Computed stats exist only for the active sets.
MULTI_SET_XML = """<PathOfBuilding2>
  <Build level="70" className="Ranger" ascendClassName="Deadeye">
    <PlayerStat stat="Life" value="2500"/>
  </Build>
  <Tree activeSpec="2">
    <Spec title="Leveling" treeVersion="0_4" nodes="1,2">
      <Sockets><Socket nodeId="2" itemId="5"/></Sockets>
    </Spec>
    <Spec title="Endgame" treeVersion="0_5" nodes="100,200,300"/>
  </Tree>
  <Skills activeSkillSet="1">
    <SkillSet id="3" title="Endgame">
      <Skill label="Main"><Gem nameSpec="Ice Shot" level="20"/></Skill>
    </SkillSet>
    <SkillSet id="1" title="Leveling">
      <Skill label="Old"><Gem nameSpec="Lightning Arrow" level="10"/></Skill>
    </SkillSet>
  </Skills>
  <Items activeItemSet="1">
    <Item id="1">Rarity: NORMAL
Iron Ring</Item>
    <Item id="2">Rarity: NORMAL
Gold Ring</Item>
    <Item id="5">Rarity: RARE
Storm Gaze
Emerald
Implicits: 0
+12% to Cold Resistance</Item>
    <ItemSet id="1" title="Leveling"><Slot name="Ring 1" itemId="1"/></ItemSet>
    <ItemSet id="2" title="Endgame"><Slot name="Ring 1" itemId="2"/></ItemSet>
  </Items>
</PathOfBuilding2>"""


def test_sets_index_lists_every_set_by_position_with_the_active_one_marked():
    sets = parse_pob_xml(MULTI_SET_XML)["sets"]
    assert sets["trees"] == [
        {"position": 1, "title": "Leveling", "active": False},
        {"position": 2, "title": "Endgame", "active": True},
    ]
    # Positions follow document order, not PoB's ids: id 3 comes first, so it's position 1.
    assert sets["skillSets"] == [
        {"position": 1, "title": "Endgame", "active": False},
        {"position": 2, "title": "Leveling", "active": True},  # activeSkillSet="1" is the 2nd set
    ]
    assert sets["itemSets"] == [
        {"position": 1, "title": "Leveling", "active": True},
        {"position": 2, "title": "Endgame", "active": False},
    ]


def test_without_selectors_the_active_sets_are_parsed_as_before():
    r = parse_pob_xml(MULTI_SET_XML)
    assert r["tree"]["treeVersion"] == "0_5"
    assert _gem_names(r) == ["Lightning Arrow"]
    assert [it["name"] for it in r["items"]] == ["Iron Ring"]
    assert r["statsNote"] is None


def test_tree_spec_selects_which_spec_is_parsed():
    tree = parse_pob_xml(MULTI_SET_XML, tree_spec=1)["tree"]
    assert tree["treeVersion"] == "0_4"
    assert tree["nodes"] == [1, 2]


def test_tree_spec_uses_the_selected_specs_version_for_names(monkeypatch):
    asked: list = []
    monkeypatch.setattr(pob, "load_snapshot", lambda version: asked.append(version))
    parse_pob_xml(MULTI_SET_XML, tree_spec=1)
    assert asked == ["0_4"]


def test_skill_set_and_item_set_select_which_sets_are_parsed():
    r = parse_pob_xml(MULTI_SET_XML, skill_set=1, item_set=2)
    assert _gem_names(r) == ["Ice Shot"]
    assert [it["name"] for it in r["items"]] == ["Gold Ring"]


def test_jewels_in_a_non_active_spec_resolve_from_the_shared_items():
    jewels = parse_pob_xml(MULTI_SET_XML, tree_spec=1)["tree"]["jewels"]
    assert [(j["nodeId"], j["name"]) for j in jewels] == [(2, "Storm Gaze")]


@pytest.mark.parametrize("selector", ["tree_spec", "skill_set", "item_set"])
@pytest.mark.parametrize("position", [0, 3])
def test_an_out_of_range_selector_is_an_error_naming_the_range(selector, position):
    # Never fall back to the active set: that would silently compare the wrong stage.
    with pytest.raises(PobError, match=rf"{selector}.*1.*2"):
        parse_pob_xml(MULTI_SET_XML, **{selector: position})


def test_stats_note_flags_when_a_selected_set_is_not_the_active_one():
    note = parse_pob_xml(MULTI_SET_XML, tree_spec=1)["statsNote"]
    assert note is not None
    assert "active" in note
    assert parse_pob_xml(MULTI_SET_XML, tree_spec=1)["life"] == 2500.0  # still the active sets'


def test_selecting_the_active_set_explicitly_needs_no_stats_note():
    assert parse_pob_xml(MULTI_SET_XML, tree_spec=2, skill_set=2, item_set=1)["statsNote"] is None


def test_an_older_export_without_skill_sets_has_one_implicit_skill_set():
    r = parse_pob_xml(SAMPLE_XML, skill_set=1)
    assert r["sets"]["skillSets"] == [{"position": 1, "title": None, "active": True}]
    assert _gem_names(r) == ["Ice Shot", "Bad Support"]
    with pytest.raises(PobError, match=r"skill_set.*1"):
        parse_pob_xml(SAMPLE_XML, skill_set=2)


def test_missing_sections_give_empty_set_lists():
    sets = parse_pob_xml("<PathOfBuilding2/>")["sets"]
    assert sets == {"trees": [], "skillSets": [], "itemSets": []}


def test_parse_code_passes_selectors_through():
    r = parse_pob_code(_encode(MULTI_SET_XML), skill_set=1)
    assert _gem_names(r) == ["Ice Shot"]


# --- Campaign rewards from PoB's config ------------------------------------------------------------
# PoB keys each reward "quest" + part + area + from, and saves only what differs from its default: a
# fixed reward is taken unless saved boolean="false", a pick-one is Nothing unless an option is saved.
# A character import sets them from GGG's quest_stats and leaves <Import lastCharacterHash>.

CAMPAIGN_SNAPSHOT = {
    "version": "0_5_5",
    "source": "test",
    "rewards": [
        {"part": "Act 1", "area": "Clearfell", "from": "Beira", "areaLevel": 2, "stat": "+10% to Cold Resistance"},
        {"part": "Act 1", "area": "Hunting Grounds", "from": "Crowbell", "areaLevel": 10,
         "stat": "+2 Weapon Set Passive Skill Points", "weaponSetPoints": 2},
        {"part": "Act 2", "area": "Valley of the Titans", "from": "Medallion", "areaLevel": 22,
         "options": ["30% increased Charm Charges Gained\n+1 Charm Slot",
                     "30% increased Charm Effect Duration\n+1 Charm Slot"]},
        {"part": "Act 2", "area": "Spires of Deshar", "from": "Sisters of Garukhan Shrine", "areaLevel": 28,
         "stat": "+10% to Lightning Resistance"},
        {"part": "Act 4", "area": "Halls Of The Dead", "from": "Ngamahu's Test", "areaLevel": 40,
         "options": ["+5 to Strength", "+5% to Fire Resistance"]},
    ],
}


def _config_xml(inputs: str, imported: bool = True) -> str:
    """A PoB with one config set holding `inputs`, imported from a character or not."""
    import_el = '<Import lastCharacterHash="e68dc6" lastLeague="SSF Forbidden Rites" lastRealm="PoE2"/>'
    return f"""<PathOfBuilding2>
  <Build level="40" className="Witch"/>
  <Config activeConfigSet="1">
    <ConfigSet id="1">
{inputs}
      <Placeholder name="enemyLevel" number="82"/>
    </ConfigSet>
  </Config>
  {import_el if imported else ""}
</PathOfBuilding2>"""


def _campaign(monkeypatch, xml: str) -> dict:
    monkeypatch.setattr(pob, "_campaign_snapshot", lambda: CAMPAIGN_SNAPSHOT)
    return parse_pob_xml(xml)["campaignRewards"]


def _where(rewards: list[dict]) -> list[str]:
    return [r["from"] for r in rewards]


def test_campaign_rewards_from_a_character_import(monkeypatch):
    # The line break inside the saved option is how PoB writes it; XML reads it back as a space.
    xml = _config_xml("""      <Input name="questAct 2Valley of the TitansMedallion"
             string="30% increased Charm Charges Gained
+1 Charm Slot"/>
      <Input name="questAct 2Spires of DesharSisters of Garukhan Shrine" boolean="false"/>""")
    rewards = _campaign(monkeypatch, xml)
    assert rewards["fromCharacter"] is True
    assert rewards["taken"] == [
        {"part": "Act 1", "area": "Clearfell", "from": "Beira", "stat": "+10% to Cold Resistance"},
        {"part": "Act 2", "area": "Valley of the Titans", "from": "Medallion",
         "stat": "30% increased Charm Charges Gained\n+1 Charm Slot"},  # the snapshot's option, line break kept
    ]
    assert rewards["notTaken"] == [
        {"part": "Act 2", "area": "Spires of Deshar", "from": "Sisters of Garukhan Shrine",
         "stat": "+10% to Lightning Resistance"},
        {"part": "Act 4", "area": "Halls Of The Dead", "from": "Ngamahu's Test",
         "options": ["+5 to Strength", "+5% to Fire Resistance"]},
    ]
    assert rewards["unmatched"] == []


def test_campaign_rewards_leave_out_weapon_set_points(monkeypatch):
    # PoB has no setting for them (useConfig = false); the tree's point count already holds them.
    rewards = _campaign(monkeypatch, _config_xml(""))
    assert "Crowbell" not in _where(rewards["taken"]) + _where(rewards["notTaken"])


def test_campaign_rewards_from_a_pob_never_imported_are_pobs_defaults(monkeypatch):
    # A guide's PoB: nothing saved means every fixed reward on and every pick-one at Nothing. Reported as
    # such, but not from a character, so a skill mustn't read it as what the player took.
    rewards = _campaign(monkeypatch, _config_xml("", imported=False))
    assert rewards["fromCharacter"] is False
    assert _where(rewards["taken"]) == ["Beira", "Sisters of Garukhan Shrine"]
    assert _where(rewards["notTaken"]) == ["Medallion", "Ngamahu's Test"]
    assert rewards["note"]


def test_campaign_rewards_quoted_names_match(monkeypatch):
    # PoB escapes the apostrophe in "Ngamahu's Test" as &apos; in the saved name.
    xml = _config_xml('      <Input name="questAct 4Halls Of The DeadNgamahu&apos;s Test" '
                      'string="+5% to Fire Resistance"/>')
    rewards = _campaign(monkeypatch, xml)
    assert {"part": "Act 4", "area": "Halls Of The Dead", "from": "Ngamahu's Test",
            "stat": "+5% to Fire Resistance"} in rewards["taken"]


def test_campaign_rewards_list_quest_settings_the_snapshot_does_not_know(monkeypatch):
    # A PoB from another patch can name a reward ours doesn't have, or an option it doesn't offer: listed,
    # never guessed into taken or not taken.
    xml = _config_xml("""      <Input name="questAct 5Some New AreaNew Boss" boolean="false"/>
      <Input name="questAct 4Halls Of The DeadNgamahu&apos;s Test" string="+7% to Fire Resistance"/>""")
    rewards = _campaign(monkeypatch, xml)
    assert rewards["unmatched"] == ["questAct 4Halls Of The DeadNgamahu's Test",
                                    "questAct 5Some New AreaNew Boss"]
    assert "Ngamahu's Test" not in _where(rewards["taken"]) + _where(rewards["notTaken"])


def test_campaign_rewards_read_only_the_active_config_set(monkeypatch):
    xml = """<PathOfBuilding2>
  <Config activeConfigSet="2">
    <ConfigSet id="1"><Input name="questAct 1ClearfellBeira" boolean="false"/></ConfigSet>
    <ConfigSet id="2"/>
  </Config>
</PathOfBuilding2>"""
    assert "Beira" in _where(_campaign(monkeypatch, xml)["taken"])


def test_campaign_rewards_without_a_config_are_pobs_defaults(monkeypatch):
    rewards = _campaign(monkeypatch, "<PathOfBuilding2/>")
    assert rewards["fromCharacter"] is False
    assert _where(rewards["taken"]) == ["Beira", "Sisters of Garukhan Shrine"]


def test_campaign_rewards_without_a_snapshot_say_why(monkeypatch):
    monkeypatch.setattr(pob, "_campaign_snapshot", lambda: None)
    rewards = parse_pob_xml(_config_xml(""))["campaignRewards"]
    assert rewards == {"fromCharacter": True, "note": rewards["note"]}
    assert "snapshot" in rewards["note"]


# --- A tree from bare node ids (guides with no PoB, e.g. Mobalytics) ------------------------------
# Same naming and point counting as a PoB tree, from id lists. Mobalytics' authored variants give
# main / weapon set 1 / weapon set 2 / ascendancy as disjoint lists; PoB (and Mobalytics' imported
# "Live Gear") put weapon-set nodes in the main list too. Both shapes must give the same answer.


def test_summarize_tree_merges_every_list_into_nodes():
    tree = summarize_tree([100, 200], "0_5", weapon_set_1=[300], weapon_set_2=[400], ascendancy=[500])
    assert tree["treeVersion"] == "0_5"
    assert tree["nodes"] == [100, 200, 300, 400, 500]
    assert tree["allocatedCount"] == 5
    assert tree["weaponSetNodes"] == {"1": [300], "2": [400]}


def test_summarize_tree_counts_a_repeated_node_once():
    tree = summarize_tree([100, 100, 200], "0_5", ascendancy=[200])
    assert tree["nodes"] == [100, 200]
    assert tree["allocatedCount"] == 2


def test_summarize_tree_names_nodes_from_the_given_version(monkeypatch):
    asked: list = []

    def fake_load_snapshot(version):
        asked.append(version)
        return FAKE_SNAPSHOT

    monkeypatch.setattr(pob, "load_snapshot", fake_load_snapshot)
    tree = summarize_tree([100, 200, 500], "0_5", ascendancy=[300, 400])
    assert asked == ["0_5"]
    assert [n["name"] for n in tree["keystones"]] == ["Zealot's Oath"]
    assert [n["name"] for n in tree["notables"]] == ["Heavy Buffer", "Gathering Winds"]
    assert tree["passiveCount"] == 3     # 100, 200, 500
    assert tree["ascendancyCount"] == 1  # 400; the ascendancy start (300) is free


def test_summarize_tree_nets_out_the_smaller_weapon_set(monkeypatch):
    # Same nodes as test_passive_count_nets_out_the_smaller_weapon_set, in the disjoint shape.
    monkeypatch.setattr(pob, "load_snapshot", lambda version: WEAPON_SET_SNAPSHOT)
    tree = summarize_tree([1, 10, 11, 12], "0_5", weapon_set_1=[20, 21], weapon_set_2=[30, 31, 32])
    assert tree["passiveCount"] == 8 - 2


def test_summarize_tree_gives_the_same_counts_when_main_includes_weapon_set_nodes(monkeypatch):
    monkeypatch.setattr(pob, "load_snapshot", lambda version: WEAPON_SET_SNAPSHOT)
    disjoint = summarize_tree([1, 10, 11, 12], "0_5", weapon_set_1=[20, 21], weapon_set_2=[30, 31, 32])
    overlapping = summarize_tree([1, 10, 11, 12, 20, 21, 30, 31, 32], "0_5",
                                 weapon_set_1=[20, 21], weapon_set_2=[30, 31, 32])
    for field in ("allocatedCount", "passiveCount", "ascendancyCount"):
        assert overlapping[field] == disjoint[field]


def test_summarize_tree_matches_a_pob_tree_with_the_same_nodes(monkeypatch):
    monkeypatch.setattr(pob, "load_snapshot", lambda version: FAKE_SNAPSHOT)
    from_pob = parse_pob_xml(NAMED_TREE_XML)["tree"]
    from_ids = summarize_tree([100, 200, 500], "0_5", weapon_set_1=[300], weapon_set_2=[400])
    for field in ("passiveCount", "ascendancyCount", "keystones", "notables", "ascendancyChoices",
                  "treeDataVersion", "note", "weaponSetNodes", "allocatedCount"):
        assert from_ids[field] == from_pob[field], field
    assert sorted(from_ids["nodes"]) == sorted(from_pob["nodes"])


def test_summarize_tree_without_a_snapshot_keeps_ids_and_says_why(monkeypatch):
    monkeypatch.setattr(pob, "load_snapshot", lambda version: None)
    tree = summarize_tree([100, 200], "0_9")
    assert tree["nodes"] == [100, 200]
    assert tree["passiveCount"] is None
    assert "0_9" in tree["note"]


def test_summarize_tree_with_no_nodes():
    tree = summarize_tree([], "0_5")
    assert tree["nodes"] == []
    assert tree["allocatedCount"] == 0
    assert tree["weaponSetNodes"] == {"1": [], "2": []}


# parse_loadouts: every loadout of a guide's PoB -- a tree spec with the skill set and item set that share
# its title -- for the in-game Build Planner. Shaped like a real PoB2 export (a 0.5 Infernalist guide),
# trimmed: notes sit escaped and indented in the XML, in the planner's own markup -- a gem's or slot's note
# with real line breaks inside its attribute, as PoB writes it (an XML parser turns those into spaces), one
# with &#10; instead; supports are .../SupportGem... by gemId; a group's source says when an item or the
# tree grants its skill.
LOADOUTS_XML = """<PathOfBuilding2>
  <Build level="87" className="Witch" ascendClassName="Infernalist"/>
  <Tree activeSpec="2">
    <Spec title="Act 2" treeVersion="0_5" ascendClassId="1" ascendancyInternalId="Witch1" classId="1"
          nodes="3823,51184,55180">
      <URL>https://www.pathofexile.com/passive-skill-tree/AAAABgEB</URL>
      <Notes>
        <Note nodeId="51184">
          &lt;b&gt;{Priority:} 1
        </Note>
        <Note nodeId="3823">
          &lt;b&gt;{Priority:} 2
        </Note>
      </Notes>
    </Spec>
    <Spec title="Mid Maps" treeVersion="0_5" ascendClassId="1" ascendancyInternalId="Witch1" classId="1"
          nodes="3823,51184,55180,17754,61419">
      <WeaponSet1 nodes="61419"/>
    </Spec>
  </Tree>
  <Skills activeSkillSet="2">
    <SkillSet id="1" title="Act 2">
      <Skill enabled="true" label="" slot="Weapon 1" source="Item:1:Withered Wand">
        <Gem enabled="true" gemId="Metadata/Items/Gems/SkillGemChaosbolt" level="1" nameSpec="Chaos Bolt"
             skillId="WeaponGrantedChaosboltPlayer"/>
      </Skill>
      <Skill enabled="true" label="">
        <Gem enabled="true" gemId="Metadata/Items/Gem/SkillGemRagingSpirits" level="4" nameSpec="Raging Spirits"
             note="
    &lt;b&gt;{Skill Crafting Order}

    1. Raging Spirits" skillId="RagingSpiritsPlayer"/>
        <Gem enabled="true" gemId="Metadata/Items/Gems/SupportGemFireInfusion" level="1" nameSpec="Fire Attunement"
             note="&lt;b&gt;{Support Crafting Order}&#10;    1. Fire Attunement"
             skillId="SupportAddedFireDamagePlayer"/>
        <Gem enabled="false" gemId="Metadata/Items/Gems/SupportGemPrimalArmamentTwo" level="1"
             nameSpec="Elemental Armament II" skillId="SupportElementalArmamentPlayerTwo"/>
      </Skill>
    </SkillSet>
    <SkillSet id="2" title="Mid Maps">
      <Skill enabled="true" label="" source="Tree:17754">
        <Gem enabled="true" gemId="Metadata/Items/Gem/SkillGemAscendancySummonInfernalHound" level="9"
             nameSpec="Summon Infernal Hound" skillId="SummonInfernalHoundPlayer"/>
        <Gem enabled="true" gemId="Metadata/Items/Gems/SupportGemMeatShield" level="1" nameSpec="Meat Shield I"
             skillId="SupportMeatShieldPlayer"/>
      </Skill>
      <Skill enabled="true" label="" slot="Weapon 1" source="Item:2:New Item, Rattling Sceptre">
        <Gem enabled="true" gemId="Metadata/Items/Gem/SupportGemSacrificialLamb" level="1"
             nameSpec="Sacrificial Lamb I" skillId="SupportSacrificialLambPlayer"/>
      </Skill>
      <Skill enabled="true" label="" removed="true" removedSkillId="SummonSkeletalWarriorsPlayer"
             removedSlot="Weapon 1" removedSource="Item:36:New Item, Rattling Sceptre">
        <Gem enabled="true" gemId="Metadata/Items/Gems/SupportGemMeatShield" level="1" nameSpec="Meat Shield I"
             skillId="SupportMeatShieldPlayer"/>
      </Skill>
    </SkillSet>
  </Skills>
  <Items activeItemSet="2">
    <Item id="1">
Rarity: NORMAL
Withered Wand
Quality: 0
    </Item>
    <Item id="3">
Rarity: UNIQUE
Bones of Ullr
Lattice Sandals
Energy Shield: 38
    </Item>
    <Item id="4">
			Rarity: MAGIC
Thawing Charm of the Verdant
Crafted: true
Prefix: None
Suffix: {range:0.468}FlaskFillChargesPerMinute2
Quality: 0
LevelReq: 20
Implicits: 1
Used when you become Frozen
{suffix}Gains 0.20 Charges per Second
			</Item>
    <ItemSet id="1" title="Act 2">
      <Slot itemId="1" itemPbURL="" name="Weapon 1"
            note="&lt;u&gt;{&lt;b&gt;{Withered Wand}}

- A shield might help
"/>
      <Slot itemId="0" itemPbURL="" name="Weapon 2 Swap"/>
      <Slot itemId="0" itemPbURL="" name="Helmet" note="&lt;u&gt;{&lt;b&gt;{Twig Circlet}}"/>
    </ItemSet>
    <ItemSet id="2" title="Mid Maps">
      <Slot itemId="3" itemPbURL="" name="Boots"/>
      <Slot itemId="4" itemPbURL="" name="Charm 1"/>
    </ItemSet>
  </Items>
</PathOfBuilding2>"""


def _loadout(title, xml=LOADOUTS_XML):
    return next(lo for lo in parse_loadouts(xml)["loadouts"] if lo["title"] == title)


def test_loadouts_follow_the_tree_specs_in_order():
    out = parse_loadouts(LOADOUTS_XML)
    assert [lo["title"] for lo in out["loadouts"]] == ["Act 2", "Mid Maps"]
    assert {(lo["ascendancy"], lo["treeVersion"]) for lo in out["loadouts"]} == {("Witch1", "0_5")}
    assert out["unpaired"] == {"skillSets": [], "itemSets": []}


def test_a_loadouts_passives_carry_their_weapon_set_and_note():
    # In the spec's order. The note is the planner's markup, unescaped, its PoB indentation trimmed.
    assert _loadout("Act 2")["passives"] == [
        {"node": 3823, "weaponSet": None, "note": "<b>{Priority:} 2"},
        {"node": 51184, "weaponSet": None, "note": "<b>{Priority:} 1"},
        {"node": 55180, "weaponSet": None, "note": None},
    ]
    assert _loadout("Mid Maps")["passives"][-1] == {"node": 61419, "weaponSet": 1, "note": None}


def test_a_loadouts_skill_groups_split_actives_from_supports():
    groups = _loadout("Act 2")["skillGroups"]
    assert groups[0] == {"source": "Item:1:Withered Wand", "supports": [], "actives": [
        {"gemId": "Metadata/Items/Gems/SkillGemChaosbolt", "name": "Chaos Bolt", "enabled": True,
         "weaponGranted": True, "note": None}]}
    assert groups[1]["source"] is None
    assert groups[1]["actives"] == [
        {"gemId": "Metadata/Items/Gem/SkillGemRagingSpirits", "name": "Raging Spirits", "enabled": True,
         "weaponGranted": False, "note": "<b>{Skill Crafting Order}\n\n1. Raging Spirits"}]
    assert groups[1]["supports"] == [
        {"gemId": "Metadata/Items/Gems/SupportGemFireInfusion", "name": "Fire Attunement", "enabled": True,
         "weaponGranted": False, "note": "<b>{Support Crafting Order}\n1. Fire Attunement"},
        {"gemId": "Metadata/Items/Gems/SupportGemPrimalArmamentTwo", "name": "Elemental Armament II",
         "enabled": False, "weaponGranted": False, "note": None},
    ]


def test_a_group_keeps_its_source_even_with_no_active_gem():
    # Supports socketed into a skill the tree or an item grants: the builder decides what to do with them.
    groups = _loadout("Mid Maps")["skillGroups"]
    assert [(g["source"], [a["name"] for a in g["actives"]], [s["name"] for s in g["supports"]]) for g in groups] == [
        ("Tree:17754", ["Summon Infernal Hound"], ["Meat Shield I"]),
        ("Item:2:New Item, Rattling Sceptre", [], ["Sacrificial Lamb I"]),
    ]


def test_a_group_pob_marks_removed_is_not_part_of_the_loadout():
    # PoB keeps an unequipped item's skill as removed="true", holding its supports in case the item comes
    # back. It isn't in the loadout: nothing of it reaches the Build Planner.
    names = [s["name"] for g in _loadout("Mid Maps")["skillGroups"] for s in g["supports"]]
    assert names == ["Meat Shield I", "Sacrificial Lamb I"]  # one Meat Shield: the hound's, not the removed one


def test_a_loadouts_gear_lists_slots_with_an_item_or_a_note():
    # An empty slot with no note is left out; a note with no item stays. An item carries its mods, as
    # parse_pob_code reads them (the trimmed Bones of Ullr's property line reads as one).
    assert _loadout("Act 2")["gear"] == [
        {"slot": "Weapon 1", "item": {"rarity": "NORMAL", "name": "Withered Wand", "base": None,
                                      "implicitMods": [], "explicitMods": []},
         "note": "<u>{<b>{Withered Wand}}\n\n- A shield might help"},
        {"slot": "Helmet", "item": None, "note": "<u>{<b>{Twig Circlet}}"},
    ]
    assert _loadout("Mid Maps")["gear"][0] == {
        "slot": "Boots", "item": {"rarity": "UNIQUE", "name": "Bones of Ullr", "base": "Lattice Sandals",
                                  "implicitMods": [], "explicitMods": ["Energy Shield: 38"]},
        "note": None}


def test_a_loadouts_charm_carries_what_it_does():
    # A guide often equips charms without a word; their mods say what each is for (the Build Planner names it).
    assert _loadout("Mid Maps")["gear"][1] == {
        "slot": "Charm 1", "item": {"rarity": "MAGIC", "name": "Thawing Charm of the Verdant", "base": None,
                                    "implicitMods": ["Used when you become Frozen"],
                                    "explicitMods": ["Gains 0.20 Charges per Second"]},
        "note": None}


def _retitle(xml, tag, old, new):
    return xml.replace(f'<{tag} id="{"1" if old == "Act 2" else "2"}" title="{old}"', f'<{tag} id="9" title="{new}"', 1)


def test_one_set_with_no_title_match_is_shared_by_every_loadout():
    # A guide with a tree per stage but one skill set and one item set.
    xml = LOADOUTS_XML
    xml = xml[:xml.index('<SkillSet id="2"')] + xml[xml.index("</SkillSet>", xml.index('<SkillSet id="2"')) + 11:]
    xml = _retitle(xml, "SkillSet", "Act 2", "Default")
    out = parse_loadouts(xml)
    assert [len(lo["skillGroups"]) for lo in out["loadouts"]] == [2, 2]
    assert out["unpaired"]["skillSets"] == []


def test_a_set_matching_no_tree_is_unpaired_and_its_loadout_goes_without():
    out = parse_loadouts(_retitle(LOADOUTS_XML, "ItemSet", "Mid Maps", "Endgame"))
    assert out["unpaired"] == {"skillSets": [], "itemSets": ["Endgame"]}
    assert [lo["gear"] == [] for lo in out["loadouts"]] == [False, True]


def test_duplicate_titles_pair_with_nothing():
    # Two item sets titled "Act 2": which one is the loadout's? Neither, and the player is asked.
    out = parse_loadouts(_retitle(LOADOUTS_XML, "ItemSet", "Mid Maps", "Act 2"))
    assert out["unpaired"]["itemSets"] == ["Act 2", "Act 2"]
    assert all(lo["gear"] == [] for lo in out["loadouts"])


def test_an_untitled_tree_is_a_loadout_with_no_title():
    xml = LOADOUTS_XML.replace('title="Act 2" treeVersion', 'treeVersion', 1)
    assert [lo["title"] for lo in parse_loadouts(xml)["loadouts"]] == [None, "Mid Maps"]


def test_parse_loadouts_rejects_xml_that_does_not_parse():
    with pytest.raises(PobError):
        parse_loadouts("<PathOfBuilding2>")
