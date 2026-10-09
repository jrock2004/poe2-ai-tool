"""Unit tests for turning one PoB loadout into an in-game Build Planner .build, for comparing a guide's new
plans with the ones already in the planner folder, and for what changed inside a stage (pure, no network).

The loadout is shaped like pob.parse_loadouts' output for a real 0.5 Infernalist guide, trimmed; passive ids
are the item snapshot's (dat-export PassiveSkills, game 4.5.5.2). What the planner accepts was checked in
game with hand-made files built the same way: passives by PassiveSkills Id, gems by gemId, the ascendancy by
PoB's ascendancyInternalId; notes show on skills and supports only without a level range, so none is set.
"""
from poe2_mcp.buildplanner import compare_plans, plan_build, plan_changes

PASSIVE_IDS = {"3823": "cold34", "51184": "witch_sorceress_notable1", "55180": "minion_offence21_",
               "61419": "jewel_slot1972", "17754": "AscendancyWitch1Notable10"}

GEMS = "Metadata/Items/Gems/"
GEM = "Metadata/Items/Gem/"  # PoB writes some gem ids this way; they're real BaseItemTypes ids too


def gem(path, name, note=None, enabled=True, weapon_granted=False):
    return {"gemId": path, "name": name, "enabled": enabled, "weaponGranted": weapon_granted, "note": note}


def group(actives, supports=(), source=None):
    return {"source": source, "actives": list(actives), "supports": list(supports)}


RAGING_NOTE = "<b>{Skill Crafting Order}\n\n1. Raging Spirits"
FIRE_NOTE = "<b>{Support Crafting Order}\n1. Fire Attunement"
LOADOUT = {
    "title": "Act 2",
    "ascendancy": "Witch1",
    "treeVersion": "0_5",
    "passives": [
        {"node": 3823, "weaponSet": None, "note": "<b>{Priority:} 2"},
        {"node": 51184, "weaponSet": None, "note": None},
        {"node": 61419, "weaponSet": 1, "note": None},
        {"node": 99999, "weaponSet": None, "note": None},  # not in this patch's passive ids
        {"node": 17754, "weaponSet": None, "note": None},
    ],
    "skillGroups": [
        group([gem(GEMS + "SkillGemChaosbolt", "Chaos Bolt", weapon_granted=True)], source="Item:1:Withered Wand"),
        group([gem(GEM + "SkillGemRagingSpirits", "Raging Spirits", note=RAGING_NOTE)],
              [gem(GEMS + "SupportGemFireInfusion", "Fire Attunement", note=FIRE_NOTE),
               gem(GEMS + "SupportGemPrimalArmamentTwo", "Elemental Armament II", enabled=False)]),
        group([gem(GEMS + "SkillGemSkeletalWarriorWeaponSkill", "Skeletal Warrior")],
              [gem(GEMS + "SupportGemMeatShield", "Meat Shield I")], source="Item:2:New Item, Rattling Sceptre"),
        group([gem(GEM + "SkillGemAscendancySummonInfernalHound", "Infernal Hound")],
              [gem(GEM + "SupportGemLoyalty", "Loyalty")], source="Tree:17754"),
        group([], [gem(GEM + "SupportGemSacrificialLamb", "Sacrificial Lamb I")],
              source="Item:2:New Item, Rattling Sceptre"),
        group([gem(GEMS + "SkillGemFlameWall", "Flame Wall", enabled=False)]),
        group([gem(GEM + "SkillGemRagingSpirits", "Raging Spirits")],
              [gem(GEMS + "SupportGemFireInfusion", "Fire Attunement"), gem(GEMS + "SupportGemUnleash", "Unleash")]),
    ],
    "gear": [
        {"slot": "Weapon 1", "item": {"rarity": "NORMAL", "name": "Withered Wand", "base": None},
         "note": "<u>{<b>{Withered Wand}}\n\n- A shield might help"},
        {"slot": "Weapon 2", "item": None, "note": "<u>{<b>{Any Focus}}"},
        {"slot": "Weapon 1 Swap", "item": None, "note": "<u>{<b>{Swap Wand}}"},
        {"slot": "Helmet", "item": {"rarity": "RARE", "name": "Gale Dome", "base": "Twig Circlet"}, "note": None},
        {"slot": "Boots", "item": {"rarity": "UNIQUE", "name": "Bones of Ullr", "base": "Lattice Sandals"},
         "note": None},
        {"slot": "Ring 3", "item": None, "note": "<u>{<b>{Any Ring}}"},
        {"slot": "Flask 1", "item": None, "note": "Life flask"},
        {"slot": "Arm 1", "item": None, "note": "Temple augment"},  # a temple mechanic's, lost on death
    ],
}


