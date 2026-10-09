"""Decode and parse a Path of Building 2 export code into a structured build summary.

A PoB export code is URL-safe base64 -> zlib -> XML (root ``PathOfBuilding2``). Format and schema were
confirmed against a real PoE2 export: `<Build level className ascendClassName>` with ~95 computed
`<PlayerStat stat value>` children (resistances, life, DPS -- the gold for gear diagnosis), `<Skills>`
of `<Skill>` groups holding `<Gem nameSpec level quality>`, and `<Items>` of `<Item id>` text blocks
mapped by the active `<ItemSet>`'s `<Slot name itemId>`.

Pure and offline -- no network. This is what lets a pasted PoB code feed poe2-gear-upgrade /
poe2-build-review without a screenshot.

`parse_loadouts` reads every stage of a guide's PoB at once -- each tree spec with its skill set and item
set, and the guide's notes on passives, gems and gear -- for writing the in-game Build Planner's files.
"""
from __future__ import annotations

import base64
import re
import zlib
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Any, Callable

from . import campaign
from .treedata import load_snapshot

# PoB annotation lines in item text that aren't readable stat mods -- dropped from the mod list. The second
# row is the base's own values PoB writes above the mods (defences, a sceptre's Spirit, a belt's charm slots).
_ITEM_META_PREFIXES = (
    "Rarity:", "Item Level:", "Quality:", "Sockets:", "LevelReq:", "Implicits:", "Crafted:",
    "Prefix:", "Suffix:", "Unique ID:", "Note:", "Requires", "Corrupted", "Split", "Rune:", "Selected",
    "Energy Shield:", "Armour:", "Evasion:", "Evasion Rating:", "Ward:", "Spirit:", "Charm Slots:",
)
_TAG_RE = re.compile(r"\{[^}]*\}")  # inline PoB tags like {range:0.5}, {crafted}, {tags:...}

# The PlayerStat keys most useful for gear/build diagnosis, surfaced as friendly convenience fields.
_RESIST_KEYS = {"FireResist": "fire", "ColdResist": "cold", "LightningResist": "lightning",
                "ChaosResist": "chaos"}


class PobError(ValueError):
    """Raised when a code can't be decoded as a PoB export."""


class PobSelectionError(PobError):
    """Raised when a set selector is out of range -- the code itself was fine."""


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


