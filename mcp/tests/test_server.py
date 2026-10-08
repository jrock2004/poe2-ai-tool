"""Tests for the server's tool functions, with fakes standing in for the poe2scout and trade2 clients
(pure, no network). The tools are thin glue; these pin how they behave when an upstream fails."""
import asyncio
import json
import math
import time
from datetime import date
from pathlib import Path

import pytest

from poe2_mcp import gamedata, server, store
from poe2_mcp._cache import Fetched


@pytest.fixture(autouse=True)
def _isolated_data_dir(monkeypatch, tmp_path):
    """Tools read the saved league; never let a test see the real per-user data dir."""
    monkeypatch.setenv("POE2_DATA_DIR", str(tmp_path))
    return tmp_path


def _entry(amount: float, currency: str) -> dict:
    """One trade2 fetch result, shaped like the real response (trimmed)."""
    return {
        "id": f"listing-{amount}-{currency}",
        "listing": {
            "price": {"type": "~price", "amount": amount, "currency": currency},
            "account": {"name": "seller", "online": {"league": "Forbidden Rites"}},
            "whisper": "@seller Hi, I would like to buy your Gale Stride",
        },
        "item": {"name": "Gale Stride", "baseType": "Leatherbound Boots", "rarity": "Rare", "ilvl": 70,
                 "explicitMods": ["+30% to Fire Resistance", "25% increased Movement Speed"]},
    }


class FakeTrade:
    """trade2 finding three listings, cheapest first: two priced in exalted, one in divine."""

    async def search(self, league: str, query: dict) -> Fetched:
        return Fetched(body={"id": "q123", "result": ["h1", "h2", "h3"], "total": 3}, fetched_at=time.time())

    async def fetch(self, query_id: str, hashes: list[str]) -> Fetched:
        entries = [_entry(40, "exalted"), _entry(55, "exalted"), _entry(1, "divine")]
        return Fetched(body=entries[:len(hashes)], fetched_at=time.time())


class FakeScout:
    """poe2scout. When `down`, the league comes back unchecked (as resolve_league's fallback gives it)
    and the price list can't be fetched."""

    def __init__(self, down: bool = False) -> None:
        self.down = down

    async def resolve_league(self, league: str | None = None, *, strict: bool = False) -> Fetched:
        body = {"Value": "Forbidden Rites", "Unchecked": True} if self.down else {"Value": "Forbidden Rites"}
        return Fetched(body=body, fetched_at=time.time())

    async def get_items(self, league_value: str) -> Fetched:
        if self.down:
            raise RuntimeError("poe2scout /poe2/Leagues/Forbidden%20Rites/Items -> HTTP 503 Service Unavailable")
        items = [{"ApiId": "exalted", "Text": "Exalted Orb", "CurrentPrice": 1},
                 {"ApiId": "divine", "Text": "Divine Orb", "CurrentPrice": 700}]
        return Fetched(body=items, fetched_at=time.time())


def _search(monkeypatch, scout: FakeScout) -> dict:
    monkeypatch.setattr(server, "_scout", scout)
    monkeypatch.setattr(server, "_trade", FakeTrade())
    return asyncio.run(server.search_trade({"query": {}}, limit=10))


def test_search_trade_converts_listing_prices_with_poe2scout_rates(monkeypatch):
    out = _search(monkeypatch, FakeScout())
    stats = out["priceStats"]
    assert out["shown"] == 3
    assert stats["converted"] == 3 and stats["unconvertedCurrencies"] == []
    assert stats["minExalted"] == 40 and stats["maxExalted"] == 700


def test_search_trade_keeps_its_listings_when_poe2scout_is_down(monkeypatch):
    # The listings come from trade2, so they survive; only the conversion to exalted needs poe2scout.
    # Exalted is the base unit -- 1 by definition -- so those listings still price.
    out = _search(monkeypatch, FakeScout(down=True))
    stats = out["priceStats"]
    assert out["url"] and out["matched"] == 3 and out["shown"] == 3
    assert stats["converted"] == 2 and stats["unconvertedCurrencies"] == ["divine"]
    assert stats["minExalted"] == 40 and stats["maxExalted"] == 55
    assert "poe2scout" in out["note"]


