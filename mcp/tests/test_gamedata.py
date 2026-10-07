"""Unit tests for the game-data snapshot generator (no network: the fetch runs over a mock transport)."""
import json

import httpx
import pytest

from poe2_mcp import gamedata
from poe2_mcp.gamedata import (
    build_items,
    build_texts,
    clean_text,
    fetch_exchange,
    fetch_export,
    item_text,
    load_items,
    main,
    mod_tiers,
    newest_snapshot,
    render_items,
)

HELM = "Metadata/Items/Armours/Helmets/"
BODY = "Metadata/Items/Armours/BodyArmours/"
CURRENCY = "Metadata/Items/Currency/"


@pytest.mark.parametrize("raw, clean", [
    ("+(41-45)% to [Resistances|Fire Resistance]", "+(41-45)% to Fire Resistance"),
    ("additional [Rune]-only sockets:", "additional Rune-only sockets:"),
    ("Grants Skill: <underline>{Fire Spell on Hit}", "Grants Skill: Fire Spell on Hit"),
    ("+(10-19) to maximum Life", "+(10-19) to maximum Life"),
])
def test_clean_text_strips_the_games_display_markup(raw, clean):
    assert clean_text(raw) == clean


# Shaped like repoe-fork/poe2's data/mods_by_base.json, mods.json and base_items.json (export 4.5.5.2),
# trimmed: real ids, names, requirements, levels and text. mods_by_base is item class -> base tag group ->
# {bases, mods by kind -> family -> {tier id: item level}}.
MODS_BY_BASE = {
    "Helmets": {
        "str_armour,ezomyte_basetype,helmet,armour,default": {
            "bases": [HELM + "FourHelmetStr1", HELM + "FourHelmetStr2"],
            "mods": {
                "prefix": {"IncreasedLife": {"IncreasedLife2": 6, "IncreasedLife1": 1}},  # out of order
                "suffix": {"FireResistance": {"FireResist1": 1, "FireResist8": 82}},
                "corrupted": {"FireResistance": {"FireResist1": 1}},
                "unique": {"IncreasedLife": {"IncreasedLife1": 1}},
            },
            "conditional_mods": None,
        },
    },
    "Body Armours": {
        "str_dex_armour,body_armour,armour,default": {
            "bases": [BODY + "FourBodyStrDex12a", BODY + "FourBodyStrDex12b"],
            "mods": {"prefix": {"IncreasedLife": {"IncreasedLife1": 1}}, "suffix": {}},
            "conditional_mods": None,
        },
        "dex_int_armour,karui_basetype,body_armour,armour,default": {
            "bases": [BODY + "FourBodyDexInt8"],
            "mods": {"prefix": {"IncreasedLife": {"IncreasedLife1": 1, "IncreasedLife2": 6}}, "suffix": {}},
            "conditional_mods": None,
        },
        "dex_int_armour,body_armour,armour,default": {
            "bases": [BODY + "FourBodyDexInt1Cruel"],
            "mods": {"prefix": {}, "suffix": {"FireResistance": {"FireResist1": 1}}},
            "conditional_mods": None,
        },
    },
    "Two Hand Swords": {
        "sword,two_hand_weapon,default": {
            "bases": ["Metadata/Items/Weapons/TwoHandWeapons/TwoHandSwords/TwoHandSwordDev"],
            "mods": {"prefix": {"IncreasedLife": {"IncreasedLife1": 1}}, "suffix": {}},
            "conditional_mods": None,
        },
    },
    "Stackable Currency": {
        "currency,default": {"bases": ["Metadata/Items/Currency/CurrencyModValues"], "mods": {}, "conditional_mods": None},
    },
}


def _mod(name, side, level, family, text):
    return {"name": name, "generation_type": side, "required_level": level, "type": family, "text": text,
            "domain": "item", "stats": []}


