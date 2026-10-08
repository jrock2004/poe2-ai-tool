"""Turn one loadout of a guide's PoB into an in-game Build Planner plan (a ``.build`` file's JSON).

The input is one loadout from ``pob.parse_loadouts``; the output is the planner's Build object, plus what
had no place in it. What the planner accepts was checked in game with hand-made files: passives named by
their PassiveSkills Id, gems by PoB's gemId, the ascendancy by PoB's ascendancyInternalId, gear by the
Inventories table's ids. No entry carries a level range -- in game, a ranged skill outside the player's
level vanishes from the Gemcutting window, and a ranged entry doesn't show its note.

``compare_plans`` sets a guide's new plans against the ones already in the planner folder, so a guide
written before is updated instead of written again.

Pure and offline -- no network. Finding the planner's folder and writing the file live elsewhere.
"""
from __future__ import annotations

import re
from typing import Any

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# PoB's equipment slot -> the game's Inventories id. Flasks, charms and PoB's Arm/Leg slots have none yet.
_INVENTORIES = {
    "Weapon 1": "Weapon1", "Weapon 2": "Offhand1", "Weapon 1 Swap": "Weapon2", "Weapon 2 Swap": "Offhand2",
    "Helmet": "Helm1", "Body Armour": "BodyArmour1", "Gloves": "Gloves1", "Boots": "Boots1",
    "Amulet": "Amulet1", "Ring 1": "Ring1", "Ring 2": "Ring2", "Ring 3": "Ring3", "Belt": "Belt1",
}