# poe2scout's live category list (Items/Categories), trimmed: unique categories, then currency ones.
CATEGORIES = {"UniqueCategories": [{"ApiId": "armour"}],
              "CurrencyCategories": [{"ApiId": c} for c in ("currency", "essences", "breach", "runes")]}


def _currency(name: str, api_id: str, price: float) -> dict:
    """One ByCategory item, trimmed to the fields the tool reads."""
    return {"Text": name, "ApiId": api_id, "CurrentPrice": price, "CurrentQuantity": 500, "PriceLogs": None}


# In poe2scout's order. Two to a page, so Greater Essence of Haste is on page 2.
ESSENCES = [_currency("Lesser Essence of Haste", "lesser-essence-of-haste", 1),
            _currency("Essence of Haste", "essence-of-haste", 4),
            _currency("Essence of the Body", "essence-of-the-body", 3),
            _currency("Greater Essence of Haste", "greater-essence-of-haste", 12)]
CURRENCY = [_currency("Divine Orb", "divine", 700), _currency("Gemcutter's Prism", "gcp", 2)]
PAGE_SIZE = 2  # poe2scout pages its answers (live: 82 essences come back as 3 pages of 40)


class PricesScout:
    """poe2scout for get_currency_prices: essences and currency are priced, a page at a time; every
    other category is empty. Records the calls, so a test can see whether the category list was
    fetched."""

    def __init__(self, categories_down: bool = False) -> None:
        self.categories_down = categories_down
        self.calls: list[str] = []

    async def resolve_league(self, league: str | None = None, *, strict: bool = False) -> Fetched:
        return Fetched(body={"Value": "Forbidden Rites", "DivinePrice": 700}, fetched_at=time.time())

    async def get_currencies_by_category(self, league_value, category, search=None, page=1, per_page=25) -> Fetched:
        self.calls.append(f"category {category}")
        pool = {"essences": ESSENCES, "currency": CURRENCY}.get(category, [])
        # As live: search is an exact, case-sensitive match on the name or the apiId, not a substring.
        matched = [i for i in pool if search is None or search in (i["Text"], i["ApiId"])]
        size = min(per_page, PAGE_SIZE)
        return Fetched(body={"Items": matched[(page - 1) * size:page * size], "Total": len(matched),
                             "CurrentPage": page, "Pages": math.ceil(len(matched) / size)},
                       fetched_at=time.time())

    async def get_categories(self, league_value: str) -> Fetched:
        self.calls.append("categories")
        if self.categories_down:
            raise RuntimeError("poe2scout /poe2/Leagues/Forbidden%20Rites/Items/Categories -> HTTP 503")
        return Fetched(body=CATEGORIES, fetched_at=time.time())


def _prices(monkeypatch, category: str, search: str | None = None, per_page: int = 25,
            **scout_kw) -> tuple[dict, PricesScout]:
    scout = PricesScout(**scout_kw)
    monkeypatch.setattr(server, "_scout", scout)
    return asyncio.run(server.get_currency_prices(category, search=search, per_page=per_page)), scout


def test_get_currency_prices_flags_a_category_poe2scout_does_not_have(monkeypatch):
    # 'catalysts' reads like a category, but poe2scout lists catalysts under 'breach'.
    out, _ = _prices(monkeypatch, "catalysts")
    assert out["items"] == [] and out["unknownCategory"] is True
    assert out["validCategories"] == ["currency", "essences", "breach", "runes"]


def test_get_currency_prices_empty_search_in_a_real_category_is_not_flagged(monkeypatch):
    out, _ = _prices(monkeypatch, "essences", search="mirror")
    assert out["items"] == [] and "unknownCategory" not in out


def test_get_currency_prices_checks_the_categories_only_when_nothing_came_back(monkeypatch):
    out, scout = _prices(monkeypatch, "essences", search="Greater Essence of Haste")
    assert [i["name"] for i in out["items"]] == ["Greater Essence of Haste"]
    assert "categories" not in scout.calls


def test_get_currency_prices_without_the_category_list_returns_the_plain_empty_result(monkeypatch):
    # The check is a nicety: if the list can't be fetched, answer as before rather than fail.
    out, _ = _prices(monkeypatch, "catalysts", categories_down=True)
    assert out["items"] == [] and "unknownCategory" not in out