MODS = {
    "IncreasedLife1": _mod("Hale", "prefix", 1, "IncreasedLife", "+(10-19) to maximum Life"),
    "IncreasedLife2": _mod("Healthy", "prefix", 6, "IncreasedLife", "+(20-29) to maximum Life"),
    "FireResist1": _mod("of the Whelpling", "suffix", 1, "FireResistance", "+(6-10)% to [Resistances|Fire Resistance]"),
    "FireResist8": _mod("of Tzteosh", "suffix", 82, "FireResistance", "+(41-45)% to [Resistances|Fire Resistance]"),
    "Strength1": _mod("of the Brute", "suffix", 1, "Strength", "+(5-8) to [Strength|Strength]"),  # no group uses it
}


def _base(name, item_class, level, strength=0, dexterity=0, intelligence=0, release_state="released"):
    return {"name": name, "item_class": item_class, "release_state": release_state, "domain": "item",
            "requirements": {"level": level, "strength": strength, "dexterity": dexterity,
                             "intelligence": intelligence}}


def _stackable(name, item_class, description, directions):
    # A currency-like record, trimmed to its text. The export leaves missing text as "" or null.
    return {"name": name, "item_class": item_class, "release_state": "released",
            "properties": {"description": description, "directions": directions}}


BASE_ITEMS = {
    HELM + "FourHelmetStr1": _base("Rusted Greathelm", "Helmet", 1),
    HELM + "FourHelmetStr2": _base("Soldier Greathelm", "Helmet", 12, strength=19),
    BODY + "FourBodyStrDex12a": _base("Tournament Mail", "Body Armour", 68, strength=67, dexterity=67),
    BODY + "FourBodyStrDex12b": _base("Tournament Mail", "Body Armour", 68, strength=67, dexterity=67),
    BODY + "FourBodyDexInt8": _base("Ascetic Garb", "Body Armour", 51, dexterity=45, intelligence=45),
    BODY + "FourBodyDexInt1Cruel": _base("Ascetic Garb", "Body Armour", 45, dexterity=41, intelligence=41),
    "Metadata/Items/Weapons/TwoHandWeapons/TwoHandSwords/TwoHandSwordDev":
        _base("Keyblade", "Two Hand Sword", 1, release_state="unreleased"),
    "Metadata/Items/Currency/CurrencyModValues": _base("Divine Orb", "StackableCurrency", 1),
    # For the text: real descriptions and directions, markup and line endings as the export has them.
    CURRENCY + "CurrencyRerollRare": _stackable(
        "Chaos Orb", "StackableCurrency",
        "Removes a random modifier and augments a [ItemRarity|Rare] item with a new random modifier",
        "Right click this item then left click a rare item to apply it."),
    CURRENCY + "OmenOnChaosPrefix": _stackable(
        "Omen of Sinistral Erasure", "Omen",
        "While this item is active in your inventory your next\nChaos Orb will remove only prefix modifiers",
        "Right click this item in your inventory to set it to be active. This item is consumed when triggered."),
    CURRENCY + "CurrencyJewelleryQualityLife": _stackable(
        "Flesh Catalyst", "StackableCurrency",
        "Adds [Quality|quality] that enhances Life modifiers on a ring or amulet\r\nReplaces other quality types",
        "Right click this item then left click a ring or amulet to apply it."),
    "Metadata/Items/SoulCores/RuneWarpingCreateJewelSocket": _stackable(
        "Cadigan's Epiphany", "SoulCore",
        "Place into an empty [Augment] Socket in a pair of Gloves to apply its effect to that item. Once socketed "
        "it cannot be retrieved or replaced. ", ""),
    CURRENCY + "CurrencyUpgradeToMagicShard": _stackable(
        "Transmutation Shard", "StackableCurrency", "",
        "A stack of 10 shards becomes an [OrbOfTransmutation|Orb of Transmutation]"),
    "Metadata/Items/MapFragments/VaultKeyWorldDrop": _stackable("Twilight Reliquary Key", "VaultKey", None, None),
    CURRENCY + "CurrencyConvertToNormal": _stackable(
        "Orb of Scouring", "StackableCurrency", "Removes all modifiers from an item",
        "Right click this item then left click on a magic or rare item to apply it."),
}
# What PoE2's Currency Exchange trades, of those: all but Orb of Scouring.
TRADED = {
    CURRENCY + "CurrencyRerollRare", CURRENCY + "OmenOnChaosPrefix", CURRENCY + "CurrencyJewelleryQualityLife",
    "Metadata/Items/SoulCores/RuneWarpingCreateJewelSocket", CURRENCY + "CurrencyUpgradeToMagicShard",
    "Metadata/Items/MapFragments/VaultKeyWorldDrop",
}


