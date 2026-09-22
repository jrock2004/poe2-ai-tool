"""Decode and parse a Path of Building 2 export code into a structured build summary.

A PoB export code is URL-safe base64 -> zlib -> XML (root ``PathOfBuilding2``). Format and schema were
confirmed against a real PoE2 export: `<Build level className ascendClassName>` with ~95 computed
`<PlayerStat stat value>` children (resistances, life, DPS -- the gold for gear diagnosis), `<Skills>`
of `<Skill>` groups holding `<Gem nameSpec level quality>`, and `<Items>` of `<Item id>` text blocks
mapped by the active `<ItemSet>`'s `<Slot name itemId>`.

Pure and offline -- no network. This is what lets a pasted PoB code feed poe2-gear-upgrade /
poe2-build-review without a screenshot.
"""
from __future__ import annotations

import base64
import re
import zlib
import xml.etree.ElementTree as ET
from typing import Any

# PoB annotation lines in item text that aren't readable stat mods -- dropped from the mod list.
_ITEM_META_PREFIXES = (
    "Rarity:", "Item Level:", "Quality:", "Sockets:", "LevelReq:", "Implicits:", "Crafted:",
    "Prefix:", "Suffix:", "Unique ID:", "Note:", "Requires", "Corrupted", "Split", "Rune:", "Selected",
)
_TAG_RE = re.compile(r"\{[^}]*\}")  # inline PoB tags like {range:0.5}, {crafted}, {tags:...}

# The PlayerStat keys most useful for gear/build diagnosis, surfaced as friendly convenience fields.
_RESIST_KEYS = {"FireResist": "fire", "ColdResist": "cold", "LightningResist": "lightning",
                "ChaosResist": "chaos"}


class PobError(ValueError):
    """Raised when a code can't be decoded as a PoB export."""


def decode_pob_code(code: str) -> str:
    """URL-safe base64 -> zlib -> UTF-8 XML. Raises PobError on anything that isn't a PoB code."""
    code = (code or "").strip()
    if code.startswith("<"):  # already raw XML
        return code
    # PoB codes are URL-safe base64, which never contains '/', so a '/' means a pasted link. Share
    # links (pobb.in) carry a short id, not the code -- resolving one would need a network fetch.
    if "pobb.in" in code.lower():
        raise PobError(
            "That's a pobb.in share link, not the build code -- open it and copy the code from the "
            "page, or export from Path of Building (Import/Export -> Generate)."
        )
    if "/" in code:
        raise PobError(
            "That looks like a link, not a Path of Building code -- paste the code itself "
            "(Path of Building: Import/Export -> Generate -> Copy)."
        )
    try:
        raw = base64.urlsafe_b64decode(code + "=" * ((-len(code)) % 4))
        return zlib.decompress(raw).decode("utf-8")
    except Exception as e:  # noqa: BLE001 -- any failure here means "not a valid PoB code"
        raise PobError(f"Not a valid Path of Building code ({type(e).__name__}).") from e


def _num(v: str | None) -> float | None:
    try:
        return round(float(v), 2) if v is not None else None
    except (TypeError, ValueError):
        return None


def _clean_item_mods(text: str) -> tuple[str, str, str, list[str], list[str]]:
    """Parse a PoB <Item> text block -> (rarity, name, base, implicit mods, explicit mods).

    PoB writes `Implicits: N` and then the N implicit lines; everything after them is explicit. With
    no `Implicits:` line, every mod is treated as explicit.
    """
    lines = [ln.rstrip() for ln in (text or "").strip().splitlines()]
    rarity = name = base = ""
    if lines and lines[0].startswith("Rarity:"):
        rarity = lines[0].split(":", 1)[1].strip().upper()
    if len(lines) > 1:
        name = lines[1].strip()
    skip = {0, 1}
    if rarity in ("RARE", "UNIQUE") and len(lines) > 2:
        base = lines[2].strip()
        skip.add(2)
    implicits: list[str] = []
    explicits: list[str] = []
    implicits_left = 0
    for i, ln in enumerate(lines):
        if i in skip:
            continue
        s = _TAG_RE.sub("", ln).strip()
        if s.startswith("Implicits:"):
            try:
                implicits_left = int(s.split(":", 1)[1])
            except ValueError:
                implicits_left = 0
            continue
        if not s or s.startswith(_ITEM_META_PREFIXES):
            continue
        if implicits_left > 0:
            implicits.append(s)
            implicits_left -= 1
        else:
            explicits.append(s)
    return rarity, name, base, implicits, explicits