def plan(**kwargs):
    return plan_build(LOADOUT, "Minion Leveling", PASSIVE_IDS, **kwargs)


def test_the_plan_is_named_for_the_build_and_its_loadout():
    build = plan()["build"]
    assert build["name"] == "Minion Leveling - Act 2"
    assert build["ascendancy"] == "Witch1"


def test_an_untitled_loadout_takes_the_build_name_alone():
    assert plan_build({**LOADOUT, "title": None}, "Minion Leveling", PASSIVE_IDS)["build"]["name"] == "Minion Leveling"


def test_author_link_and_description_are_set_only_when_given():
    # Hovering the plan's name in game shows its description, with the author under it.
    assert not {"author", "link", "description"} & set(plan()["build"])
    build = plan(author="jrock2004", link="https://example.test/guide", description="Stage 3 of 9")["build"]
    assert (build["author"], build["link"], build["description"]) == (
        "jrock2004", "https://example.test/guide", "Stage 3 of 9")


def test_passives_are_ids_in_order_objects_only_for_a_note_or_weapon_set():
    # Like GGG's own example: a bare id, or an object when there's more to say. An unmapped node is left out.
    assert plan()["build"]["passives"] == [
        {"id": "cold34", "additional_text": "<b>{Priority:} 2"},
        "witch_sorceress_notable1",
        {"id": "jewel_slot1972", "weapon_set": 1},
        "AscendancyWitch1Notable10",
    ]


def test_skills_take_their_note_and_their_groups_supports():
    # A support with a note is an object, one without a bare id. A switched-off support stays out. The same
    # skill in a second group is one entry: supports merged in order, no repeats, its first note kept.
    # Skeletal Warrior comes from the sceptre and the hound from the tree, but both are real gems, so they stay.
    assert plan()["build"]["skills"] == [
        {"id": GEM + "SkillGemRagingSpirits", "additional_text": RAGING_NOTE,
         "support_skills": [{"id": GEMS + "SupportGemFireInfusion", "additional_text": FIRE_NOTE},
                            GEMS + "SupportGemUnleash"]},
        {"id": GEMS + "SkillGemSkeletalWarriorWeaponSkill", "support_skills": [GEMS + "SupportGemMeatShield"]},
        {"id": GEM + "SkillGemAscendancySummonInfernalHound", "support_skills": [GEM + "SupportGemLoyalty"]},
    ]


def test_gear_maps_pob_slots_to_the_games_inventories():
    # The note as hover text; a unique by name, and -- with no note -- a note naming it, since the game shows
    # nothing for unique_name alone (checked in game 2026-10-08). A rare with no note adds nothing.
    assert plan()["build"]["inventory_slots"] == [
        {"inventory_id": "Weapon1", "additional_text": "<u>{<b>{Withered Wand}}\n\n- A shield might help"},
        {"inventory_id": "Offhand1", "additional_text": "<u>{<b>{Any Focus}}"},
        {"inventory_id": "Weapon2", "additional_text": "<u>{<b>{Swap Wand}}"},
        {"inventory_id": "Boots1", "additional_text": "<b>{Bones of Ullr}\nLattice Sandals",
         "unique_name": "Bones of Ullr"},
        {"inventory_id": "Ring3", "additional_text": "<u>{<b>{Any Ring}}"},
        {"inventory_id": "Flask1", "slot_x": 0, "additional_text": "Life flask"},
    ]


def test_flasks_and_charms_share_the_flask_inventory_each_at_its_own_position():
    # Checked in game with a hand-made file: one Flask1 inventory, slot_x 0-1 the flasks and 2-4 the charms.
    gear = [{"slot": "Charm 2", "item": {"rarity": "UNIQUE", "name": "Nascent Hope", "base": "Thawing Charm"},
             "note": None},
            {"slot": "Flask 2", "item": None, "note": "Mana flask"}]
    assert plan_build({**LOADOUT, "gear": gear}, "Minion Leveling", PASSIVE_IDS)["build"]["inventory_slots"] == [
        {"inventory_id": "Flask1", "slot_x": 3, "additional_text": "<b>{Nascent Hope}\nThawing Charm",
         "unique_name": "Nascent Hope"},
        {"inventory_id": "Flask1", "slot_x": 1, "additional_text": "Mana flask"},
    ]


