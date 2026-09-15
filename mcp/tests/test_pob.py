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


def test_decode_extracts_code_from_pobbin_url():
    code = _encode(SAMPLE_XML)
    assert decode_pob_code(f"https://pobb.in/{code}").startswith("<?xml")


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
    assert "+80 to maximum Life" in boots["mods"]
    assert "Item Level: 82" not in boots["mods"]  # meta line dropped


def test_parse_code_end_to_end():
    r = parse_pob_code(_encode(SAMPLE_XML))
    assert r["character"]["className"] == "Ranger"