# poe2scout's own search takes only an exact name or apiId (live: "Divine" and "haste" find nothing).
# The tool's search matches part of a name or apiId, in any case, across every page of the category.
def test_get_currency_prices_search_matches_part_of_a_name_in_any_case(monkeypatch):
    out, _ = _prices(monkeypatch, "essences", search="HASTE")
    assert [i["name"] for i in out["items"]] == [
        "Lesser Essence of Haste", "Essence of Haste", "Greater Essence of Haste"]  # the last from page 2


def test_get_currency_prices_search_finds_divine_from_a_partial_name(monkeypatch):
    # The currency glossary's own advice: normalize "div", then search "Divine".
    out, _ = _prices(monkeypatch, "currency", search="Divine")
    assert [i["name"] for i in out["items"]] == ["Divine Orb"]


def test_get_currency_prices_search_still_matches_an_api_id(monkeypatch):
    # Gemcutter's Prism's apiId is "gcp", which its name doesn't contain.
    out, _ = _prices(monkeypatch, "currency", search="gcp")
    assert [i["name"] for i in out["items"]] == ["Gemcutter's Prism"]


def test_get_currency_prices_search_returns_up_to_per_page_and_counts_every_match(monkeypatch):
    out, _ = _prices(monkeypatch, "essences", search="essence", per_page=2)
    assert len(out["items"]) == 2 and out["total"] == 4


# A loaded item snapshot, trimmed to one real row of its texts.
ITEM_SNAPSHOT = {"patch": "0.5.5", "texts": {"Orb of Annulment": {
    "class": "StackableCurrency", "text": "Removes a random modifier from an item",
    "use": "Right click this item then left click on a magic or rare item to apply it."}}}


def test_item_text_looks_the_search_up_in_the_installed_snapshot(monkeypatch):
    monkeypatch.setattr(server, "load_items", lambda: ITEM_SNAPSHOT)
    out = asyncio.run(server.item_text("orb of annulment"))
    assert out == gamedata.item_text(ITEM_SNAPSHOT, "orb of annulment") and out["total"] == 1


def test_item_text_says_when_no_snapshot_is_installed(monkeypatch):
    monkeypatch.setattr(server, "load_items", lambda: None)
    out = asyncio.run(server.item_text("orb of annulment"))
    assert out["valid"] is False and out["error"] == "no item snapshot is installed"


# A loaded snapshot, trimmed to one real entry of each trial's pool.
TRIAL_SNAPSHOT = {
    "patch": "0.5.5",
    "chaos": [{"name": "Time Paradox", "kind": "modifier", "versions": [
        {"name": "Time Paradox", "tier": 1,
         "text": "Buffs on you expire 50% faster and Debuffs on you expire 25% slower"}]}],
    "sekhemas": [{"name": "Iron Manacles", "category": "Minor Afflictions", "text": "You have no Evasion"}],
}


def test_trial_pool_looks_the_search_up_in_the_installed_snapshot(monkeypatch):
    monkeypatch.setattr(server, "load_items", lambda: TRIAL_SNAPSHOT)
    out = asyncio.run(server.trial_pool("sekhemas", "evasion"))
    assert out == gamedata.trial_pool(TRIAL_SNAPSHOT, "sekhemas", "evasion") and out["total"] == 1


def test_trial_pool_says_when_no_snapshot_is_installed(monkeypatch):
    monkeypatch.setattr(server, "load_items", lambda: None)
    out = asyncio.run(server.trial_pool("chaos"))
    assert out["valid"] is False and out["error"] == "no item snapshot is installed"