def _items():
    return build_items(MODS_BY_BASE, MODS, BASE_ITEMS)


def _pool(items, base, variant=0):
    return items["groups"][items["bases"][base][variant]["group"]]


def test_build_items_gives_a_base_its_pools_tiers_in_item_level_order():
    items = _items()
    assert items["bases"]["Rusted Greathelm"] == [
        {"class": "Helmets", "group": items["bases"]["Rusted Greathelm"][0]["group"],
         "requirements": {"level": 1, "str": 0, "dex": 0, "int": 0}}]
    assert _pool(items, "Rusted Greathelm") == {
        "prefix": {"IncreasedLife": ["IncreasedLife1", "IncreasedLife2"]},
        "suffix": {"FireResistance": ["FireResist1", "FireResist8"]},
    }
    assert _pool(items, "Soldier Greathelm") == _pool(items, "Rusted Greathelm")  # one tag group, one pool


def test_build_items_describes_each_tier_with_its_text_cleaned():
    assert _items()["mods"]["FireResist8"] == {
        "name": "of Tzteosh", "side": "suffix", "level": 82, "family": "FireResistance",
        "text": "+(41-45)% to Fire Resistance"}


def test_build_items_keeps_prefixes_and_suffixes_only():
    # Corruption and unique mods aren't rolled by crafting currency; a later slice can add corruption.
    assert all(set(group) == {"prefix", "suffix"} for group in _items()["groups"])


def test_build_items_lists_only_the_tiers_a_pool_uses():
    assert set(_items()["mods"]) == {"IncreasedLife1", "IncreasedLife2", "FireResist1", "FireResist8"}


def test_build_items_leaves_out_unreleased_bases_and_non_equipment_classes():
    bases = _items()["bases"]
    assert "Keyblade" not in bases and "Divine Orb" not in bases


def test_build_items_merges_same_named_bases_with_the_same_pool():
    assert len(_items()["bases"]["Tournament Mail"]) == 1


def test_build_items_keeps_same_named_variants_that_roll_different_pools():
    # Two "Ascetic Garb" bases (one a Cruel campaign variant) roll different mods: keep both, the
    # lower-level one first, so a lookup can tell them apart by their requirements.
    garb = _items()["bases"]["Ascetic Garb"]
    assert [v["requirements"]["level"] for v in garb] == [45, 51]
    assert garb[0]["group"] != garb[1]["group"]


@pytest.mark.parametrize("drop", ["mods", "base_items"])
def test_build_items_refuses_a_reference_it_cant_resolve(drop):
    # A tier or base the other file doesn't have means the export changed shape: fail, don't guess.
    mods = {k: v for k, v in MODS.items() if k != "FireResist8"} if drop == "mods" else MODS
    base_items = ({k: v for k, v in BASE_ITEMS.items() if not k.endswith("FourHelmetStr2")}
                  if drop == "base_items" else BASE_ITEMS)
    with pytest.raises(ValueError, match="FireResist8" if drop == "mods" else "FourHelmetStr2"):
        build_items(MODS_BY_BASE, mods, base_items)


def _texts():
    return build_texts(BASE_ITEMS, TRADED)