def test_a_flask_or_charm_with_no_note_is_named_by_its_item_and_what_it_does():
    # So the player still sees which charm to use and when it fires: guides often equip one without a word.
    # Its name, then its mods, implicits first. A note wins; elsewhere a rare with no note adds nothing
    # (PoB's rares are mostly "New Item").
    magic = {"rarity": "MAGIC", "base": None}
    gear = [{"slot": "Charm 1", "item": {**magic, "name": "Thawing Charm of the Verdant",
                                         "implicitMods": ["Used when you become Frozen"],
                                         "explicitMods": ["Gains 0.20 Charges per Second"]}, "note": None},
            {"slot": "Charm 2", "item": {**magic, "name": "Stone Charm", "implicitMods": [], "explicitMods": []},
             "note": None},
            {"slot": "Flask 1", "item": {**magic, "name": "Abundant Ultimate Life Flask"}, "note": "Life flask"},
            {"slot": "Belt", "item": {**magic, "name": "Heavy Belt of the Lynx"}, "note": None}]
    assert plan_build({**LOADOUT, "gear": gear}, "Minion Leveling", PASSIVE_IDS)["build"]["inventory_slots"] == [
        {"inventory_id": "Flask1", "slot_x": 2, "additional_text":
            "<b>{Thawing Charm of the Verdant}\n\nUsed when you become Frozen\nGains 0.20 Charges per Second"},
        {"inventory_id": "Flask1", "slot_x": 3, "additional_text": "<b>{Stone Charm}"},
        {"inventory_id": "Flask1", "slot_x": 0, "additional_text": "Life flask"},
    ]


# A .build names a unique by its UniqueName in the Words table (the item snapshot's "uniques"). PoB's own
# custom uniques are "New Item", which the game can't match: it isn't written, the slot's note still is.
UNIQUES = {"Bones of Ullr", "Nascent Hope"}


def _unique_slot(slot: str, name: str, note: str | None = None, **item: object) -> dict:
    return {"slot": slot, "item": {"rarity": "UNIQUE", "name": name, "base": "Some Base", **item}, "note": note}


def _unknown(result: dict) -> list[dict]:
    return [entry for entry in result["leftOut"] if entry["why"] == "unknown-unique"]


def test_a_unique_the_game_knows_is_written_by_name():
    gear = [_unique_slot("Boots", "Bones of Ullr")]
    result = plan_build({**LOADOUT, "gear": gear}, "Minion Leveling", PASSIVE_IDS, unique_names=UNIQUES)
    assert result["build"]["inventory_slots"] == [
        {"inventory_id": "Boots1", "additional_text": "<b>{Bones of Ullr}\nSome Base", "unique_name": "Bones of Ullr"}]
    assert _unknown(result) == []


def test_a_unique_with_no_note_is_named_with_its_base_and_mods_so_the_slot_shows_it():
    # In game, unique_name alone shows nothing on hover (2026-10-08): the note is what the player sees.
    gear = [_unique_slot("Boots", "Bones of Ullr", implicitMods=["+100 to Stun Threshold"],
                         explicitMods=["6% increased Movement Speed", "+40 to maximum Life"])]
    [slot] = plan_build({**LOADOUT, "gear": gear}, "Minion Leveling", PASSIVE_IDS)["build"]["inventory_slots"]
    assert slot["additional_text"] == ("<b>{Bones of Ullr}\nSome Base\n\n+100 to Stun Threshold\n"
                                       "6% increased Movement Speed\n+40 to maximum Life")


def test_a_uniques_guide_note_wins_over_its_name():
    gear = [_unique_slot("Boots", "Bones of Ullr", note="Wear these until 60")]
    [slot] = plan_build({**LOADOUT, "gear": gear}, "Minion Leveling", PASSIVE_IDS)["build"]["inventory_slots"]
    assert slot == {"inventory_id": "Boots1", "additional_text": "Wear these until 60", "unique_name": "Bones of Ullr"}