# write_build_plan: a guide's PoB with two loadouts, trimmed from a 0.5 Infernalist guide, and the item
# snapshot's passive ids for its nodes. Every note is a marker that must stay in the files, out of the reply.
PLAN_XML = """<PathOfBuilding2>
  <Tree>
    <Spec title="Act 2" treeVersion="0_5" ascendancyInternalId="Witch1" nodes="3823,99999">
      <Notes><Note nodeId="3823">NOTE-passive</Note></Notes>
    </Spec>
    <Spec title="Mid Maps" treeVersion="0_5" ascendancyInternalId="Witch1" nodes="3823,51184"/>
  </Tree>
  <Skills>
    <SkillSet title="Act 2">
      <Skill source="Item:1:Withered Wand">
        <Gem enabled="true" gemId="Metadata/Items/Gems/SkillGemChaosbolt" nameSpec="Chaos Bolt"
             skillId="WeaponGrantedChaosboltPlayer"/>
      </Skill>
    </SkillSet>
    <SkillSet title="Mid Maps">
      <Skill>
        <Gem enabled="true" gemId="Metadata/Items/Gem/SkillGemRagingSpirits" nameSpec="Raging Spirits"
             note="NOTE-skill"/>
      </Skill>
    </SkillSet>
  </Skills>
  <Items>
    <ItemSet title="Act 2"><Slot itemId="0" name="Flask 1" note="NOTE-flask"/></ItemSet>
    <ItemSet title="Mid Maps"><Slot itemId="0" name="Helmet" note="NOTE-helmet"/></ItemSet>
  </Items>
</PathOfBuilding2>"""
PLAN_SNAPSHOT = {"patch": "0.5.5", "passives": {"3823": "cold34", "51184": "witch_sorceress_notable1"},
                 "gems": {"Metadata/Items/Gem/SkillGemRagingSpirits": "Raging Spirits",
                          "Metadata/Items/Gems/SupportGemUnleash": "Unleash"}}


def _game(root: Path) -> Path:
    """A "Path of Exile 2" folder under root/My Games, as the game's first launch makes it."""
    game = root / "My Games" / "Path of Exile 2"
    game.mkdir(parents=True)
    return game


def _write_plan(monkeypatch, tmp_path, code=PLAN_XML, **kwargs) -> dict:
    """write_build_plan with the snapshot above, searching only tmp_path/Documents for the game folder."""
    monkeypatch.setattr(server, "load_items", lambda: PLAN_SNAPSHOT)
    monkeypatch.setattr(server, "documents_folders", lambda: [tmp_path / "Documents"])
    return asyncio.run(server.write_build_plan(code, "Minion Leveling", **kwargs))


LINK = "https://example.test/guide"


def _read_plan(planner: Path, name: str) -> dict:
    return json.loads((planner / f"{name}.build").read_text(encoding="utf-8"))


def _redate(planner: Path, name: str, day: str) -> None:
    """Make a written plan look written on another day -- as when the guide is written again later."""
    plan = _read_plan(planner, name)
    plan["description"] = plan["description"].replace(date.today().isoformat(), day)
    store.write_json(planner / f"{name}.build", plan)


def test_write_build_plan_writes_a_plan_per_loadout_into_the_game_folder(monkeypatch, tmp_path):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    out = _write_plan(monkeypatch, tmp_path, author="Guide Author", link="https://example.test/guide")
    assert (out["status"], out["folder"]) == ("written", str(planner))
    assert sorted(p.name for p in planner.iterdir()) == ["Minion Leveling - 1 Act 2.build",
                                                         "Minion Leveling - 2 Mid Maps.build"]
    assert json.loads((planner / "Minion Leveling - 1 Act 2.build").read_text(encoding="utf-8")) == {
        "name": "Minion Leveling - 1 Act 2", "author": "Guide Author", "link": "https://example.test/guide",
        "description": f"Stage 1 of 2. Written {date.today().isoformat()} from the guide's PoB.",
        "ascendancy": "Witch1", "passives": [{"id": "cold34", "additional_text": "NOTE-passive"}],
        "inventory_slots": [{"inventory_id": "Flask1", "slot_x": 0, "additional_text": "NOTE-flask"}]}


def test_write_build_plan_reports_each_plan_without_its_notes(monkeypatch, tmp_path):
    # The notes go to the files, never into the reply: the skill tells the player what's in each plan.
    _game(tmp_path / "Documents")
    out = _write_plan(monkeypatch, tmp_path)
    assert out["plans"] == [
        {"name": "Minion Leveling - 1 Act 2", "file": "Minion Leveling - 1 Act 2.build", "state": "new",
         "passives": 1, "skills": 0, "gear": 1,
         "leftOut": [{"what": "passive node 99999", "why": "unmapped-passive"},
                     {"what": "Chaos Bolt", "why": "item-granted"}]},
        {"name": "Minion Leveling - 2 Mid Maps", "file": "Minion Leveling - 2 Mid Maps.build", "state": "new",
         "passives": 2, "skills": 1, "gear": 1, "leftOut": []},
    ]
    assert (out["gone"], out["unpaired"]) == ([], {"skillSets": [], "itemSets": []})
    assert "warning" not in out and "NOTE-" not in json.dumps(out)