def test_build_texts_gives_each_traded_item_its_class_description_and_directions():
    assert _texts()["Omen of Sinistral Erasure"] == {
        "class": "Omen",
        "text": "While this item is active in your inventory your next\nChaos Orb will remove only prefix modifiers",
        "use": "Right click this item in your inventory to set it to be active. This item is consumed when triggered.",
    }


@pytest.mark.parametrize("name, text, use", [
    # Markup removed; a Windows line ending becomes the game's line break.
    ("Flesh Catalyst", "Adds quality that enhances Life modifiers on a ring or amulet\nReplaces other quality types",
     "Right click this item then left click a ring or amulet to apply it."),
    # Edge spaces trimmed; no directions is "".
    ("Cadigan's Epiphany", "Place into an empty Augment Socket in a pair of Gloves to apply its effect to that item. "
     "Once socketed it cannot be retrieved or replaced.", ""),
    # Directions alone are worth keeping: they say what shards are for.
    ("Transmutation Shard", "", "A stack of 10 shards becomes an Orb of Transmutation"),
])
def test_build_texts_cleans_the_text_to_what_a_player_reads(name, text, use):
    assert (_texts()[name]["text"], _texts()[name]["use"]) == (text, use)


def test_build_texts_keeps_only_traded_items_that_have_text_by_name():
    # The game files still carry PoE1 items marked released (Orb of Scouring); PoE2's own Currency Exchange
    # doesn't trade them. A traded item with neither text (a Reliquary Key) has nothing to quote.
    assert list(_texts()) == [
        "Cadigan's Epiphany", "Chaos Orb", "Flesh Catalyst", "Omen of Sinistral Erasure", "Transmutation Shard"]


def test_build_texts_refuses_a_traded_item_it_cant_resolve():
    # The exchange and the items pinned at different game versions: fail, don't guess.
    with pytest.raises(ValueError, match="CurrencyNotInTheExport"):
        build_texts(BASE_ITEMS, TRADED | {CURRENCY + "CurrencyNotInTheExport"})


def test_build_texts_refuses_two_traded_items_with_one_name():
    # The text is looked up by name, so a second "Chaos Orb" would be ambiguous.
    base_items = {**BASE_ITEMS, CURRENCY + "CurrencyRerollRareCopy": BASE_ITEMS[CURRENCY + "CurrencyRerollRare"]}
    with pytest.raises(ValueError, match="Chaos Orb"):
        build_texts(base_items, TRADED | {CURRENCY + "CurrencyRerollRareCopy"})


def test_render_items_is_json_with_one_mod_and_one_text_per_line():
    items = {**_items(), "texts": _texts()}
    text = render_items(items, "0.5.5", "repoe-fork/poe2@abc123 (game 4.5.5.2)")
    snapshot = json.loads(text)
    assert snapshot["patch"] == "0.5.5" and snapshot["source"] == "repoe-fork/poe2@abc123 (game 4.5.5.2)"
    assert {k: snapshot[k] for k in ("groups", "bases", "mods", "texts")} == items
    assert sum('"side":' in line for line in text.splitlines()) == len(snapshot["mods"])
    assert sum('"use":' in line for line in text.splitlines()) == len(snapshot["texts"])
    assert text.endswith("\n")