def parse_pob_xml(xml: str) -> dict[str, Any]:
    """Parse decoded PoB XML into a structured summary. Pure; tolerant of missing sections."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise PobError(f"PoB XML did not parse ({e}).") from e

    build = root.find("Build")
    stats: dict[str, float] = {}
    character: dict[str, Any] = {}
    if build is not None:
        character = {
            "level": _num(build.get("level")),
            "className": build.get("className"),
            "ascendancy": build.get("ascendClassName") or None,
        }
        for ps in build.findall("PlayerStat"):
            val = _num(ps.get("value"))
            if ps.get("stat") and val is not None:
                stats[ps.get("stat")] = val

    resistances = {friendly: stats[key] for key, friendly in _RESIST_KEYS.items() if key in stats}

    # Skill groups -> gems, from the active SkillSet only (a build can carry leveling + endgame sets)
    skills: list[dict[str, Any]] = []
    skills_el = root.find("Skills")
    skill_parent = _active_skillset(skills_el) if skills_el is not None else None
    for skill in (skill_parent.findall("Skill") if skill_parent is not None else []):
        gems = [
            {
                "name": g.get("nameSpec") or g.get("skillId"),
                "level": _num(g.get("level")),
                "quality": _num(g.get("quality")),
                "enabled": g.get("enabled") != "false",
            }
            for g in skill.findall("Gem")
        ]
        if gems:
            skills.append({"label": (skill.get("label") or "").strip() or None, "gems": gems})

    # Equipped items in the active ItemSet
    items: list[dict[str, Any]] = []
    items_el = root.find("Items")
    if items_el is not None:
        by_id = {it.get("id"): (it.text or "") for it in items_el.findall("Item")}
        itemset = _active_itemset(items_el)
        for slot in (itemset.findall("Slot") if itemset is not None else []):
            item_id = slot.get("itemId", "0")
            if item_id == "0" or item_id not in by_id:
                continue
            rarity, name, base, implicits, explicits = _clean_item_mods(by_id[item_id])
            items.append(
                {"slot": slot.get("name"), "rarity": rarity or None, "name": name or None,
                 "base": base or None, "implicitMods": implicits, "explicitMods": explicits}
            )

    return {
        "valid": True,
        "character": character,
        "resistances": resistances,
        "life": stats.get("Life"),
        "energyShield": stats.get("EnergyShield"),
        "mana": stats.get("Mana"),
        "totalDPS": stats.get("TotalDPS"),
        "stats": stats,
        "skills": skills,
        "items": items,
    }


def _active_skillset(skills_el: ET.Element) -> ET.Element:
    """The active <SkillSet>, else the first; older exports with no SkillSets hold <Skill> directly."""
    sets = skills_el.findall("SkillSet")
    if not sets:
        return skills_el
    active_id = skills_el.get("activeSkillSet")
    for s in sets:
        if active_id is not None and s.get("id") == active_id:
            return s
    return sets[0]


def _active_itemset(items_el: ET.Element) -> ET.Element | None:
    sets = items_el.findall("ItemSet")
    if not sets:
        return None
    active_id = items_el.get("activeItemSet")
    for s in sets:
        if active_id is not None and s.get("id") == active_id:
            return s
    return sets[0]


def parse_pob_code(code: str) -> dict[str, Any]:
    """Decode + parse a PoB export code into a build summary."""
    return parse_pob_xml(decode_pob_code(code))
