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

from .treedata import load_snapshot

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
    by_id: dict[str | None, str] = {}
    if items_el is not None:
        by_id = {it.get("id"): (it.text or "") for it in items_el.findall("Item")}
        itemset = _active_itemset(items_el)
        for slot in (itemset.findall("Slot") if itemset is not None else []):
            item_id = slot.get("itemId", "0")
            if item_id == "0" or item_id not in by_id:
                continue
            items.append({"slot": slot.get("name"), **_item_summary(by_id[item_id])})

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
        "tree": _parse_tree(root, by_id),
    }


def _item_summary(text: str) -> dict[str, Any]:
    rarity, name, base, implicits, explicits = _clean_item_mods(text)
    return {"rarity": rarity or None, "name": name or None, "base": base or None,
            "implicitMods": implicits, "explicitMods": explicits}


def _node_ids(csv: str | None) -> list[int]:
    """'100,200,300' -> [100, 200, 300]; blanks and non-numeric tokens are skipped."""
    return [int(t) for t in (csv or "").split(",") if t.strip().isdigit()]


def _parse_tree(root: ET.Element, items_by_id: dict[str | None, str]) -> dict[str, Any] | None:
    """The active passive-tree <Spec> as node ids (no names -- those need the tree data).

    `activeSpec` is the 1-based POSITION of the active <Spec>, defaulting to the first. `nodes` lists
    every allocated node; <WeaponSetN nodes> marks the subset allocated to weapon set N; <Sockets>
    maps a jewel socket's node id to an <Item id> (itemId 0 = empty socket).
    """
    tree_el = root.find("Tree")
    specs = tree_el.findall("Spec") if tree_el is not None else []
    if not specs:
        return None
    try:
        index = int(tree_el.get("activeSpec", "1")) - 1
    except ValueError:
        index = 0
    spec = specs[index] if 0 <= index < len(specs) else specs[0]

    nodes = _node_ids(spec.get("nodes"))
    weapon_sets = {
        child.tag.removeprefix("WeaponSet"): _node_ids(child.get("nodes"))
        for child in spec
        if child.tag.startswith("WeaponSet") and child.tag.removeprefix("WeaponSet").isdigit()
    }
    jewels = []
    for socket in spec.findall("Sockets/Socket"):
        item_id = socket.get("itemId", "0")
        node_id = socket.get("nodeId", "")
        if item_id == "0" or item_id not in items_by_id or not node_id.isdigit():
            continue
        jewels.append({"nodeId": int(node_id), **_item_summary(items_by_id[item_id])})

    tree_version = spec.get("treeVersion")
    return {
        "treeVersion": tree_version,
        "nodes": nodes,
        "allocatedCount": len(nodes),
        "weaponSetNodes": weapon_sets,
        "jewels": jewels,
        **_name_and_count(nodes, tree_version, weapon_sets),
    }


def _name_and_count(
    nodes: list[int], tree_version: str | None, weapon_sets: dict[str, list[int]]
) -> dict[str, Any]:
    """Names (keystones/notables) and PoB-style point counts from the committed tree snapshot.

    Counts mirror PoB's CountAllocNodes: the snapshot's `uncounted` nodes (class/ascendancy starts,
    choice options, free-allocate) cost nothing; a node is an ascendancy point if the snapshot gives
    it an ascendancy, else a passive point (the snapshot names every ascendancy node, so an unnamed
    node is an ordinary small one). Weapon-set nodes are in `nodes` too, but PoE2 funds them from
    weapon-set points: like PoB's `normalPassives`, passiveCount nets out the smaller of the two
    sets' counted nodes. With no snapshot for this version, everything here is None.
    """
    snapshot = load_snapshot(tree_version)
    if snapshot is None:
        return {
            "treeDataVersion": None, "keystones": None, "notables": None, "ascendancyChoices": None,
            "passiveCount": None, "ascendancyCount": None,
            "note": (
                f'No passive-tree names for tree version "{tree_version}" -- node ids only. '
                "Names and point counts need a matching tree snapshot."
            ),
        }

    named = snapshot["nodes"]
    uncounted = set(snapshot.get("uncounted") or [])
    set_of = {node_id: ws for ws, ids in weapon_sets.items() for node_id in ids}
    weapon_set_used = {"1": 0, "2": 0}
    lists: dict[str, list[dict[str, Any]]] = {"keystone": [], "notable": [], "choice": []}
    passive = ascendancy = 0
    for node_id in nodes:
        info = named.get(str(node_id))
        if info and info["kind"] in lists:
            lists[info["kind"]].append({"nodeId": node_id, "name": info["name"],
                                        "ascendancy": info["ascendancy"], "stats": info["stats"]})
        if node_id in uncounted:
            continue
        if info and info["ascendancy"]:
            ascendancy += 1
        else:
            passive += 1
        if set_of.get(node_id) in weapon_set_used:  # PoB tallies these for any counted node
            weapon_set_used[set_of[node_id]] += 1
    return {
        "treeDataVersion": snapshot.get("treeVersion"),
        "keystones": lists["keystone"],
        "notables": lists["notable"],
        "ascendancyChoices": lists["choice"],  # the option picked under a choice-parent notable
        "passiveCount": passive - min(weapon_set_used.values()),
        "ascendancyCount": ascendancy,
        "note": None,
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