COMMIT = "0123abcd"
REPO = f"/repoe-fork/poe2/{COMMIT}"
EXPORT = {"mods_by_base": MODS_BY_BASE, "mods": MODS, "base_items": BASE_ITEMS, "game_version": "4.5.5.2"}
EXCHANGE_COMMIT = "4567cdef"
TABLES = f"/repoe-fork/dat-export/{EXCHANGE_COMMIT}/current/poe2/heuristics/csv"
# Shaped like repoe-fork/dat-export's CurrencyExchange.csv and BaseItemTypes.csv (game 4.5.5.2), trimmed: real
# rows, fewer columns. An exchange row's Item is a BaseItemTypes rownum.
EXCHANGE_CSV = (
    '"rownum","Item","Category","SubCategory","EnabledInStandardLeague","EnabledInChallengeLeague",'
    '"GoldPurchaseFee","bool_54","bool_55"\n'
    '12,3,0,0,1,1,160,"",1\n'
    '330,4436,6,41,1,1,1000,"",1\n'
    '318,4442,6,41,1,"",450,"",1\n'
)
BASE_ITEM_TYPES_CSV = (
    '"rownum","Id","Name"\n'
    '3,"Metadata/Items/Currency/CurrencyRerollRare","Chaos Orb"\n'
    '17,"Metadata/Items/Currency/CurrencyConvertToNormal","Orb of Scouring"\n'
    '4436,"Metadata/Items/Currency/OmenOnChaosPrefix","Omen of Sinistral Erasure"\n'
    '4442,"Metadata/Items/Currency/OmenOnVaalRemoveDoNothingOutcome","Omen of Corruption"\n'
)


def _transport(calls: list[str], status: int = 200) -> httpx.MockTransport:
    """GitHub's raw file host, serving both fixture exports at their commits; records each URL asked for."""
    served = {f"{REPO}/data/mods_by_base.json": MODS_BY_BASE, f"{REPO}/data/mods.json": MODS,
              f"{REPO}/data/base_items.json": BASE_ITEMS, f"{REPO}/version.txt": "4.5.5.2\n",
              f"{TABLES}/CurrencyExchange.csv": EXCHANGE_CSV, f"{TABLES}/BaseItemTypes.csv": BASE_ITEM_TYPES_CSV}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status)
        body = served[request.url.path]
        return httpx.Response(200, text=body) if isinstance(body, str) else httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


def test_fetch_export_reads_the_three_files_and_the_game_version_at_the_commit():
    calls: list[str] = []
    assert fetch_export(COMMIT, transport=_transport(calls)) == EXPORT
    assert sorted(calls) == sorted(f"https://raw.githubusercontent.com{REPO}/{path}" for path in (
        "data/mods_by_base.json", "data/mods.json", "data/base_items.json", "version.txt"))


def test_fetch_exchange_reads_what_the_currency_exchange_trades_at_the_commit():
    # Every row counts: Omen of Corruption's isn't enabled in challenge leagues, but it is in Standard, so
    # the omen is in the game. Orb of Scouring has a BaseItemTypes row but no exchange row.
    calls: list[str] = []
    assert fetch_exchange(EXCHANGE_COMMIT, transport=_transport(calls)) == {
        CURRENCY + "CurrencyRerollRare", CURRENCY + "OmenOnChaosPrefix", CURRENCY + "OmenOnVaalRemoveDoNothingOutcome"}
    assert sorted(calls) == sorted(f"https://raw.githubusercontent.com{TABLES}/{name}"
                                   for name in ("CurrencyExchange.csv", "BaseItemTypes.csv"))


def test_fetch_exchange_refuses_a_row_it_cant_resolve():
    # An exchange row naming an item BaseItemTypes doesn't have: the export changed shape.
    served = {f"{TABLES}/CurrencyExchange.csv": EXCHANGE_CSV + '400,9999,0,0,1,1,10,"",1\n',
              f"{TABLES}/BaseItemTypes.csv": BASE_ITEM_TYPES_CSV}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=served[request.url.path]))
    with pytest.raises(ValueError, match="9999"):
        fetch_exchange(EXCHANGE_COMMIT, transport=transport)


@pytest.mark.parametrize("fetch", [fetch_export, fetch_exchange])
@pytest.mark.parametrize("ref", ["master", "develop", "v4.5.5", "abc12", ""])
def test_each_fetch_takes_a_pinned_commit_only(fetch, ref):
    # A branch or tag can move under you; the snapshot has to say exactly which export it came from.
    with pytest.raises(ValueError, match="commit"):
        fetch(ref, transport=_transport([]))


