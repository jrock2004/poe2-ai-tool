"""Game data for the tools, from pinned exports of the game's own files -- generated, never hand-edited.

Mod tiers, bases and their requirements come from repoe-fork/poe2 (`data/mods_by_base.json`,
`mods.json`, `base_items.json`), which is processed from GGG's game files; the data remains GGG's. So does
the in-game text of what PoE2's Currency Exchange trades (currency, omens, essences, runes...). Which items
those are comes from repoe-fork/dat-export's `CurrencyExchange` table -- the game files still carry PoE1
items, and nothing in their records tells the two apart -- and what each essence adds from its essence
tables. Runes, soul cores and idols come from repoe-fork/poe2's `augments.json`, traded or not: PoE1 has
none. This module turns them into one compact snapshot per patch (`data/items_<patch>.json`) that the
tools read at runtime: which mods each base can roll, each tier's name, side, item-level gate and text,
each item's text, what each essence and augment adds, both trials' pools, and the id the in-game Build
Planner names each passive-tree node by. Regenerate per patch, from each export's commit for that game
version:

    python -m poe2_mcp.gamedata items <poe2-commit> <dat-export-commit> 0.5.5 src/poe2_mcp/data/items_0_5_5.json

Build-time only: the command line fetches the exports; nothing the tools call touches the network. Text
keeps the game's wording with its display markup stripped ("[Resistances|Fire Resistance]" -> "Fire
Resistance").
"""
from __future__ import annotations

import csv
import functools
import io
import json
import re
import sys
from collections.abc import Sequence
from importlib import resources
from typing import Any

import httpx

from .knowledge import patch_key

# Equipment, by mods_by_base's class names: what a player wears or wields that rolls prefixes/suffixes.
PLAYER_CLASSES = (
    "Amulets", "Belts", "Body Armours", "Boots", "Bows", "Bucklers", "Charms", "Claws", "Crossbows",
    "Daggers", "Flails", "Foci", "Gloves", "Helmets", "Jewels", "Life Flasks", "Mana Flasks",
    "One Hand Axes", "One Hand Maces", "One Hand Swords", "Quarterstaves", "Quivers", "Rings", "Sceptres",
    "Shields", "Spears", "Staves", "Talismans", "Traps", "Two Hand Axes", "Two Hand Maces",
    "Two Hand Swords", "Wands",
)
_SIDES = ("prefix", "suffix")
RAW_HOST = "https://raw.githubusercontent.com"
EXPORT_REPO = "repoe-fork/poe2"
EXPORT_FILES = ("mods_by_base", "mods", "base_items", "augments")
TABLES_REPO = "repoe-fork/dat-export"
TABLES_DIR = "current/poe2/heuristics/csv"
# The dat-export tables the snapshot reads: what the Currency Exchange trades, what each essence adds, the
# two trials' pools, and the Build Planner's passive ids.
TABLE_NAMES = ("CurrencyExchange", "BaseItemTypes", "Essences", "EssenceMods", "EssenceTargetItemCategories",
               "Mods", "UltimatumModifiers", "UltimatumModifierTypes", "SanctumPersistentEffects",
               "SanctumPersistentEffectCategories", "PassiveSkills", "Words")
USER_AGENT = "poe2-ai-tools (game-data refresh; https://github.com/jrock2004/poe2-ai-tool)"
_COMMIT_RE = re.compile(r"[0-9a-f]{7,40}")
_PATCH_RE = re.compile(r"\d+\.\d+\.\d+[a-z]?")
_SNAPSHOT_PREFIX = "items_"
_TEXT_MATCHES = 20
# The game's display markup: "<underline>{Fire Spell on Hit}", "[EnergyShield|Energy Shield]", "[Rune]".
_DISPLAY_TAG_RE = re.compile(r"<[^>]*>\{([^}]*)\}")
_DISPLAY_LINK_RE = re.compile(r"\[([^\]|]*)(?:\|([^\]]*))?\]")
_NUMBER_RE = re.compile(r"\d+")


def clean_text(line: str) -> str:
    """Game text as a player reads it, with the display markup removed. Pure."""
    line = _DISPLAY_TAG_RE.sub(lambda m: m.group(1), line)
    return _DISPLAY_LINK_RE.sub(lambda m: m.group(2) or m.group(1), line)