def test_a_unique_name_the_game_doesnt_know_is_left_out_but_the_slot_still_says_what_to_wear():
    # The guide's note if it has one, else the item's own name, base and mods -- PoB's custom uniques are
    # "New Item", so the mods are what says what it is.
    gear = [_unique_slot("Helmet", "New Item", note="<b>{Any ES helmet}"), _unique_slot("Gloves", "New Item")]
    result = plan_build({**LOADOUT, "gear": gear}, "Minion Leveling", PASSIVE_IDS, unique_names=UNIQUES)
    assert result["build"]["inventory_slots"] == [
        {"inventory_id": "Helm1", "additional_text": "<b>{Any ES helmet}"},
        {"inventory_id": "Gloves1", "additional_text": "<b>{New Item}\nSome Base"}]
    assert _unknown(result) == [{"what": "New Item", "why": "unknown-unique"},
                                {"what": "New Item", "why": "unknown-unique"}]


def test_an_unknown_unique_on_the_flask_bar_is_named_by_its_item_like_any_other():
    gear = [_unique_slot("Charm 1", "New Item", implicitMods=["Used when you become Frozen"], explicitMods=[])]
    result = plan_build({**LOADOUT, "gear": gear}, "Minion Leveling", PASSIVE_IDS, unique_names=UNIQUES)
    assert result["build"]["inventory_slots"] == [
        {"inventory_id": "Flask1", "slot_x": 2,
         "additional_text": "<b>{New Item}\nSome Base\n\nUsed when you become Frozen"}]
    assert _unknown(result) == [{"what": "New Item", "why": "unknown-unique"}]


def test_without_unique_names_every_unique_is_written():
    # No snapshot list to check against (an older snapshot): written as before.
    gear = [_unique_slot("Boots", "New Item")]
    assert plan_build({**LOADOUT, "gear": gear}, "Minion Leveling", PASSIVE_IDS)["build"]["inventory_slots"] == [
        {"inventory_id": "Boots1", "additional_text": "<b>{New Item}\nSome Base", "unique_name": "New Item"}]


def test_left_out_says_what_and_why_in_the_order_met():
    # Codes, not sentences: the skill tells the player in plain words.
    assert plan()["leftOut"] == [
        {"what": "passive node 99999", "why": "unmapped-passive"},
        {"what": "Chaos Bolt", "why": "item-granted"},
        {"what": "Elemental Armament II", "why": "disabled"},
        {"what": "Sacrificial Lamb I", "why": "item-skill-support"},
        {"what": "Flame Wall", "why": "disabled"},
        {"what": "Arm 1", "why": "unmapped-slot"},
    ]


def test_empty_sections_are_left_out_of_the_file():
    bare = {**LOADOUT, "ascendancy": None, "passives": [], "skillGroups": [], "gear": []}
    assert plan_build(bare, "Minion Leveling", PASSIVE_IDS) == {"build": {"name": "Minion Leveling - Act 2"},
                                                                 "leftOut": []}


def test_every_pob_equipment_slot_has_an_inventory():
    slots = ["Weapon 1", "Weapon 2", "Weapon 1 Swap", "Weapon 2 Swap", "Helmet", "Body Armour", "Gloves",
             "Boots", "Amulet", "Ring 1", "Ring 2", "Ring 3", "Belt", "Flask 1", "Flask 2", "Charm 1", "Charm 2",
             "Charm 3"]
    gear = [{"slot": s, "item": None, "note": "x"} for s in slots]
    out = plan_build({**LOADOUT, "gear": gear}, "Minion Leveling", PASSIVE_IDS)
    assert [(s["inventory_id"], s.get("slot_x")) for s in out["build"]["inventory_slots"]] == [
        ("Weapon1", None), ("Offhand1", None), ("Weapon2", None), ("Offhand2", None), ("Helm1", None),
        ("BodyArmour1", None), ("Gloves1", None), ("Boots1", None), ("Amulet1", None), ("Ring1", None),
        ("Ring2", None), ("Ring3", None), ("Belt1", None),
        ("Flask1", 0), ("Flask1", 1), ("Flask1", 2), ("Flask1", 3), ("Flask1", 4)]
    assert not [x for x in out["leftOut"] if x["why"] == "unmapped-slot"]