def test_write_build_plan_gives_a_single_loadout_no_stage(monkeypatch, tmp_path):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    one = PLAN_XML.replace('<Spec title="Mid Maps" treeVersion="0_5" ascendancyInternalId="Witch1" '
                           'nodes="3823,51184"/>', "")
    out = _write_plan(monkeypatch, tmp_path, code=one)
    assert [p["name"] for p in out["plans"]] == ["Minion Leveling - Act 2"]  # no number, nothing to order
    plan = json.loads((planner / "Minion Leveling - Act 2.build").read_text(encoding="utf-8"))
    assert plan["description"] == f"Written {date.today().isoformat()} from the guide's PoB."
    assert not {"author", "link"} & set(plan)  # never invented when not given
    assert out["unpaired"] == {"skillSets": ["Mid Maps"], "itemSets": ["Mid Maps"]}


def test_write_build_plan_numbers_the_stages_so_the_dropdown_keeps_the_guides_order(monkeypatch, tmp_path):
    # In game the dropdown sorts plans by name and cuts each at about 30 characters, so the stage number
    # comes right after the build's name, padded so that 10 follows 9.
    _game(tmp_path / "Documents")
    specs = "".join(f'<Spec title="Stage {i}" treeVersion="0_5" nodes="3823"/>' for i in range(1, 11))
    out = _write_plan(monkeypatch, tmp_path, code=f"<PathOfBuilding2><Tree>{specs}</Tree></PathOfBuilding2>")
    names = [p["name"] for p in out["plans"]]
    assert names == [f"Minion Leveling - {i:02d} Stage {i}" for i in range(1, 11)]
    assert names == sorted(names)


def test_write_build_plan_names_an_untitled_stage_by_its_number(monkeypatch, tmp_path):
    _game(tmp_path / "Documents")
    out = _write_plan(monkeypatch, tmp_path, code=PLAN_XML.replace('<Spec title="Mid Maps" ', "<Spec "))
    assert [p["name"] for p in out["plans"]] == ["Minion Leveling - 1 Act 2", "Minion Leveling - 2"]


def test_write_build_plan_never_overwrites_a_file_that_is_not_this_guides_until_told_to(monkeypatch, tmp_path):
    # Here a file the planner can't even read: it isn't this guide's plan, so it's the player's call.
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    planner.mkdir()
    (planner / "Minion Leveling - 2 Mid Maps.build").write_text("old", encoding="utf-8")
    out = _write_plan(monkeypatch, tmp_path, link=LINK)
    assert out == {"status": "exists", "folder": str(planner), "existing": ["Minion Leveling - 2 Mid Maps.build"]}
    assert [p.name for p in planner.iterdir()] == ["Minion Leveling - 2 Mid Maps.build"]
    out = _write_plan(monkeypatch, tmp_path, link=LINK, overwrite=True)
    assert (out["status"], [p["state"] for p in out["plans"]]) == ("written", ["new", "new"])
    assert _read_plan(planner, "Minion Leveling - 2 Mid Maps")["link"] == LINK


def test_write_build_plan_asks_before_touching_another_guides_plans(monkeypatch, tmp_path):
    # Same build name, another link (or none): not provably this guide's plans.
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    _write_plan(monkeypatch, tmp_path, link="https://example.test/other")
    out = _write_plan(monkeypatch, tmp_path, link=LINK)
    assert out == {"status": "exists", "folder": str(planner),
                   "existing": ["Minion Leveling - 1 Act 2.build", "Minion Leveling - 2 Mid Maps.build"]}
    assert _write_plan(monkeypatch, tmp_path, link=LINK, overwrite=True)["status"] == "written"
    assert _read_plan(planner, "Minion Leveling - 1 Act 2")["link"] == LINK