def build_items(
    mods_by_base: dict[str, Any],
    mods: dict[str, Any],
    base_items: dict[str, Any],
    classes: tuple[str, ...] = PLAYER_CLASSES,
) -> dict[str, Any]:
    """The item snapshot from the parsed export files. Pure.

    Returns {"groups", "bases", "mods"}:
    - groups: each distinct mod pool, {"prefix"|"suffix": {family: [tier ids in item-level order]}}.
      Tag groups that roll the same mods share one pool.
    - bases: name -> variants [{"class", "group" (index into groups), "requirements": {level, str, dex,
      int}}]. Released bases of `classes` only. Same-named bases that roll the same pool with the same
      requirements are one variant; the rest stay apart, lowest level first.
    - mods: tier id -> {"name", "side", "level" (the item-level gate), "family", "text"}, for the tiers
      some pool uses.

    Only prefixes and suffixes: corruption and unique mods aren't rolled by crafting currency. A tier
    or base that the other file doesn't have raises ValueError -- the export changed shape.
    """
    groups: list[dict[str, Any]] = []
    group_index: dict[str, int] = {}
    used: set[str] = set()
    variants: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {}

    for item_class in sorted(c for c in mods_by_base if c in classes):
        for tags in sorted(mods_by_base[item_class]):
            entry = mods_by_base[item_class][tags]
            pool: dict[str, Any] = {}
            for side in _SIDES:
                families: dict[str, list[str]] = {}
                for family, tiers in sorted((entry["mods"].get(side) or {}).items()):
                    for tier in tiers:
                        if tier not in mods:
                            raise ValueError(f"{item_class} / {tags} lists tier {tier}, which mods.json doesn't have")
                    families[family] = sorted(tiers, key=lambda t: (tiers[t], t))
                    used.update(tiers)
                pool[side] = families
            group = group_index.setdefault(json.dumps(pool, sort_keys=True), len(groups))
            if group == len(groups):
                groups.append(pool)

            for base_id in entry["bases"]:
                base = base_items.get(base_id)
                if base is None:
                    raise ValueError(f"{item_class} / {tags} lists base {base_id}, which base_items.json doesn't have")
                if base.get("release_state") != "released":
                    continue
                req = base.get("requirements") or {}
                requirements = {"level": req.get("level", 0), "str": req.get("strength", 0),
                                "dex": req.get("dexterity", 0), "int": req.get("intelligence", 0)}
                variant = {"class": item_class, "group": group, "requirements": requirements}
                variants.setdefault(base["name"], {})[(group, *requirements.values())] = variant

    bases = {
        name: sorted(found.values(), key=lambda v: (v["requirements"]["level"], v["group"]))
        for name, found in sorted(variants.items())
    }
    tiers = {
        tier: {
            "name": mods[tier].get("name"),
            "side": mods[tier].get("generation_type"),
            "level": mods[tier].get("required_level"),
            "family": mods[tier].get("type"),
            "text": clean_text(mods[tier].get("text") or ""),
        }
        for tier in sorted(used)
    }
    return {"groups": groups, "bases": bases, "mods": tiers}


def build_texts(
    base_items: dict[str, Any], ids: set[str], extras: dict[str, dict[str, Any]] | None = None
) -> dict[str, dict[str, Any]]:
    """The game's text for each of the items `ids`: name -> {"class", "text", "use"}, by name, plus the
    fields `extras` has for it ("adds", "limit", "level" -- `build_essences`, `build_augments`). Pure.

    `ids` is base ids: what PoE2's Currency Exchange trades (`exchange_ids`), plus the augments. text is
    the item's description, use its directions ("Right click this item then left click a rare item to
    apply it."), each as a player reads it (`_game_text`), or "" if it has none. An item with none of
    text, use and extras is left out. An id that base_items doesn't have raises ValueError -- the two
    exports came from different game versions -- and so do two items with one name, since the text is
    looked up by name.
    """
    extras = extras or {}
    texts: dict[str, dict[str, Any]] = {}
    seen: dict[str, str] = {}
    for base_id in sorted(ids):
        base = base_items.get(base_id)
        if base is None:
            raise ValueError(f"{base_id} isn't in base_items.json")
        props = base.get("properties") or {}
        text, use = _game_text(props.get("description")), _game_text(props.get("directions"))
        if not (text or use or base_id in extras):
            continue
        name = base["name"]
        if name in seen:
            raise ValueError(f"two items are named {name!r}: {seen[name]} and {base_id}")
        seen[name] = base_id
        texts[name] = {"class": base["item_class"], "text": text, "use": use, **extras.get(base_id, {})}
    return dict(sorted(texts.items()))