def test_a_support_only_group_with_no_source_is_reported_too():
    # Supports with no skill to go under, whatever the reason: never dropped silently.
    lone = {**LOADOUT, "skillGroups": [group([], [gem(GEMS + "SupportGemMeatShield", "Meat Shield I")])]}
    assert {"what": "Meat Shield I", "why": "no-skill"} in plan_build(lone, "Minion Leveling", PASSIVE_IDS)["leftOut"]


def test_a_switched_off_skills_supports_are_left_out_as_disabled_too():
    # They're off with their skill, even one an item grants -- not supports missing a skill.
    off = {**LOADOUT, "passives": [], "gear": [], "skillGroups": [
        group([gem(GEMS + "SkillGemFlameWall", "Flame Wall", enabled=False)],
              [gem(GEMS + "SupportGemUnleash", "Unleash")]),
        group([gem(GEMS + "SkillGemSkeletalWarriorWeaponSkill", "Skeletal Warrior", enabled=False)],
              [gem(GEMS + "SupportGemMeatShield", "Meat Shield I")], source="Item:2:New Item, Rattling Sceptre"),
    ]}
    assert plan_build(off, "Minion Leveling", PASSIVE_IDS)["leftOut"] == [
        {"what": "Flame Wall", "why": "disabled"}, {"what": "Unleash", "why": "disabled"},
        {"what": "Skeletal Warrior", "why": "disabled"}, {"what": "Meat Shield I", "why": "disabled"},
    ]


# compare_plans: a guide's plans, about to be written, against the plans already in the folder -- all of them,
# as read from disk. Shaped like write_build_plan's output for a three-stage guide.
LINK = "https://example.test/infernalist"


def staged(n, title, of=3, day="2026-10-07", **content):
    return {"name": f"Infernalist - {n} {title}", "link": LINK,
            "description": f"Stage {n} of {of}. Written {day} from the guide's PoB.",
            "passives": ["cold34"], **content}


NEW = [staged(1, "Act 1"), staged(2, "Act 2"), staged(3, "Maps")]


def states(out):
    return [(s["name"], s["state"]) for s in out["stages"]]


def test_with_nothing_of_this_build_on_disk_every_stage_is_new():
    out = compare_plans(NEW, [], "Infernalist", LINK)
    assert states(out) == [("Infernalist - 1 Act 1", "new"), ("Infernalist - 2 Act 2", "new"),
                           ("Infernalist - 3 Maps", "new")]
    assert (out["write"], out["gone"], out["conflict"]) == (
        ["Infernalist - 1 Act 1", "Infernalist - 2 Act 2", "Infernalist - 3 Maps"], [], [])


def test_a_stage_the_guide_did_not_change_is_left_alone_even_on_another_day():
    # Its "Written" date then keeps meaning when the stage last changed.
    disk = [staged(1, "Act 1", day="2026-09-01"), staged(2, "Act 2", day="2026-09-01"),
            staged(3, "Maps", day="2026-09-01")]
    out = compare_plans(NEW, disk, "Infernalist", LINK)
    assert [state for _, state in states(out)] == ["unchanged"] * 3
    assert out["write"] == []


def test_a_stage_whose_passives_skills_or_gear_changed_is_rewritten():
    disk = [staged(1, "Act 1"), staged(2, "Act 2", passives=["cold34", "witch_sorceress_notable1"]),
            staged(3, "Maps", inventory_slots=[{"inventory_id": "Boots1", "unique_name": "Bones of Ullr"}])]
    out = compare_plans(NEW, disk, "Infernalist", LINK)
    assert states(out) == [("Infernalist - 1 Act 1", "unchanged"), ("Infernalist - 2 Act 2", "changed"),
                           ("Infernalist - 3 Maps", "changed")]
    assert out["write"] == ["Infernalist - 2 Act 2", "Infernalist - 3 Maps"]


def test_a_new_stage_count_rewrites_the_descriptions_without_calling_them_changed():
    # "Stage 1 of 2" has to become "of 3", but the player is only told about the stage that's new.
    disk = [staged(1, "Act 1", of=2), staged(2, "Act 2", of=2)]
    out = compare_plans(NEW, disk, "Infernalist", LINK)
    assert states(out) == [("Infernalist - 1 Act 1", "unchanged"), ("Infernalist - 2 Act 2", "unchanged"),
                           ("Infernalist - 3 Maps", "new")]
    assert out["write"] == ["Infernalist - 1 Act 1", "Infernalist - 2 Act 2", "Infernalist - 3 Maps"]