def test_write_build_plan_updates_the_same_guides_plans_without_asking(monkeypatch, tmp_path):
    # Only what the guide changed is written: an unchanged plan keeps its file, and the day it was written.
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    _write_plan(monkeypatch, tmp_path, link=LINK)
    _redate(planner, "Minion Leveling - 1 Act 2", "2026-01-01")
    out = _write_plan(monkeypatch, tmp_path, link=LINK, code=PLAN_XML.replace('nodes="3823,51184"', 'nodes="3823"'))
    assert out["status"] == "written"
    assert [(p["name"], p["state"]) for p in out["plans"]] == [("Minion Leveling - 1 Act 2", "unchanged"),
                                                               ("Minion Leveling - 2 Mid Maps", "changed")]
    assert "2026-01-01" in _read_plan(planner, "Minion Leveling - 1 Act 2")["description"]
    assert _read_plan(planner, "Minion Leveling - 2 Mid Maps")["passives"] == ["cold34"]


def test_write_build_plan_says_when_the_plans_are_already_up_to_date(monkeypatch, tmp_path):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    _write_plan(monkeypatch, tmp_path, link=LINK)
    _redate(planner, "Minion Leveling - 2 Mid Maps", "2026-01-01")
    out = _write_plan(monkeypatch, tmp_path, link=LINK)
    assert (out["status"], [p["state"] for p in out["plans"]], out["gone"]) == ("unchanged", ["unchanged"] * 2, [])
    assert "2026-01-01" in _read_plan(planner, "Minion Leveling - 2 Mid Maps")["description"]


def test_write_build_plan_lists_the_stages_the_guide_no_longer_has_and_leaves_them(monkeypatch, tmp_path):
    # Removing them is the player's yes, through remove_build_plans.
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    _write_plan(monkeypatch, tmp_path, link=LINK)
    out = _write_plan(monkeypatch, tmp_path, link=LINK, code=PLAN_XML.replace('title="Mid Maps"', 'title="Endgame"'))
    assert [(p["name"], p["state"]) for p in out["plans"]] == [("Minion Leveling - 1 Act 2", "unchanged"),
                                                               ("Minion Leveling - 2 Endgame", "new")]
    assert out["gone"] == ["Minion Leveling - 2 Mid Maps.build"]
    assert (planner / "Minion Leveling - 2 Mid Maps.build").is_file()


def test_remove_build_plans_removes_the_plans_named_from_the_planner_folder(monkeypatch, tmp_path):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    _write_plan(monkeypatch, tmp_path, link=LINK)
    out = asyncio.run(server.remove_build_plans(["Minion Leveling - 2 Mid Maps.build"]))
    assert out == {"status": "removed", "folder": str(planner), "removed": ["Minion Leveling - 2 Mid Maps.build"]}
    assert [p.name for p in planner.iterdir()] == ["Minion Leveling - 1 Act 2.build"]


def test_remove_build_plans_refuses_a_name_that_is_not_a_plan_file(monkeypatch, tmp_path):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    _write_plan(monkeypatch, tmp_path, link=LINK)
    out = asyncio.run(server.remove_build_plans(["Minion Leveling - 1 Act 2.build", "../config.json"]))
    assert out["status"] == "invalid" and "../config.json" in out["error"]
    assert len(list(planner.iterdir())) == 2


def test_remove_build_plans_asks_for_the_folder_when_it_finds_none(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "documents_folders", lambda: [tmp_path / "Documents"])
    out = asyncio.run(server.remove_build_plans(["Minion Leveling - 1 Act 2.build"]))
    assert out == {"status": "no-folder", "checked": [str(tmp_path / "Documents" / "My Games" / "Path of Exile 2")]}


def test_write_build_plan_asks_for_the_folder_when_it_finds_none(monkeypatch, tmp_path):
    store.write_config(tmp_path, {"buildPlannerFolder": str(tmp_path / "Gone" / "Path of Exile 2" / "BuildPlanner")})
    out = _write_plan(monkeypatch, tmp_path)
    assert out == {"status": "no-folder", "checked": [str(tmp_path / "Gone" / "Path of Exile 2"),
                                                       str(tmp_path / "Documents" / "My Games" / "Path of Exile 2")]}