def parse_pob_xml(
    xml: str,
    tree_spec: int | None = None,
    skill_set: int | None = None,
    item_set: int | None = None,
) -> dict[str, Any]:
    """Parse decoded PoB XML into a structured summary. Pure; tolerant of missing sections.

    A build can carry several tree specs, skill sets, and item sets (a guide often has one per
    stage). `sets` indexes all three by 1-based document position; the selectors pick which one of
    each is parsed in full, defaulting to the active one. An out-of-range selector raises PobError
    rather than falling back. Computed stats exist only for the active sets -- `statsNote` says so
    when a selector picks a different one.
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise PobError(f"PoB XML did not parse ({e}).") from e

    tree_el = root.find("Tree")
    specs, spec_active = _sets(tree_el, "Spec", _active_spec_index)
    skills_el = root.find("Skills")
    skill_sets, skills_active = _sets(skills_el, "SkillSet", _active_by_id("activeSkillSet"))
    if skills_el is not None and not skill_sets:  # older exports hold <Skill> directly
        skill_sets, skills_active = [skills_el], 0
    items_el = root.find("Items")
    item_sets, items_active = _sets(items_el, "ItemSet", _active_by_id("activeItemSet"))

    spec_i = _select(specs, spec_active, tree_spec, "tree_spec")
    skills_i = _select(skill_sets, skills_active, skill_set, "skill_set")
    items_i = _select(item_sets, items_active, item_set, "item_set")

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

    # Skill groups -> gems, from the selected SkillSet only (a build can carry leveling + endgame sets)
    skills: list[dict[str, Any]] = []
    skill_parent = skill_sets[skills_i] if skills_i is not None else None
    for skill in (skill_parent.findall("Skill") if skill_parent is not None else []):
        if skill.get("removed") == "true":  # an unequipped item's skill, kept for its supports: not the build's
            continue
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

    # Equipped items in the selected ItemSet
    items: list[dict[str, Any]] = []
    by_id: dict[str | None, str] = {}
    if items_el is not None:
        by_id = {it.get("id"): (it.text or "") for it in items_el.findall("Item")}
        itemset = item_sets[items_i] if items_i is not None else None
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
        "tree": _parse_tree(specs[spec_i], by_id) if spec_i is not None else None,
        "sets": {
            "trees": _index(specs, spec_active),
            "skillSets": _index(skill_sets, skills_active),
            "itemSets": _index(item_sets, items_active),
        },
        "statsNote": _stats_note(
            [("tree", spec_i, spec_active), ("skills", skills_i, skills_active),
             ("items", items_i, items_active)]
        ),
        "campaignRewards": _campaign_rewards(root),
    }


def _campaign_snapshot() -> dict[str, Any] | None:
    version = campaign.latest_version()
    return campaign.load_snapshot(version) if version else None


_IMPORTED_NOTE = ("PoB imported this from a character, which sets these from the game's record of the "
                  "rewards it took.")
_DEFAULTS_NOTE = ("Not imported from a character: these are the PoB's own settings (every fixed reward on and "
                  "every pick-one at Nothing unless changed), not what a player took.")


def _campaign_rewards(root: ET.Element) -> dict[str, Any]:
    """The campaign rewards PoB's active config set counts, matched to our campaign snapshot. Pure.

    PoB keys each reward "quest" + part + area + from and saves only what differs from its default: a
    fixed reward is taken unless saved false, a pick-one is Nothing unless an option is saved. Rewards of
    weapon-set points have no setting (the tree's point count holds them) and are left out. A saved key or
    option the snapshot doesn't know goes in `unmatched`, never guessed into taken or not taken.
    `fromCharacter` is whether PoB imported the build from a character (<Import lastCharacterHash>).
    """
    import_el = root.find("Import")
    from_character = import_el is not None and bool(import_el.get("lastCharacterHash"))
    snapshot = _campaign_snapshot()
    if snapshot is None:
        return {"fromCharacter": from_character, "note": "No campaign snapshot is installed to name the rewards."}

    config = root.find("Config")
    config_sets, config_active = _sets(config, "ConfigSet", _active_by_id("activeConfigSet"))
    chosen = config_sets[config_active] if config_active is not None else config
    saved = {} if chosen is None else {
        el.get("name"): el.get("string", el.get("boolean")) for el in chosen.findall("Input")
        if (el.get("name") or "").startswith("quest")
    }

    taken: list[dict[str, Any]] = []
    not_taken: list[dict[str, Any]] = []
    for reward in snapshot["rewards"]:
        if reward.get("weaponSetPoints"):
            continue
        where = {"part": reward["part"], "area": reward["area"], "from": reward["from"]}
        key = f"quest{reward['part']}{reward['area']}{reward['from']}"
        value = saved.get(key)
        if "options" in reward:
            if value is None:
                not_taken.append({**where, "options": reward["options"]})
            else:
                option = next((o for o in reward["options"] if o.split() == value.split()), None)
                if option is not None:
                    saved.pop(key)
                    taken.append({**where, "stat": option})
        else:
            saved.pop(key, None)
            (not_taken if value == "false" else taken).append({**where, "stat": reward["stat"]})

    return {"fromCharacter": from_character, "taken": taken, "notTaken": not_taken, "unmatched": sorted(saved),
            "note": _IMPORTED_NOTE if from_character else _DEFAULTS_NOTE}


def _item_summary(text: str) -> dict[str, Any]:
    rarity, name, base, implicits, explicits = _clean_item_mods(text)
    return {"rarity": rarity or None, "name": name or None, "base": base or None,
            "implicitMods": implicits, "explicitMods": explicits}


def _node_ids(csv: str | None) -> list[int]:
    """'100,200,300' -> [100, 200, 300]; blanks and non-numeric tokens are skipped."""
    return [int(t) for t in (csv or "").split(",") if t.strip().isdigit()]


def _parse_tree(spec: ET.Element, items_by_id: dict[str | None, str]) -> dict[str, Any]:
    """A passive-tree <Spec> as node ids, plus names and point counts from the tree snapshot.

    `nodes` lists every allocated node; <WeaponSetN nodes> marks the subset allocated to weapon set
    N; <Sockets> maps a jewel socket's node id to an <Item id> (itemId 0 = empty socket).
    """
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

    return {**_tree_block(nodes, spec.get("treeVersion"), weapon_sets), "jewels": jewels}


def summarize_tree(
    main: list[int],
    tree_version: str,
    weapon_set_1: list[int] | None = None,
    weapon_set_2: list[int] | None = None,
    ascendancy: list[int] | None = None,
) -> dict[str, Any]:
    """A passive tree from bare node ids -- for guides with no PoB (e.g. Mobalytics' page data).

    Gives the same block as a PoB tree, minus `jewels` (ids carry no items). The lists may be
    disjoint (Mobalytics' authored variants) or overlap (PoB puts weapon-set nodes in the main list
    too); a repeated node counts once, so both shapes give the same counts.
    """
    set_1, set_2 = _unique(weapon_set_1 or []), _unique(weapon_set_2 or [])
    nodes = _unique([*main, *set_1, *set_2, *(ascendancy or [])])
    return _tree_block(nodes, tree_version, {"1": set_1, "2": set_2})


def _unique(ids: list[int]) -> list[int]:
    """`ids` without repeats, first occurrence kept."""
    return list(dict.fromkeys(ids))


def _tree_block(
    nodes: list[int], tree_version: str | None, weapon_sets: dict[str, list[int]]
) -> dict[str, Any]:
    return {
        "treeVersion": tree_version,
        "nodes": nodes,
        "allocatedCount": len(nodes),
        "weaponSetNodes": weapon_sets,
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


ActiveFinder = Callable[[ET.Element, list[ET.Element]], int]


def _sets(
    parent: ET.Element | None, tag: str, find_active: ActiveFinder
) -> tuple[list[ET.Element], int | None]:
    """The <tag> children of `parent` in document order, and the 0-based index of the active one."""
    sets = parent.findall(tag) if parent is not None else []
    return sets, (find_active(parent, sets) if sets else None)


def _active_spec_index(tree_el: ET.Element, specs: list[ET.Element]) -> int:
    """`activeSpec` is the 1-based POSITION of the active <Spec>; the first if missing or invalid."""
    try:
        index = int(tree_el.get("activeSpec", "1")) - 1
    except ValueError:
        return 0
    return index if 0 <= index < len(specs) else 0


def _active_by_id(attr: str) -> ActiveFinder:
    """Skill and item sets name the active one by its `id` attribute; the first if none matches."""
    def find(parent: ET.Element, sets: list[ET.Element]) -> int:
        active_id = parent.get(attr)
        for i, s in enumerate(sets):
            if active_id is not None and s.get("id") == active_id:
                return i
        return 0
    return find


def _select(sets: list[ET.Element], active: int | None, position: int | None, name: str) -> int | None:
    """0-based index of the set to parse: the 1-based `position` if given, else the active one."""
    if position is None:
        return active
    if not 1 <= position <= len(sets):
        available = f"1-{len(sets)}" if sets else "none"
        raise PobSelectionError(f"{name}={position} is out of range; this build has {available}.")
    return position - 1


def _index(sets: list[ET.Element], active: int | None) -> list[dict[str, Any]]:
    return [{"position": i + 1, "title": (s.get("title") or "").strip() or None, "active": i == active}
            for i, s in enumerate(sets)]


def _stats_note(chosen: list[tuple[str, int | None, int | None]]) -> str | None:
    """Say so when any selected set isn't the active one: PoB only stores stats for the active sets."""
    if all(index == active for _, index, active in chosen):
        return None
    active = ", ".join(f"{kind} {a + 1}" for kind, _, a in chosen if a is not None)
    return (f"Stats (resistances, life, DPS) are for the active sets ({active}); PoB only stores "
            "computed stats for those, so they don't reflect the sets selected here.")


def parse_loadouts(xml: str) -> dict[str, Any]:
    """Every loadout of a guide's PoB, for the in-game Build Planner: a tree spec with the skill set and
    item set that share its title. Pure.

    One loadout per <Spec>, in order -- the guide's progression. A spec's skill set (and item set) is the
    one with its title; with no title match, a build's only set is shared by every loadout; otherwise it
    gets none. Sets no loadout took are listed by title in `unpaired` -- so are sets whose title repeats,
    since which one belongs where is the player's call.

    Each loadout: {"title", "ascendancy" (the planner's id, e.g. "Witch1"), "treeVersion", "passives":
    [{"node", "weaponSet", "note"}], "skillGroups": [{"source", "actives", "supports"}], "gear": [{"slot",
    "item": {"rarity", "name", "base", "implicitMods", "explicitMods"} | None, "note"}]}. A gem is {"gemId",
    "name", "enabled", "weaponGranted", "note"}; supports are the .../SupportGem... ones. A group's `source`
    says when an item or the tree grants its skill; a group PoB marks removed (an unequipped item's skill,
    kept so its supports come back with the item) isn't part of the loadout and is left out. Notes stay in
    the planner's markup, unescaped, each line trimmed, their line breaks kept; a note on a node the spec
    doesn't allocate has nowhere to go and is dropped. Gear lists the slots that hold an item or carry a
    note. XML that doesn't parse raises PobError.
    """
    try:
        root = ET.fromstring(_keep_attribute_line_breaks(xml))
    except ET.ParseError as e:
        raise PobError(f"PoB XML did not parse ({e}).") from e

    specs = root.findall("Tree/Spec")
    skill_sets = root.findall("Skills/SkillSet")
    item_sets = root.findall("Items/ItemSet")
    items = {item.get("id"): (item.text or "") for item in root.findall("Items/Item")}
    spec_titles = Counter(_title(spec) for spec in specs)
    taken: dict[str, set[int]] = {"skillSets": set(), "itemSets": set()}

    def pick(sets: list[ET.Element], kind: str, title: str | None) -> ET.Element | None:
        if title is not None and spec_titles[title] == 1:
            matches = [i for i, s in enumerate(sets) if _title(s) == title]
            if len(matches) == 1:
                taken[kind].add(matches[0])
                return sets[matches[0]]
        if len(sets) == 1:
            taken[kind].add(0)
            return sets[0]
        return None

    loadouts = []
    for spec in specs:
        title = _title(spec)
        skill_set = pick(skill_sets, "skillSets", title)
        item_set = pick(item_sets, "itemSets", title)
        loadouts.append({
            "title": title,
            "ascendancy": spec.get("ascendancyInternalId") or None,
            "treeVersion": spec.get("treeVersion"),
            "passives": _loadout_passives(spec),
            "skillGroups": [_skill_group(skill) for skill in
                            (skill_set.findall("Skill") if skill_set is not None else [])
                            if skill.get("removed") != "true"],
            "gear": _loadout_gear(item_set, items),
        })
    unpaired = {kind: [_title(s) for i, s in enumerate(sets) if i not in taken[kind]]
                for kind, sets in (("skillSets", skill_sets), ("itemSets", item_sets))}
    return {"loadouts": loadouts, "unpaired": unpaired}


_START_TAG = re.compile(r"<[A-Za-z][^<>]*>")
_QUOTED = re.compile(r""""[^"]*"|'[^']*'""")
_LINE_BREAK = re.compile(r"\r\n|\r|\n")


def _keep_attribute_line_breaks(xml: str) -> str:
    """xml with each line break inside a start tag's quoted value written as &#10;.

    PoB writes a gem's or slot's note with real line breaks inside its note="..." attribute, and an XML
    parser must turn those into spaces; written as &#10; they come through. Text between tags is left
    alone, so quotes in it can't throw the matching off; a tag with a raw ">" in a value (PoB escapes
    them) doesn't match and parses as before.
    """
    def value(quoted: re.Match[str]) -> str:
        return _LINE_BREAK.sub("&#10;", quoted.group(0))

    return _START_TAG.sub(lambda tag: _QUOTED.sub(value, tag.group(0)), xml)


def _title(el: ET.Element) -> str | None:
    return (el.get("title") or "").strip() or None


def _note(text: str | None) -> str | None:
    """A PoB note as the planner shows it: each line trimmed, blank lines at either end dropped."""
    lines = [line.strip() for line in (text or "").splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) or None


def _loadout_passives(spec: ET.Element) -> list[dict[str, Any]]:
    weapon_sets = {
        node: int(child.tag.removeprefix("WeaponSet"))
        for child in spec
        if child.tag.startswith("WeaponSet") and child.tag.removeprefix("WeaponSet").isdigit()
        for node in _node_ids(child.get("nodes"))
    }
    notes = {note.get("nodeId"): _note(note.text) for note in spec.findall("Notes/Note")}
    return [{"node": node, "weaponSet": weapon_sets.get(node), "note": notes.get(str(node))}
            for node in _node_ids(spec.get("nodes"))]


def _skill_group(skill: ET.Element) -> dict[str, Any]:
    gems = skill.findall("Gem")
    supports = [g for g in gems if (g.get("gemId") or "").rsplit("/", 1)[-1].startswith("SupportGem")]
    return {"source": skill.get("source") or None,
            "actives": [_loadout_gem(g) for g in gems if g not in supports],
            "supports": [_loadout_gem(g) for g in supports]}


def _loadout_gem(gem: ET.Element) -> dict[str, Any]:
    return {"gemId": gem.get("gemId"), "name": gem.get("nameSpec") or gem.get("skillId"),
            "enabled": gem.get("enabled") != "false",
            "weaponGranted": (gem.get("skillId") or "").startswith("WeaponGranted"),
            "note": _note(gem.get("note"))}


def _loadout_gear(item_set: ET.Element | None, items: dict[str | None, str]) -> list[dict[str, Any]]:
    gear = []
    for slot in (item_set.findall("Slot") if item_set is not None else []):
        item_id = slot.get("itemId", "0")
        item = None
        if item_id != "0" and item_id in items:
            summary = _item_summary(items[item_id])
            item = {key: summary[key] for key in ("rarity", "name", "base", "implicitMods", "explicitMods")}
        note = _note(slot.get("note"))
        if item or note:
            gear.append({"slot": slot.get("name"), "item": item, "note": note})
    return gear


def parse_pob_code(
    code: str,
    tree_spec: int | None = None,
    skill_set: int | None = None,
    item_set: int | None = None,
) -> dict[str, Any]:
    """Decode + parse a PoB export code into a build summary (see parse_pob_xml for the selectors)."""
    return parse_pob_xml(decode_pob_code(code), tree_spec, skill_set, item_set)