def test_this_builds_plans_the_guide_no_longer_has_are_gone():
    # Matched by name, number and all: a renamed or renumbered stage is new, and its old plan is gone.
    disk = [staged(1, "Act 1"), staged(2, "Act 2"), staged(3, "Early Maps"), staged(4, "Late Maps", of=4)]
    out = compare_plans(NEW, disk, "Infernalist", LINK)
    assert states(out)[2] == ("Infernalist - 3 Maps", "new")
    assert out["gone"] == ["Infernalist - 3 Early Maps", "Infernalist - 4 Late Maps"]


def test_names_match_in_any_case_as_the_file_system_sees_them():
    # A guide fixing a title's case writes the same file; it must never be listed as gone.
    disk = [staged(1, "act 1"), staged(2, "Act 2"), staged(3, "Maps")]
    out = compare_plans(NEW, disk, "Infernalist", LINK)
    assert states(out)[0] == ("Infernalist - 1 Act 1", "changed")
    assert out["gone"] == []


def test_other_builds_plans_are_never_counted():
    other = [{**staged(1, "Act 1"), "name": "Deadeye - 1 Act 1"},
             {**staged(1, "Act 1"), "name": "Infernalist Minions - 1 Act 1", "link": "https://example.test/other"}]
    out = compare_plans(NEW, other, "Infernalist", LINK)
    assert [state for _, state in states(out)] == ["new"] * 3
    assert (out["gone"], out["conflict"]) == ([], [])


def test_this_builds_plans_from_another_guide_or_with_no_link_are_a_conflict():
    # Same name, but not provably the same guide: the tool asks before touching them. A single-stage plan
    # is the build's name alone.
    disk = [staged(1, "Act 1"), {**staged(2, "Act 2"), "link": "https://example.test/other"},
            {"name": "Infernalist", "passives": ["cold34"]}]
    out = compare_plans(NEW, disk, "Infernalist", LINK)
    assert out["conflict"] == ["Infernalist - 2 Act 2", "Infernalist"]
    assert compare_plans(NEW, [staged(1, "Act 1")], "Infernalist", None)["conflict"] == ["Infernalist - 1 Act 1"]


# plan_changes: what changed inside one stage between the plan on disk and the guide's new one. Names come from
# lookups the caller builds -- notables and keystones from the tree snapshot, gems from the item snapshot.
PASSIVE_NAMES = {"passive_keystone_zealots_oath": "Zealot's Oath", "ailments38": "Fast Acting Toxins",
                 "mana_regeneration49": "Efficient Killing"}
RAGING, FLAME_WALL = GEM + "SkillGemRagingSpirits", GEMS + "SkillGemFlameWall"
SKELETAL, FIRE = GEMS + "SkillGemSkeletalWarriorWeaponSkill", GEMS + "SupportGemFireInfusion"
UNLEASH, MEAT_SHIELD = GEMS + "SupportGemUnleash", GEMS + "SupportGemMeatShield"
GEM_NAMES = {RAGING: "Raging Spirits", FLAME_WALL: "Flame Wall", SKELETAL: "Skeletal Warrior",
             FIRE: "Fire Attunement", UNLEASH: "Unleash", MEAT_SHIELD: "Meat Shield I"}

BEFORE = {
    "name": "Minion Leveling - 4 Act 3", "ascendancy": "Witch1", "description": "Stage 4 of 9. Written 2026-09-01.",
    "passives": ["attributes1", {"id": "ailments38", "additional_text": "Priority 1"},
                 "passive_keystone_zealots_oath", "cold34"],
    "skills": [{"id": RAGING, "additional_text": "order",
                "support_skills": [FIRE, {"id": UNLEASH, "additional_text": "x"}]},
               {"id": FLAME_WALL}],
    "inventory_slots": [{"inventory_id": "Weapon1", "additional_text": "Any wand"},
                        {"inventory_id": "Boots1", "unique_name": "Bones of Ullr"}],
}
AFTER = {
    **BEFORE, "description": "Stage 4 of 10. Written 2026-10-08.",
    "passives": ["attributes1", {"id": "ailments38", "additional_text": "Priority 2"}, "mana_regeneration49",
                 "cold35"],
    "skills": [{"id": RAGING, "additional_text": "order",
                "support_skills": [{"id": FIRE, "additional_text": "now first"}, MEAT_SHIELD]},
               {"id": SKELETAL, "additional_text": "from the sceptre", "support_skills": [UNLEASH]}],
    "inventory_slots": [{"inventory_id": "Weapon1", "additional_text": "Any wand, or a sceptre"},
                        {"inventory_id": "Helm1", "additional_text": "Any helmet"}],
}