def test_write_build_plan_saves_a_folder_the_player_names_and_uses_it_from_then_on(monkeypatch, tmp_path):
    # A named folder wins over a found one, and is kept in config.json beside the league.
    _game(tmp_path / "Documents")
    game = _game(tmp_path / "Elsewhere")
    store.write_config(tmp_path, {"league": "Runes of Aldur"})
    out = _write_plan(monkeypatch, tmp_path, folder=f'"{game}"')
    assert (out["status"], out["folder"]) == ("written", str(game / "BuildPlanner"))
    assert store.read_config(tmp_path) == {"league": "Runes of Aldur", "buildPlannerFolder": str(game / "BuildPlanner")}
    assert _write_plan(monkeypatch, tmp_path)["folder"] == str(game / "BuildPlanner")


def test_write_build_plan_refuses_a_folder_the_game_would_not_read(monkeypatch, tmp_path):
    (tmp_path / "Documents").mkdir()
    out = _write_plan(monkeypatch, tmp_path, folder=str(tmp_path / "Documents"))
    assert out["status"] == "no-folder" and "Path of Exile 2" in out["error"]
    assert store.read_config(tmp_path) == {}


def test_write_build_plan_warns_when_the_guides_tree_is_older_than_the_passive_ids(monkeypatch, tmp_path):
    # Node ids mostly carry over between trees, so the plan is still written; the skill passes the warning on.
    _game(tmp_path / "Documents")
    out = _write_plan(monkeypatch, tmp_path, code=PLAN_XML.replace('treeVersion="0_5"', 'treeVersion="0_4"'))
    assert out["status"] == "written" and "0.4" in out["warning"] and "0.5.5" in out["warning"]


@pytest.mark.parametrize("code, error", [
    ("not a code", "Not a valid Path of Building code"),
    ("<PathOfBuilding2/>", "no passive tree"),
])
def test_write_build_plan_says_when_the_code_has_nothing_to_plan(monkeypatch, tmp_path, code, error):
    game = _game(tmp_path / "Documents")
    out = _write_plan(monkeypatch, tmp_path, code=code)
    assert out["status"] == "invalid" and error in out["error"]
    assert not (game / "BuildPlanner").exists()


def test_write_build_plan_says_when_no_snapshot_is_installed(monkeypatch, tmp_path):
    _game(tmp_path / "Documents")
    monkeypatch.setattr(server, "documents_folders", lambda: [tmp_path / "Documents"])
    monkeypatch.setattr(server, "load_items", lambda: None)
    out = asyncio.run(server.write_build_plan(PLAN_XML, "Minion Leveling"))
    assert out == {"status": "invalid", "error": "no item snapshot is installed"}


def test_write_build_plan_says_what_changed_inside_each_changed_stage(monkeypatch, tmp_path):
    # Mid Maps drops a passive (the committed 0.5 tree names node 51184 Raw Power), gains a support, and its
    # skill's note changes; Act 2 is untouched and says nothing. Notes are counted, never quoted.
    _game(tmp_path / "Documents")
    _write_plan(monkeypatch, tmp_path, link=LINK)
    updated = (PLAN_XML.replace('nodes="3823,51184"', 'nodes="3823"')
               .replace('note="NOTE-skill"/>', 'note="NOTE-skill, reworded"/>\n        <Gem enabled="true" '
                        'gemId="Metadata/Items/Gems/SupportGemUnleash" nameSpec="Unleash"/>'))
    out = _write_plan(monkeypatch, tmp_path, link=LINK, code=updated)
    act2, mid_maps = out["plans"]
    assert "changes" not in act2
    assert mid_maps["changes"] == {
        "passives": {"added": [], "removed": ["Raw Power"], "otherAdded": 0, "otherRemoved": 0},
        "supports": {"added": [{"skill": "Raging Spirits", "support": "Unleash"}], "removed": []},
        "notes": 1,
    }
    assert "NOTE-" not in json.dumps(out)


def test_write_build_plan_counts_passives_it_cannot_name(monkeypatch, tmp_path):
    # No tree snapshot for the guide's tree version: nothing to name the passives by, so they're counted.
    _game(tmp_path / "Documents")
    old_tree = PLAN_XML.replace('treeVersion="0_5"', 'treeVersion="0_1"')
    _write_plan(monkeypatch, tmp_path, link=LINK, code=old_tree)
    out = _write_plan(monkeypatch, tmp_path, link=LINK, code=old_tree.replace('nodes="3823,51184"', 'nodes="3823"'))
    assert out["plans"][1]["changes"] == {"passives": {"added": [], "removed": [], "otherAdded": 0,
                                                       "otherRemoved": 1}}