@pytest.mark.parametrize("fetch", [fetch_export, fetch_exchange])
def test_each_fetch_raises_on_an_http_error(fetch):
    with pytest.raises(RuntimeError, match="HTTP 404"):
        fetch(COMMIT, transport=_transport([], status=404))


def _fake_fetches(monkeypatch):
    # Each fetch answers only its own commit, so swapped arguments fail.
    monkeypatch.setattr(gamedata, "fetch_export", {COMMIT: EXPORT}.__getitem__)
    monkeypatch.setattr(gamedata, "fetch_exchange", {EXCHANGE_COMMIT: TRADED}.__getitem__)


def test_main_writes_the_snapshot_as_utf8_with_lf_naming_its_sources(monkeypatch, tmp_path):
    # Written by main itself, not a shell redirect: PowerShell 5.1's `>` writes UTF-16.
    _fake_fetches(monkeypatch)
    out = tmp_path / "items_0_5_5.json"
    main(["items", COMMIT, EXCHANGE_COMMIT, "0.5.5", str(out)])
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw
    snapshot = json.loads(raw.decode("utf-8"))
    assert snapshot["patch"] == "0.5.5"
    assert snapshot["source"].startswith(
        f"repoe-fork/poe2@{COMMIT} (game 4.5.5.2), repoe-fork/dat-export@{EXCHANGE_COMMIT} ")
    assert "Rusted Greathelm" in snapshot["bases"] and "Chaos Orb" in snapshot["texts"]


@pytest.mark.parametrize("argv", [
    [],
    ["items", COMMIT, "0.5.5", "out.json"],  # the old form, before the exchange commit
    ["trees", COMMIT, EXCHANGE_COMMIT, "0.5.5", "out.json"],
])
def test_main_requires_its_arguments(argv):
    with pytest.raises(SystemExit):
        main(argv)


@pytest.mark.parametrize("patch", ["latest", "0.5", "5"])
def test_main_rejects_a_patch_that_isnt_a_version(monkeypatch, tmp_path, patch):
    # Snapshots are per patch ("0.5.5", or a hotfix like "0.5.5e"); the tool picks the newest by it.
    _fake_fetches(monkeypatch)
    with pytest.raises(SystemExit):
        main(["items", COMMIT, EXCHANGE_COMMIT, patch, str(tmp_path / "out.json")])


SNAPSHOT = {**build_items(MODS_BY_BASE, MODS, BASE_ITEMS), "patch": "0.5.5", "source": "fixture"}
WHELPLING = {"name": "of the Whelpling", "itemLevel": 1, "text": "+(6-10)% to Fire Resistance"}
TZTEOSH = {"name": "of Tzteosh", "itemLevel": 82, "text": "+(41-45)% to Fire Resistance"}


def test_mod_tiers_lists_the_matching_families_of_a_base_with_every_tier():
    # The base name matches in any case; search matches part of a tier's text.
    assert mod_tiers(SNAPSHOT, "rusted greathelm", search="fire") == {
        "base": "Rusted Greathelm",
        "patch": "0.5.5",
        "variants": [{
            "class": "Helmets",
            "requirements": {"level": 1, "str": 0, "dex": 0, "int": 0},
            "families": [{"family": "FireResistance", "side": "suffix", "tiers": [WHELPLING, TZTEOSH]}],
        }],
    }


def test_mod_tiers_search_matches_a_family_name_too():
    # "fireresistance" isn't in any tier's text ("Fire Resistance" has a space) -- only the family's name.
    families = mod_tiers(SNAPSHOT, "Rusted Greathelm", search="fireresistance")["variants"][0]["families"]
    assert [f["family"] for f in families] == ["FireResistance"]


def test_mod_tiers_without_search_lists_every_family_prefixes_first():
    families = mod_tiers(SNAPSHOT, "Rusted Greathelm")["variants"][0]["families"]
    assert [(f["side"], f["family"]) for f in families] == [("prefix", "IncreasedLife"), ("suffix", "FireResistance")]