def build_exchange_names(base_items: dict[str, Any], ids: set[str]) -> dict[str, str]:
    """The name of each item PoE2's Currency Exchange trades (`exchange_ids`): base id -> name, in id order.
    Pure. Every traded item, text or not -- the exchange prices by base id, so this is how its prices get
    names when poe2scout is down. An id that base_items doesn't have raises ValueError, as in build_texts.
    """
    names: dict[str, str] = {}
    for base_id in sorted(ids):
        base = base_items.get(base_id)
        if base is None:
            raise ValueError(f"{base_id} isn't in base_items.json")
        names[base_id] = base["name"]
    return names


_UNIQUE_NAME_WORDLIST = "6"  # dat-export writes the Wordlist enum as its number; 6 is UniqueName


def build_unique_names(tables: dict[str, list[dict[str, str]]]) -> list[str]:
    """Every unique item's name, from the Words table's UniqueName rows, in order. Pure.

    A .build file names a unique by "a UniqueName entry from the Words table" (GGG's docs), so this is what
    write_build_plan checks a guide's uniques against -- PoB's own custom items are "New Item". Both
    spellings count: Text2 is what the game shows, and Text an older spelling a few rows keep (Rigvald's /
    Rigwald's Charge). The list keeps PoE1's uniques too; a name isn't proof the unique drops in PoE2. No
    UniqueName rows raises ValueError -- the enum moved, or the export changed shape.
    """
    names = {name.strip() for row in tables["Words"] if row["Wordlist"] == _UNIQUE_NAME_WORDLIST
             for name in (row["Text"], row["Text2"]) if name.strip()}
    if not names:
        raise ValueError(f"Words has no UniqueName rows (Wordlist {_UNIQUE_NAME_WORDLIST})")
    return sorted(names)


