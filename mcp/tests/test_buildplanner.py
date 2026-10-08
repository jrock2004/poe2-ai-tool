"""Unit tests for turning one PoB loadout into an in-game Build Planner .build, and for comparing a guide's new
plans with the ones already in the planner folder (pure, no network).

The loadout is shaped like pob.parse_loadouts' output for a real 0.5 Infernalist guide, trimmed; passive ids
are the item snapshot's (dat-export PassiveSkills, game 4.5.5.2). What the planner accepts was checked in
game with hand-made files built the same way: passives by PassiveSkills Id, gems by gemId, the ascendancy by
PoB's ascendancyInternalId; notes show on skills and supports only without a level range, so none is set.
"""
from poe2_mcp.buildplanner import compare_plans, plan_build

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
    # The note as hover text; a unique by name. A slot with neither (a rare, no note) adds nothing.
    assert plan()["build"]["inventory_slots"] == [
        {"inventory_id": "Weapon1", "additional_text": "<u>{<b>{Withered Wand}}\n\n- A shield might help"},
        {"inventory_id": "Offhand1", "additional_text": "<u>{<b>{Any Focus}}"},
        {"inventory_id": "Weapon2", "additional_text": "<u>{<b>{Swap Wand}}"},
        {"inventory_id": "Boots1", "unique_name": "Bones of Ullr"},
        {"inventory_id": "Ring3", "additional_text": "<u>{<b>{Any Ring}}"},
    ]


def test_left_out_says_what_and_why_in_the_order_met():
    # Codes, not sentences: the skill tells the player in plain words.
    assert plan()["leftOut"] == [
        {"what": "passive node 99999", "why": "unmapped-passive"},
        {"what": "Chaos Bolt", "why": "item-granted"},
        {"what": "Elemental Armament II", "why": "disabled"},
        {"what": "Sacrificial Lamb I", "why": "item-skill-support"},
        {"what": "Flame Wall", "why": "disabled"},
        {"what": "Flask 1", "why": "unmapped-slot"},
    ]


def test_empty_sections_are_left_out_of_the_file():
    bare = {**LOADOUT, "ascendancy": None, "passives": [], "skillGroups": [], "gear": []}
    assert plan_build(bare, "Minion Leveling", PASSIVE_IDS) == {"build": {"name": "Minion Leveling - Act 2"},
                                                                 "leftOut": []}


def test_every_pob_equipment_slot_has_an_inventory():
    slots = ["Weapon 1", "Weapon 2", "Weapon 1 Swap", "Weapon 2 Swap", "Helmet", "Body Armour", "Gloves",
             "Boots", "Amulet", "Ring 1", "Ring 2", "Ring 3", "Belt"]
    gear = [{"slot": s, "item": None, "note": "x"} for s in slots]
    out = plan_build({**LOADOUT, "gear": gear}, "Minion Leveling", PASSIVE_IDS)
    assert [s["inventory_id"] for s in out["build"]["inventory_slots"]] == [
        "Weapon1", "Offhand1", "Weapon2", "Offhand2", "Helm1", "BodyArmour1", "Gloves1", "Boots1", "Amulet1",
        "Ring1", "Ring2", "Ring3", "Belt1"]
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