def plan_build(
    loadout: dict[str, Any],
    name: str,
    passive_ids: dict[str, str],
    *,
    author: str | None = None,
    link: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """One loadout as a Build Planner plan. Pure.

    `name` is the build's; the plan is "<name> - <loadout title>", or `name` alone for an untitled loadout.
    `passive_ids` maps a tree node id (as a string) to its PassiveSkills Id -- the item snapshot's
    "passives". `author`, `link` and `description` are set only when given; hovering the plan's name in
    game shows the description, with the author under it.

    Returns {"build": the plan, "leftOut": [{"what", "why"}]} in the order met: passives, skills, gear.
    `why` is a code -- "unmapped-passive", "item-granted", "disabled", "item-skill-support", "no-skill" or
    "unmapped-slot" -- for the calling skill to put in plain words. Sections with nothing in them are
    left out of the plan.
    """
    left_out: list[dict[str, str]] = []
    title = loadout.get("title")
    build: dict[str, Any] = {"name": f"{name} - {title}" if title else name}
    for key, value in (("author", author), ("link", link), ("description", description),
                       ("ascendancy", loadout.get("ascendancy"))):
        if value:
            build[key] = value

    sections = (("passives", _passives(loadout["passives"], passive_ids, left_out)),
                ("skills", _skills(loadout["skillGroups"], left_out)),
                ("inventory_slots", _inventory_slots(loadout["gear"], left_out)))
    build.update((key, value) for key, value in sections if value)
    return {"build": build, "leftOut": left_out}


def _entry(id_: str, **extra: Any) -> str | dict[str, Any]:
    """A bare id, or an object when there's more to say -- like GGG's own example file."""
    extra = {key: value for key, value in extra.items() if value}
    return {"id": id_, **extra} if extra else id_


def _passives(passives: list[dict[str, Any]], passive_ids: dict[str, str],
              left_out: list[dict[str, str]]) -> list[str | dict[str, Any]]:
    out = []
    for passive in passives:
        passive_id = passive_ids.get(str(passive["node"]))
        if passive_id is None:
            left_out.append({"what": f"passive node {passive['node']}", "why": "unmapped-passive"})
            continue
        out.append(_entry(passive_id, additional_text=passive["note"], weapon_set=passive["weaponSet"]))
    return out


def _skills(groups: list[dict[str, Any]], left_out: list[dict[str, str]]) -> list[dict[str, Any]]:
    """One entry per skill gem, first-seen order: its first note, and every group's supports merged."""
    skills: dict[str, dict[str, Any]] = {}  # gemId -> {"note", "supports": {gemId: note}}
    for group in groups:
        kept, disabled = [], False
        for active in group["actives"]:
            if active["weaponGranted"]:
                left_out.append({"what": active["name"], "why": "item-granted"})
            elif not active["enabled"]:
                left_out.append({"what": active["name"], "why": "disabled"})
                disabled = True
            else:
                kept.append(active)
        supports = []
        for support in group["supports"]:
            if support["enabled"]:
                supports.append(support)
            else:
                left_out.append({"what": support["name"], "why": "disabled"})
        if not kept:
            # Never dropped silently: a switched-off skill's supports are off with it; otherwise they
            # support a skill the gem list doesn't hold -- an item's, or none.
            why = ("disabled" if disabled else
                   "item-skill-support" if (group["source"] or "").startswith("Item:") else "no-skill")
            left_out.extend({"what": support["name"], "why": why} for support in supports)
            continue
        for active in kept:
            skill = skills.setdefault(active["gemId"], {"note": None, "supports": {}})
            skill["note"] = skill["note"] or active["note"]
            for support in supports:
                skill["supports"][support["gemId"]] = skill["supports"].get(support["gemId"]) or support["note"]

    out = []
    for gem_id, skill in skills.items():
        entry: dict[str, Any] = {"id": gem_id}
        if skill["note"]:
            entry["additional_text"] = skill["note"]
        if skill["supports"]:
            entry["support_skills"] = [_entry(support_id, additional_text=note)
                                       for support_id, note in skill["supports"].items()]
        out.append(entry)
    return out


def _inventory_slots(gear: list[dict[str, Any]], left_out: list[dict[str, str]]) -> list[dict[str, Any]]:
    """A slot's note as hover text and its unique by name; a slot with neither adds nothing."""
    out = []
    for slot in gear:
        item = slot["item"] or {}
        unique = item.get("name") if item.get("rarity") == "UNIQUE" else None
        if not (slot["note"] or unique):
            continue
        inventory = _INVENTORIES.get(slot["slot"])
        if inventory is None:
            left_out.append({"what": slot["slot"], "why": "unmapped-slot"})
            continue
        entry: dict[str, Any] = {"inventory_id": inventory}
        if slot["note"]:
            entry["additional_text"] = slot["note"]
        if unique:
            entry["unique_name"] = unique
        out.append(entry)
    return out


def compare_plans(
    new: list[dict[str, Any]], on_disk: list[dict[str, Any]], name: str, link: str | None,
) -> dict[str, Any]:
    """A guide's new plans against every plan already in the planner folder. Pure.

    `name` is the build's: this build's plans on disk are the ones named it, or "<name> - ...", in any case
    -- the file system's view, so another build's plans are never counted. Each new plan is matched to one
    of them by name, in any case: "new" when there's none, "changed" when anything but its description
    differs, else "unchanged". A description that differs only by a date doesn't count, so an unchanged
    plan keeps the day it was written.

    Returns {"stages": [{"name", "state"}] per new plan, in order; "write": the names to write -- new and
    changed, and unchanged ones whose description differs by more than a date (a stage count); "gone":
    this build's plans on disk the guide no longer has, in disk order; "conflict": this build's plans on
    disk that aren't provably this guide's -- another link, or no link to compare.
    """
    def ours(plan: dict[str, Any]) -> bool:
        plan_name = (plan.get("name") or "").casefold()
        return plan_name == name.casefold() or plan_name.startswith(f"{name.casefold()} - ")

    mine = [plan for plan in on_disk if ours(plan)]
    by_name = {plan["name"].casefold(): plan for plan in mine}
    stages, write = [], []
    for plan in new:
        old = by_name.get(plan["name"].casefold())
        if old is None:
            state, rewrite = "new", True
        else:
            same = _without_description(old) == _without_description(plan)
            state = "unchanged" if same else "changed"
            rewrite = not same or _undated(old) != _undated(plan)
        stages.append({"name": plan["name"], "state": state})
        if rewrite:
            write.append(plan["name"])

    names = {plan["name"].casefold() for plan in new}
    return {"stages": stages, "write": write,
            "gone": [plan["name"] for plan in mine if plan["name"].casefold() not in names],
            "conflict": [plan["name"] for plan in mine if link is None or plan.get("link") != link]}


def _without_description(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if key != "description"}


def _undated(plan: dict[str, Any]) -> str:
    return _DATE.sub("", plan.get("description") or "")