def build_essences(
    tables: dict[str, list[dict[str, str]]], mods: dict[str, Any]
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """What each essence adds, per item type: essence base id -> {"adds": [{"on", "side", "text"}]}, rows
    in the game's order -- the field its text entry gets. Pure. Essences here are everything in the game's
    Essences table, Expedition's alloys included -- they work the same way.

    `tables` is dat-export's tables by name, each a list of rows as `csv.DictReader` reads them:
    `EssenceMods` (a row per essence and item type), and the `Essences`, `EssenceTargetItemCategories`,
    `Mods` and `BaseItemTypes` rows it points at by rownum. `mods` is repoe-fork/poe2's mods.json.

    on: the item types, as the game names them ("Amulet, Boots or Gloves"). text: what the game shows --
    the row's own text, else its display modifier's, else its modifier's -- as a player reads it. side:
    the modifier's ("prefix"/"suffix"); when the essence picks a modifier at random, that of the possible
    picks ("prefix or suffix" if they differ). A row pointing at one that isn't there, a modifier
    mods.json doesn't have, or a row with no text or no side raises ValueError -- the export changed shape.
    """
    index = {table: {row["rownum"]: row for row in tables[table]}
             for table in ("BaseItemTypes", "Essences", "EssenceTargetItemCategories", "Mods")}

    def ref(table: str, rownum: str, by: str) -> dict[str, str]:
        return _table_ref(index[table], table, rownum, by)

    def mod(rownum: str, by: str) -> dict[str, Any]:
        mod_id = ref("Mods", rownum, by)["Id"]
        if mod_id not in mods:
            raise ValueError(f"{by} names mod {mod_id}, which mods.json doesn't have")
        return mods[mod_id]

    adds: dict[str, list[dict[str, str]]] = {}
    for row in tables["EssenceMods"]:
        by = f"EssenceMods row {row['rownum']}"
        essence = ref("Essences", row["Essence"], by)
        base_id = ref("BaseItemTypes", essence["BaseItemType"], f"Essences row {essence['rownum']}")["Id"]
        on = clean_text(ref("EssenceTargetItemCategories", row["TargetItemCategory"], by)["Text"])
        if row["Text"]:
            shown = row["Text"]
        elif row["DisplayMod"]:
            shown = mod(row["DisplayMod"], by).get("text")
        else:
            shown = row["Mod"] and mod(row["Mod"], by).get("text")
        text = _game_text(shown)
        if not text:
            raise ValueError(f"{by} has nothing to show: no text of its own, and its modifier has none")
        if row["Mod"]:
            side = mod(row["Mod"], by)["generation_type"]
        else:
            picks = {mod(str(pick), by)["generation_type"] for pick in json.loads(row["OutcomeMods"] or "[]")}
            if not picks:
                raise ValueError(f"{by} has no modifier and no outcomes to take a side from")
            side = " or ".join(sorted(picks))
        adds.setdefault(base_id, []).append({"on": on, "side": side, "text": text})
    return {base_id: {"adds": rows} for base_id, rows in adds.items()}


def build_augments(augments: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """What each augment -- rune, soul core, idol -- does, from repoe-fork/poe2's augments.json: base id ->
    {"adds": [{"on", "text", "bonded"?}], "limit"?, "level"?}, the fields its text entry gets. Pure.

    on: the kinds of item it fits, as augments.json names them ("Martial Weapon", "All"). text: its effect
    there, as a player reads it -- "" if it only has a bonded one. bonded: its Bonded modifier there, which
    the game gives only a Shaman who allocated Wisdom of the Maji. No side: an augment fills a socket, not
    an affix. limit: how many can be socketed ("1 Ancient Augment"). level: its level requirement. A kind
    of item with neither effect raises ValueError -- the export changed shape.
    """
    out: dict[str, dict[str, Any]] = {}
    for base_id, augment in augments.items():
        adds = []
        for on, effects in augment["categories"].items():
            text = _game_text("\n".join(effects.get("stat_text") or []))
            bonded = _game_text("\n".join(effects.get("bonded_stat_text") or []))
            if not (text or bonded):
                raise ValueError(f"augments.json gives {base_id} no effect on {on}")
            adds.append({"on": clean_text(on), "text": text, **({"bonded": bonded} if bonded else {})})
        entry: dict[str, Any] = {"adds": adds}
        if augment.get("limit"):
            entry["limit"] = clean_text(augment["limit"])
        if augment.get("required_level") is not None:
            entry["level"] = augment["required_level"]
        out[base_id] = entry
    return out


def build_chaos(tables: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    """The Trial of Chaos modifiers, from dat-export's `UltimatumModifiers` and `UltimatumModifierTypes`:
    [{"name", "kind", "versions": [{"name", "tier", "text"}]}], in the game's order. Pure.

    Each row points at the version below it (PreviousTier), so a modifier's versions run from its first
    to its last, tiers 1-5 with gaps. kind is from the game's type names: its "...Daemon" types are room
    hazards, its "Wager..." types wagers, the rest modifiers. A row pointing at one that isn't there
    raises ValueError -- the export changed shape.
    """
    types = {row["rownum"]: row["Id"] for row in tables["UltimatumModifierTypes"]}
    rows = tables["UltimatumModifiers"]
    by_rownum = {row["rownum"]: row for row in rows}
    after: dict[str, dict[str, str]] = {}
    for row in rows:
        for below in json.loads(row["PreviousTier"] or "[]"):
            _table_ref(by_rownum, "UltimatumModifiers", str(below), f"UltimatumModifiers row {row['rownum']}")
            after[str(below)] = row

    chaos = []
    for row in rows:
        if json.loads(row["PreviousTier"] or "[]"):
            continue
        by = f"UltimatumModifiers row {row['rownum']}"
        kinds = [_table_ref(types, "UltimatumModifierTypes", str(t), by) for t in json.loads(row["Types"] or "[]")]
        kind = ("wager" if any(k.startswith("Wager") for k in kinds)
                else "hazard" if any(k.endswith("Daemon") for k in kinds) else "modifier")
        versions = []
        step: dict[str, str] | None = row
        while step is not None:
            versions.append({"name": clean_text(step["Name"]), "tier": int(step["Tier"]),
                             "text": _table_text(step["Description"])})
            step = after.get(step["rownum"])
        chaos.append({"name": clean_text(row["Name"]), "kind": kind, "versions": versions})
    return chaos


def build_sekhemas(tables: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    """The Trial of the Sekhemas afflictions, boons and pledges, from dat-export's
    `SanctumPersistentEffects` and `SanctumPersistentEffectCategories`: [{"name", "category", "text",
    "cost"?, "values"?}], in the game's order. Pure.

    category is the game's ("Minor Afflictions", "Pledges"). A pledge is a boon with a cost. The game fills
    a "{0}" in the text from the row's values, which come along as `values` -- how it formats them isn't
    in the export. Left out: the rows the game marks UNUSED, nameless rows, and the later steps of a chain
    (NextEffect: Ghastly Scythe counting down its rooms is listed once, by the step it starts at). A row
    pointing at one that isn't there raises ValueError -- the export changed shape.
    """
    categories = {row["rownum"]: row["Name"] for row in tables["SanctumPersistentEffectCategories"]}
    rows = tables["SanctumPersistentEffects"]
    by_rownum = {row["rownum"]: row for row in rows}
    later_steps = set()
    for row in rows:
        if row["NextEffect"]:
            _table_ref(by_rownum, "SanctumPersistentEffects", row["NextEffect"],
                       f"SanctumPersistentEffects row {row['rownum']}")
            later_steps.add(row["NextEffect"])

    effects = []
    for row in rows:
        name = clean_text(row["Name"])
        boon, curse = _table_text(row["BoonDesc"]), _table_text(row["CurseDesc"])
        if not name or row["rownum"] in later_steps or "UNUSED" in (name, boon, curse):
            continue
        category = _table_ref(categories, "SanctumPersistentEffectCategories", row["EffectCategory"],
                              f"SanctumPersistentEffects row {row['rownum']}")
        effect: dict[str, Any] = {"name": name, "category": category, "text": boon or curse}
        if boon and curse:
            effect["cost"] = curse
        if "{" in effect["text"] + effect.get("cost", ""):
            effect["values"] = json.loads(row["StatValues"] or "[]")
        effects.append(effect)
    return effects


def build_passives(tables: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    """Each passive-tree node's id in dat-export's `PassiveSkills` -- what the in-game Build Planner's .build
    files name a passive by -- keyed by its PassiveSkillGraphId, the node id Path of Building and the tree
    snapshot use: {"52": "passive_keystone_zealots_oath", ...}, in numeric node order. Pure.

    Every row with a node id: small and ascendancy nodes too, since a guide allocates those as well. A row
    with none has no place on the tree and is left out. Two rows for one node raise ValueError -- the export
    changed shape.
    """
    passives: dict[str, str] = {}
    for row in tables["PassiveSkills"]:
        node = row["PassiveSkillGraphId"]
        if not node:
            continue
        if node in passives:
            raise ValueError(f"PassiveSkills rows {passives[node]!r} and {row['Id']!r} are both node {node}")
        passives[node] = row["Id"]
    return {node: passives[node] for node in sorted(passives, key=int)}


def build_gems(tables: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    """Each skill and support gem's name, keyed by its `BaseItemTypes` id -- the id Path of Building's gemId
    and the in-game Build Planner's .build files name it by, under Metadata/Items/Gems/ or, for some,
    Metadata/Items/Gem/ -- in id order. Pure.

    The name is the one the game shows, which the id doesn't always spell (SupportGemFireInfusion is Fire
    Attunement). A name the game fills in ("Spectre: {0}", the monster) is the gem's own ("Spectre"). Rows
    with no name, and unused gems the game marks [DNT] ("do not translate"), are left out.
    """
    gems = {}
    for row in tables["BaseItemTypes"]:
        name = row["Name"].replace(": {0}", "").strip()
        if row["Id"].startswith(("Metadata/Items/Gem/", "Metadata/Items/Gems/")) and name \
                and not name.startswith("[DNT"):
            gems[row["Id"]] = name
    return {gem_id: gems[gem_id] for gem_id in sorted(gems)}


def _table_ref(rows: dict[str, Any], table: str, rownum: str, by: str) -> Any:
    """`rows[rownum]` -- a dat-export row reference -- or ValueError naming both rows. Pure."""
    if rownum not in rows:
        raise ValueError(f"{by} names {table} row {rownum}, which the table doesn't have")
    return rows[rownum]


def _table_text(raw: str | None) -> str:
    """A dat-export text as a player reads it: the export writes a line break as the two characters \\n
    (or \\r\\n); otherwise like `_game_text`. Pure."""
    return _game_text((raw or "").replace("\\r\\n", "\n").replace("\\n", "\n"))


def _game_text(raw: str | None) -> str:
    """Item text as a player reads it: markup removed, each line trimmed, and the game's line breaks kept
    as LF (the export mixes in CRLF). Pure."""
    return "\n".join(clean_text(line).strip() for line in (raw or "").splitlines()).strip()


def render_items(items: dict[str, Any], patch: str, source: str) -> str:
    """The snapshot JSON text: patch, source, then one pool, base, tier, item text, Trial of Chaos modifier,
    Sekhemas effect, passive id, gem name, exchange name and unique name per line, so a per-patch regeneration
    reads as a small diff. Pure; ends with a newline."""

    def rows(pairs: Any) -> str:
        return ",\n".join(f"  {key}{json.dumps(value, ensure_ascii=False)}" for key, value in pairs)

    return (
        "{\n"
        f'"patch": {json.dumps(patch)},\n'
        f'"source": {json.dumps(source)},\n'
        '"groups": [\n' + rows(("", g) for g in items["groups"]) + "\n],\n"
        '"bases": {\n' + rows((f"{json.dumps(n)}: ", v) for n, v in items["bases"].items()) + "\n},\n"
        '"mods": {\n' + rows((f"{json.dumps(t)}: ", m) for t, m in items["mods"].items()) + "\n},\n"
        '"texts": {\n' + rows((f"{json.dumps(n)}: ", t) for n, t in items["texts"].items()) + "\n},\n"
        '"chaos": [\n' + rows(("", c) for c in items["chaos"]) + "\n],\n"
        '"sekhemas": [\n' + rows(("", e) for e in items["sekhemas"]) + "\n],\n"
        '"passives": {\n' + rows((f"{json.dumps(n)}: ", p) for n, p in items["passives"].items()) + "\n},\n"
        '"gems": {\n' + rows((f"{json.dumps(g)}: ", n) for g, n in items["gems"].items()) + "\n},\n"
        '"exchange": {\n' + rows((f"{json.dumps(b)}: ", n) for b, n in items["exchange"].items()) + "\n},\n"
        '"uniques": [\n' + rows(("", n) for n in items["uniques"]) + "\n]\n"
        "}\n"
    )


def mod_tiers(
    items: dict[str, Any], base: str, search: str | None = None, item_level: int | None = None
) -> dict[str, Any]:
    """Which mods `base` can roll, from a loaded snapshot: {"base", "patch", "variants"}. Pure.

    `base` matches a base name in any case; an unknown one returns base None and up to 8 `suggestions`
    (see `_suggest`). Each variant of the name comes back with its class, requirements and
    families -- prefixes first, then suffixes -- each with every tier: name, itemLevel, text. `search`
    keeps the families whose name or any tier's text contains it (any case); a found base with no
    matching family is the answer "that can't roll here". With `item_level`, each tier says whether it
    `canRoll` on an item of that level.
    """
    if item_level is not None and item_level < 1:
        raise ValueError(f"item_level must be at least 1 (the item's item level), got {item_level}")
    wanted = base.strip().lower()
    name = next((n for n in items["bases"] if n.lower() == wanted), None)
    if name is None:
        return {"base": None, "patch": items["patch"], "variants": [], "suggestions": _suggest(items["bases"], wanted)}

    needle = (search or "").strip().lower()
    variants = []
    for variant in items["bases"][name]:
        pool = items["groups"][variant["group"]]
        families = []
        for side in _SIDES:
            for family, tier_ids in pool[side].items():
                tiers = [items["mods"][t] for t in tier_ids]
                if needle and needle not in family.lower() and not any(needle in t["text"].lower() for t in tiers):
                    continue
                rows = []
                for tier in tiers:
                    row = {"name": tier["name"], "itemLevel": tier["level"], "text": tier["text"]}
                    if item_level is not None:
                        row["canRoll"] = tier["level"] <= item_level
                    rows.append(row)
                families.append({"family": family, "side": side, "tiers": rows})
        variants.append({"class": variant["class"], "requirements": variant["requirements"], "families": families})
    return {"base": name, "patch": items["patch"], "variants": variants}


def top_rolls(items: dict[str, Any], family: str) -> tuple[tuple[int, int], ...]:
    """The highest value a mod family can roll as the item level goes up, from a loaded snapshot: ((item
    level, highest value), ...), ascending -- only the levels where it goes up. Pure.

    Across every base the family rolls on (the snapshot's tiers are only those some base rolls). A tier's
    highest value is the last number in its text ("+(10-19) to maximum Life" -> 19), which fits
    single-stat families; a tier with no number is left out. A family no base rolls gives ().
    """
    best: dict[int, int] = {}
    for tier in items["mods"].values():
        numbers = _NUMBER_RE.findall(tier["text"]) if tier["family"] == family else []
        if numbers:
            best[tier["level"]] = max(best.get(tier["level"], 0), int(numbers[-1]))
    steps: list[tuple[int, int]] = []
    for level in sorted(best):
        if not steps or best[level] > steps[-1][1]:
            steps.append((level, best[level]))
    return tuple(steps)


def item_text(items: dict[str, Any], search: str) -> dict[str, Any]:
    """The game's text for the items matching `search`, from a loaded snapshot: {"patch", "total",
    "matches"}. Pure.

    An item matches when its name, text or use (its directions) contains `search`, or for an essence or
    augment what it adds, bonded effects included, and on which kinds of item -- in any case, with line
    breaks read as spaces. So "Chaos Orb" finds the orb and the omens that change it, and "maximum life"
    the essences that add it. Each match is {"name", "class", "text", "use"}, plus "adds" for an essence
    or augment and an augment's "limit" and "level"; an exact name comes first, then by name. Up to 20
    matches; `total` counts them all. No match adds up to 8 `suggestions` (see `_suggest`). A blank
    search raises ValueError: it would match every item.
    """
    needle = _flat(search)
    if not needle:
        raise ValueError("search is empty: give an item's name, or words from what it does")
    found = [{"name": name, **entry} for name, entry in items["texts"].items()
             if any(needle in _flat(field) for field in _searched(name, entry))]
    found.sort(key=lambda row: (row["name"].lower() != needle, row["name"]))
    out = {"patch": items["patch"], "total": len(found), "matches": found[:_TEXT_MATCHES]}
    if not found:
        out["suggestions"] = _suggest(items["texts"], needle)
    return out


def trial_pool(items: dict[str, Any], trial: str, search: str | None = None) -> dict[str, Any]:
    """A trial's pool from a loaded snapshot -- "chaos" (the Trial of Chaos modifiers, `build_chaos`) or
    "sekhemas" (its afflictions, boons and pledges, `build_sekhemas`): {"patch", "trial", "total",
    "matches"}, in the game's order. Pure.

    Without `search`, the whole pool. With it, the entries whose name, text (any version's, a pledge's
    cost) or kind of entry (a modifier's kind, an effect's category) contains it -- in any case, with line
    breaks read as spaces. No match adds up to 8 `suggestions` (see `_suggest`). An unknown trial raises
    ValueError.
    """
    key = (trial or "").strip().lower()
    if key not in _TRIALS:
        raise ValueError(f"trial must be 'chaos' or 'sekhemas', not {trial!r}")
    pool = items[key]
    needle = _flat(search or "")
    matches = [entry for entry in pool if not needle or any(needle in _flat(f) for f in _TRIALS[key](entry))]
    out = {"patch": items["patch"], "trial": key, "total": len(matches), "matches": matches}
    if not matches:
        out["suggestions"] = _suggest([entry["name"] for entry in pool], needle)
    return out


# What `trial_pool` searches in each trial's entries.
_TRIALS = {
    "chaos": lambda modifier: [modifier["name"], modifier["kind"],
                               *(version[key] for version in modifier["versions"] for key in ("name", "text"))],
    "sekhemas": lambda effect: [effect["name"], effect["category"], effect["text"], effect.get("cost", "")],
}


def _searched(name: str, entry: dict[str, Any]) -> list[str]:
    """What `item_text` searches in an item: its name, text and use, and each kind of item, effect and
    bonded effect it adds. Pure."""
    added = [add[key] for add in entry.get("adds", ()) for key in ("on", "text", "bonded") if key in add]
    return [name, entry["text"], entry["use"], *added]


def _flat(text: str) -> str:
    """Lowercase, with each run of whitespace -- line breaks included -- as one space. Pure."""
    return " ".join(text.lower().split())


def _suggest(names: Any, wanted: str) -> list[str]:
    """Up to 8 names (bases, or traded items) for a lowercase name that matched none: those that contain
    it, or, when none does (an old or mistyped full name), those sharing the most whole words with it --
    fewer words first, as the closer match, then by name. Pure."""
    hits = sorted(n for n in names if wanted in n.lower())
    if hits:
        return hits[:8]
    words = set(wanted.split())
    ranked = sorted((-len(words & set(n.lower().split())), len(n.split()), n) for n in names)
    return [n for shared, _, n in ranked if shared < 0][:8]


def newest_snapshot(names: Any) -> str | None:
    """The `items_<patch>.json` name with the highest patch, or None. Pure. Ordered by patch, not text
    (0.5.10 after 0.5.5; a hotfix letter after its base patch); other names are ignored."""
    best, best_key = None, None
    for name in names:
        if not (name.startswith(_SNAPSHOT_PREFIX) and name.endswith(".json")):
            continue
        try:
            key = patch_key(name[len(_SNAPSHOT_PREFIX):-len(".json")].replace("_", "."))
        except ValueError:
            continue
        if best_key is None or key > best_key:
            best, best_key = name, key
    return best


@functools.lru_cache(maxsize=None)
def load_items() -> dict[str, Any] | None:
    """The newest committed item snapshot, or None if there isn't one. Loaded once."""
    data = resources.files("poe2_mcp").joinpath("data")
    name = newest_snapshot(entry.name for entry in data.iterdir())
    return json.loads(data.joinpath(name).read_text(encoding="utf-8")) if name else None


def _fetch_files(repo: str, commit: str, paths: list[str],
                 transport: httpx.BaseTransport | None) -> list[httpx.Response]:
    """Each of `paths` in GitHub repo `repo` at `commit`, in order, from GitHub's raw file host.

    `commit` must be a commit hash: a branch or tag can move, and the snapshot has to name exactly the
    export it came from. An HTTP error raises RuntimeError.
    """
    if not _COMMIT_RE.fullmatch(commit or ""):
        raise ValueError(f"Expected a commit hash (7-40 hex characters), not {commit!r}: a branch or tag can move")
    responses = []
    with httpx.Client(base_url=f"{RAW_HOST}/{repo}/{commit}/", headers={"User-Agent": USER_AGENT},
                      timeout=60.0, transport=transport) as client:
        for path in paths:
            resp = client.get(path)
            if resp.status_code != 200:
                raise RuntimeError(f"{repo}@{commit} {path} -> HTTP {resp.status_code}")
            responses.append(resp)
    return responses


def fetch_export(commit: str, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    """Download repoe-fork/poe2's export at `commit`: {"mods_by_base", "mods", "base_items", "augments"
    (parsed), "game_version"}. Build-time only -- the command line runs it, the tools never do. A commit
    hash only; an HTTP error raises RuntimeError (see `_fetch_files`).
    """
    *files, version = _fetch_files(
        EXPORT_REPO, commit, [*(f"data/{name}.json" for name in EXPORT_FILES), "version.txt"], transport)
    export: dict[str, Any] = {name: resp.json() for name, resp in zip(EXPORT_FILES, files)}
    export["game_version"] = version.text.strip()
    return export


def fetch_tables(
    commit: str, names: Sequence[str], transport: httpx.BaseTransport | None = None
) -> dict[str, list[dict[str, str]]]:
    """The tables `names` from repoe-fork/dat-export at `commit`: name -> its rows, each as `csv.DictReader`
    reads it (column -> text, "" when empty). Build-time only, like `fetch_export`. A commit hash only; an
    HTTP error raises RuntimeError (see `_fetch_files`).
    """
    files = _fetch_files(TABLES_REPO, commit, [f"{TABLES_DIR}/{name}.csv" for name in names], transport)
    return {name: list(csv.DictReader(io.StringIO(resp.text))) for name, resp in zip(names, files)}


def exchange_ids(tables: dict[str, list[dict[str, str]]]) -> set[str]:
    """The base item ids PoE2's Currency Exchange trades: each `CurrencyExchange` row's Item, a
    `BaseItemTypes` row. Pure.

    Every row counts, enabled in challenge leagues or not: what Standard trades is in the game. A row
    naming a BaseItemTypes row that isn't there raises ValueError -- the export changed shape.
    """
    ids = {row["rownum"]: row["Id"] for row in tables["BaseItemTypes"]}
    return {_table_ref(ids, "BaseItemTypes", row["Item"], f"CurrencyExchange row {row['rownum']}")
            for row in tables["CurrencyExchange"]}


def main(argv: list[str]) -> None:
    """CLI: gamedata items <poe2-commit> <dat-export-commit> <patch> <out.json> -- fetch repoe-fork/poe2's
    export and dat-export's tables (`TABLE_NAMES`) at their commits, and write the item snapshot for game
    patch <patch> (e.g. 0.5.5) to <out.json>.

    Writes the file itself (UTF-8, no BOM, LF) instead of printing for a shell redirect: Windows
    PowerShell 5.1's `>` would write UTF-16, and text mode on Windows would turn LF into CRLF.
    """
    if len(argv) != 5 or argv[0] != "items":
        sys.exit("usage: python -m poe2_mcp.gamedata items <poe2-commit> <dat-export-commit> <patch> <out.json>")
    _, commit, tables_commit, patch, out = argv
    if not _PATCH_RE.fullmatch(patch):
        sys.exit(f"patch must be a game patch like 0.5.5 (or a hotfix like 0.5.5e), not {patch!r}")
    export = fetch_export(commit)
    tables = fetch_tables(tables_commit, TABLE_NAMES)
    items = build_items(export["mods_by_base"], export["mods"], export["base_items"])
    # Every augment gets an entry, traded or not; the exchange decides only for everything else.
    augments = build_augments(export["augments"])
    extras = {**build_essences(tables, export["mods"]), **augments}
    traded = exchange_ids(tables)
    items["texts"] = build_texts(export["base_items"], traded | set(augments), extras)
    items["chaos"] = build_chaos(tables)
    items["sekhemas"] = build_sekhemas(tables)
    items["passives"] = build_passives(tables)
    items["gems"] = build_gems(tables)
    items["exchange"] = build_exchange_names(export["base_items"], traded)
    items["uniques"] = build_unique_names(tables)
    source = (f"{EXPORT_REPO}@{commit} (game {export['game_version']}), "
              f"{TABLES_REPO}@{tables_commit} {TABLES_DIR} -- data is GGG's")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_items(items, patch, source))


if __name__ == "__main__":
    main(sys.argv[1:])