def changes(before, after):
    return plan_changes(before, after, passive_names=PASSIVE_NAMES, gem_names=GEM_NAMES)


def test_plan_changes_names_what_a_stage_gained_and_lost():
    # Notables and keystones by name, other passives counted; supports under the skill they serve; notes
    # counted, never quoted -- they stay out of the reply.
    assert changes(BEFORE, AFTER) == {
        "passives": {"added": ["Efficient Killing"], "removed": ["Zealot's Oath"], "otherAdded": 1,
                     "otherRemoved": 1},
        "skills": {"added": ["Skeletal Warrior"], "removed": ["Flame Wall"]},
        "supports": {"added": [{"skill": "Raging Spirits", "support": "Meat Shield I"}],
                     "removed": [{"skill": "Raging Spirits", "support": "Unleash"}]},
        "notes": 4,
        "uniques": [{"slot": "Boots1", "was": "Bones of Ullr", "now": None}],
    }


def test_plan_changes_counts_only_notes_on_what_both_plans_hold():
    # The notes: a passive's, a support's, and two gear slots' (one only now has a note). A skill that's new
    # brings its own note and supports with it -- they're not counted or listed again.
    out = changes(BEFORE, AFTER)
    assert out["notes"] == 4
    assert {"skill": "Skeletal Warrior", "support": "Unleash"} not in out["supports"]["added"]


def test_plan_changes_of_a_stage_that_did_not_change_is_empty():
    # Its description doesn't count: the stage count and the day are compare_plans' business.
    assert changes(BEFORE, {**BEFORE, "description": "Stage 4 of 10. Written 2026-10-08."}) == {}


def test_plan_changes_leaves_out_what_did_not_change():
    after = {**BEFORE, "passives": [*BEFORE["passives"], "cold35"]}
    assert changes(BEFORE, after) == {"passives": {"added": [], "removed": [], "otherAdded": 1, "otherRemoved": 0}}


def test_plan_changes_falls_back_to_the_id_for_a_gem_it_cannot_name():
    unknown = GEMS + "SkillGemSomethingNew"
    after = {**BEFORE, "skills": [*BEFORE["skills"], {"id": unknown}]}
    assert changes(BEFORE, after)["skills"] == {"added": [unknown], "removed": []}


def test_plan_changes_reports_a_new_ascendancy():
    assert changes(BEFORE, {**BEFORE, "ascendancy": "Witch2"}) == {"ascendancy": {"was": "Witch1", "now": "Witch2"}}


def test_plan_changes_ignores_a_passive_only_moving_between_weapon_sets():
    # Not in the first version: weapon sets aren't checked in game yet.
    after = {**BEFORE, "passives": ["attributes1", {"id": "ailments38", "additional_text": "Priority 1",
                                                     "weapon_set": 2}, "passive_keystone_zealots_oath", "cold34"]}
    assert changes(BEFORE, after) == {}


def test_plan_changes_tells_the_flask_bar_slots_apart():
    # Five slots share the Flask1 inventory; slot_x says which is which, and a unique is reported by PoB's name.
    before = {**BEFORE, "inventory_slots": [{"inventory_id": "Flask1", "slot_x": 0, "additional_text": "Life"},
                                            {"inventory_id": "Flask1", "slot_x": 2, "unique_name": "Nascent Hope"}]}
    after = {**BEFORE, "inventory_slots": [{"inventory_id": "Flask1", "slot_x": 0, "additional_text": "Life"},
                                           {"inventory_id": "Flask1", "slot_x": 2, "additional_text": "Any charm"}]}
    assert changes(before, after) == {"notes": 1,
                                      "uniques": [{"slot": "Charm 1", "was": "Nascent Hope", "now": None}]}