def test_mod_tiers_says_which_tiers_can_roll_at_an_item_level():
    tiers = mod_tiers(SNAPSHOT, "Rusted Greathelm", search="fire", item_level=45)["variants"][0]["families"][0]["tiers"]
    assert tiers == [{**WHELPLING, "canRoll": True}, {**TZTEOSH, "canRoll": False}]


def test_mod_tiers_says_when_no_family_on_the_base_matches():
    # The answer to "can this roll here at all?" when it can't: the base is found, no family matches.
    out = mod_tiers(SNAPSHOT, "Rusted Greathelm", search="minion")
    assert out["base"] == "Rusted Greathelm" and out["variants"][0]["families"] == []


def test_mod_tiers_gives_each_variant_of_a_shared_name():
    variants = mod_tiers(SNAPSHOT, "Ascetic Garb")["variants"]
    assert [v["requirements"]["level"] for v in variants] == [45, 51]
    assert [[f["family"] for f in v["families"]] for v in variants] == [["FireResistance"], ["IncreasedLife"]]


def test_mod_tiers_suggests_close_names_for_an_unknown_base():
    assert mod_tiers(SNAPSHOT, "greathelm") == {
        "base": None, "patch": "0.5.5", "variants": [], "suggestions": ["Rusted Greathelm", "Soldier Greathelm"]}


def test_mod_tiers_suggests_names_sharing_words_when_none_contains_the_name():
    # An old or mistyped full name ("Expert Hunter Hood" isn't a 0.5.5 base) contains no base name, so
    # suggest by shared whole words: most shared first, then fewer words (closer), then by name. Real
    # 0.5.5 names; "Hooded" isn't the word "Hood".
    names = ["Covert Hood", "Hooded Mask", "Hunter Hood", "Lace Hood", "Runeforged Hunter Hood",
             "Runemastered Hunter Hood"]
    snapshot = {"patch": "0.5.5", "bases": {name: [] for name in names}, "groups": [], "mods": {}}
    assert mod_tiers(snapshot, "Expert HUNTER hood")["suggestions"] == [
        "Hunter Hood", "Runeforged Hunter Hood", "Runemastered Hunter Hood", "Covert Hood", "Lace Hood"]


def test_mod_tiers_suggests_nothing_when_no_name_shares_a_word():
    assert mod_tiers(SNAPSHOT, "Mirror of Kalandra")["suggestions"] == []


@pytest.mark.parametrize("level", [0, -1])
def test_mod_tiers_rejects_an_item_level_below_1(level):
    with pytest.raises(ValueError, match="item_level"):
        mod_tiers(SNAPSHOT, "Rusted Greathelm", item_level=level)


# Rows of the committed snapshot's texts (game 4.5.5.2).
OMEN_USE = "Right click this item in your inventory to set it to be active. This item is consumed when triggered."
TEXTS = {
    "Chaos Orb": {
        "class": "StackableCurrency",
        "text": "Removes a random modifier and augments a Rare item with a new random modifier",
        "use": "Right click this item then left click a rare item to apply it."},
    "Diluted Liquid Ire": {
        "class": "StackableCurrency",
        "text": "Removes a random modifer and Augments a Rare Basic Jewel with a\nnew guaranteed Crafted modifier",
        "use": "Can be used at The Withered Willow to Instil Amulets with a Notable Passive Skill.\n"
               "Right click this item then left click a Rare Jewel to apply it."},
    "Omen of Sinistral Annulment": {
        "class": "Omen",
        "text": "While this item is active in your inventory your next\n"
                "Orb of Annulment will remove only prefix modifiers",
        "use": OMEN_USE},
    "Omen of Sinistral Erasure": {
        "class": "Omen",
        "text": "While this item is active in your inventory your next\nChaos Orb will remove only prefix modifiers",
        "use": OMEN_USE},
    "Orb of Annulment": {
        "class": "StackableCurrency",
        "text": "Removes a random modifier from an item",
        "use": "Right click this item then left click on a magic or rare item to apply it."},
    "Orb of Transmutation": {
        "class": "StackableCurrency",
        "text": "Upgrades a Normal item to a Magic item with 1 modifier",
        "use": "Right click this item then left click a normal item to apply it."},
    "Transmutation Shard": {
        "class": "StackableCurrency", "text": "", "use": "A stack of 10 shards becomes an Orb of Transmutation"},
}
TEXT_SNAPSHOT = {"patch": "0.5.5", "texts": TEXTS}


def _names(out):
    return [match["name"] for match in out["matches"]]


def test_item_text_finds_an_item_and_what_mentions_it_exact_name_first():
    # Any case. The omen's text names the orb; the orb comes first, though it sorts after the omen.
    assert item_text(TEXT_SNAPSHOT, "orb of ANNULMENT") == {
        "patch": "0.5.5",
        "total": 2,
        "matches": [{"name": "Orb of Annulment", **TEXTS["Orb of Annulment"]},
                    {"name": "Omen of Sinistral Annulment", **TEXTS["Omen of Sinistral Annulment"]}],
    }


def test_item_text_reads_line_breaks_as_spaces():
    # The game breaks "your next\nChaos Orb" for display; a search shouldn't depend on where.
    assert _names(item_text(TEXT_SNAPSHOT, "next chaos orb")) == ["Omen of Sinistral Erasure"]


def test_item_text_searches_the_directions_too():
    # Some facts live only there: where an item is used, and what shards add up to.
    assert _names(item_text(TEXT_SNAPSHOT, "instil")) == ["Diluted Liquid Ire"]
    assert _names(item_text(TEXT_SNAPSHOT, "Orb of Transmutation")) == ["Orb of Transmutation", "Transmutation Shard"]


def test_item_text_stops_at_20_matches_and_counts_them_all():
    texts = {f"Orb {i:02}": {"class": "StackableCurrency", "text": "", "use": ""} for i in range(25)}
    out = item_text({"patch": "0.5.5", "texts": texts}, "orb")
    assert out["total"] == 25 and _names(out) == [f"Orb {i:02}" for i in range(20)]


def test_item_text_suggests_names_sharing_words_when_nothing_matches():
    # Orb of Scouring is a PoE1 leftover the exchange doesn't trade. As in mod_tiers: most shared words
    # first, then fewer words -- so names sharing only "of" come last, but they do come.
    assert item_text(TEXT_SNAPSHOT, "Orb of Scouring") == {
        "patch": "0.5.5",
        "total": 0,
        "matches": [],
        "suggestions": ["Orb of Annulment", "Orb of Transmutation", "Chaos Orb", "Omen of Sinistral Annulment",
                        "Omen of Sinistral Erasure"],
    }


@pytest.mark.parametrize("search", ["", "   "])
def test_item_text_rejects_a_blank_search(search):
    # It would match every item.
    with pytest.raises(ValueError, match="search"):
        item_text(TEXT_SNAPSHOT, search)


def test_newest_snapshot_picks_the_highest_patch():
    # By patch, not text: 0.5.10 is after 0.5.5, and a hotfix letter after its base patch.
    names = ["items_0_5_5.json", "items_0_5_5e.json", "items_0_5_10.json", "tree_0_5.json", "items_notes.json"]
    assert newest_snapshot(names) == "items_0_5_10.json"
    assert newest_snapshot(["items_0_5_5.json", "items_0_5_5e.json"]) == "items_0_5_5e.json"
    assert newest_snapshot(["tree_0_5.json"]) is None


def test_load_items_reads_the_committed_snapshot_once():
    items = load_items()
    assert items["patch"] == "0.5.5" and "Rusted Greathelm" in items["bases"]
    assert "Chaos Orb" in items["texts"] and "Orb of Scouring" not in items["texts"]  # a PoE1 leftover
    assert load_items() is items
