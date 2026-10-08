"""Unit tests for finding the in-game Build Planner's folder and writing plans into it (no network; temp
folders only).

The game reads plans from <Documents>\\My Games\\Path of Exile 2\\BuildPlanner and watches it while it runs.
On Windows, Documents is wherever its known folder points -- OneDrive moves it, e.g. to
C:\\Users\\<name>\\OneDrive\\Documents. The game makes "Path of Exile 2" on first launch; BuildPlanner may
not exist yet, and finding the folder never makes it -- writing does.
"""
import codecs
import json
import sys
from pathlib import Path

import pytest

from poe2_mcp import plannerfolder
from poe2_mcp.plannerfolder import accept_folder, documents_folders, find_planner_folder, write_plans

GAME = Path("My Games") / "Path of Exile 2"


def _profile(monkeypatch, tmp_path: Path, known: Path | None = None) -> Path:
    """USERPROFILE and the home directory at tmp_path/me, and the known-folder call answering `known`."""
    me = tmp_path / "me"
    monkeypatch.setenv("HOME", str(me))
    monkeypatch.setenv("USERPROFILE", str(me))
    monkeypatch.setattr(plannerfolder, "known_documents_folder", lambda: known)
    return me


def _game(documents: Path) -> Path:
    """Make the "Path of Exile 2" folder under documents, as the game's first launch does."""
    folder = documents / GAME
    folder.mkdir(parents=True)
    return folder


def test_the_known_folder_comes_first_then_the_profile_guesses(monkeypatch, tmp_path):
    known = tmp_path / "D" / "Docs"
    me = _profile(monkeypatch, tmp_path, known)
    assert documents_folders() == [known, me / "Documents", me / "OneDrive" / "Documents"]


def test_a_folder_found_twice_is_listed_once(monkeypatch, tmp_path):
    # OneDrive's redirect is the usual case: the known folder is the profile's OneDrive\Documents.
    me = tmp_path / "me"
    _profile(monkeypatch, tmp_path, me / "OneDrive" / "Documents")
    assert documents_folders() == [me / "OneDrive" / "Documents", me / "Documents"]


def test_with_no_known_folder_or_profile_it_guesses_home_documents(monkeypatch, tmp_path):
    # Off Windows the known-folder call has nothing to answer, and there's no USERPROFILE.
    _profile(monkeypatch, tmp_path)
    monkeypatch.delenv("USERPROFILE")
    assert documents_folders() == [Path.home() / "Documents"]


@pytest.mark.skipif(sys.platform != "win32", reason="the known-folder call is Windows' own")
def test_the_known_folder_call_finds_documents_on_windows():
    folder = plannerfolder.known_documents_folder()
    assert folder is not None and folder.is_dir()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has a known folder to ask for")
def test_off_windows_there_is_no_known_folder():
    assert plannerfolder.known_documents_folder() is None


def test_the_planner_folder_is_in_the_first_documents_with_the_game_folder(tmp_path):
    (tmp_path / "a").mkdir()
    _game(tmp_path / "b")
    _game(tmp_path / "c")
    documents = [tmp_path / "a", tmp_path / "b", tmp_path / "c"]
    assert find_planner_folder(None, documents) == tmp_path / "b" / GAME / "BuildPlanner"


def test_finding_the_folder_never_makes_it(tmp_path):
    game = _game(tmp_path / "Documents")
    find_planner_folder(None, [tmp_path / "Documents"])
    assert not (game / "BuildPlanner").exists()


def test_with_no_game_folder_anywhere_nothing_is_found(tmp_path):
    (tmp_path / "Documents" / "My Games" / "Path of Exile").mkdir(parents=True)  # PoE1's, not this game's
    assert find_planner_folder(None, [tmp_path / "Documents", tmp_path / "missing"]) is None


def test_a_saved_folder_wins_while_its_game_folder_is_still_there(tmp_path):
    saved = _game(tmp_path / "elsewhere") / "BuildPlanner"
    _game(tmp_path / "Documents")
    assert find_planner_folder(str(saved), [tmp_path / "Documents"]) == saved


def test_a_saved_folder_that_is_gone_falls_back_to_the_search(tmp_path):
    game = _game(tmp_path / "Documents")
    saved = tmp_path / "gone" / GAME / "BuildPlanner"
    assert find_planner_folder(str(saved), [tmp_path / "Documents"]) == game / "BuildPlanner"


def test_the_players_game_folder_is_accepted_as_its_planner_folder(tmp_path):
    game = _game(tmp_path / "Documents")
    assert accept_folder(str(game)) == game / "BuildPlanner"
    assert not (game / "BuildPlanner").exists()


def test_the_planner_folder_itself_is_accepted_whether_or_not_it_exists_yet(tmp_path):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    assert accept_folder(str(planner)) == planner
    planner.mkdir()
    assert accept_folder(str(planner)) == planner


def test_a_pasted_path_may_carry_quotes_and_spaces(tmp_path):
    # Explorer's "Copy as path" wraps the path in double quotes.
    game = _game(tmp_path / "Documents")
    assert accept_folder(f'  "{game}" ') == game / "BuildPlanner"


def test_folder_names_match_in_any_case(tmp_path):
    # Windows folder names ignore case, and players type them by hand.
    game = tmp_path / "my games" / "path of exile 2"
    game.mkdir(parents=True)
    assert accept_folder(str(game)) == game / "BuildPlanner"
    assert accept_folder(str(game / "buildplanner")) == game / "buildplanner"


@pytest.mark.parametrize("where", ["Documents", "Documents/My Games", "Documents/My Games/Path of Exile 2/Old"])
def test_any_other_folder_is_refused_and_nothing_is_made(tmp_path, where):
    _game(tmp_path / "Documents")
    folder = tmp_path / where
    folder.mkdir(parents=True, exist_ok=True)
    before = sorted(tmp_path.rglob("*"))
    with pytest.raises(ValueError, match="Path of Exile 2"):
        accept_folder(str(folder))
    assert sorted(tmp_path.rglob("*")) == before


def test_a_game_folder_that_is_not_there_is_refused(tmp_path):
    game = tmp_path / GAME
    for path in (game, game / "BuildPlanner"):
        with pytest.raises(ValueError, match="Path of Exile 2"):
            accept_folder(str(path))


def test_a_relative_path_is_refused_even_when_it_resolves(monkeypatch, tmp_path):
    # It would be saved and used from wherever the server happens to run.
    _game(tmp_path)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="Path of Exile 2"):
        accept_folder(str(GAME))


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_each_plan_is_written_to_a_build_file_named_for_it(tmp_path):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    plans = [{"name": "Minion Leveling - Act 1", "passives": ["cold34"]}, {"name": "Minion Leveling - Act 2"}]
    assert write_plans(planner, plans) == {"written": True, "existing": [], "plans": [
        {"name": "Minion Leveling - Act 1", "file": "Minion Leveling - Act 1.build"},
        {"name": "Minion Leveling - Act 2", "file": "Minion Leveling - Act 2.build"},
    ]}
    assert [_read(planner / f"{plan['name']}.build") for plan in plans] == plans
    assert sorted(p.name for p in planner.iterdir()) == ["Minion Leveling - Act 1.build",
                                                         "Minion Leveling - Act 2.build"]


def test_the_planner_folder_is_made_but_never_the_game_folder(tmp_path):
    with pytest.raises(FileNotFoundError):
        write_plans(tmp_path / "Documents" / GAME / "BuildPlanner", [{"name": "Act 1"}])
    assert not (tmp_path / "Documents").exists()


def test_files_are_utf8_json_with_unix_newlines_and_no_bom(tmp_path):
    # Notes are multi-line; a file written the Windows way would carry \r\n or a byte-order mark.
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    plan = {"name": "Act 2", "description": "Stage 3 of 9 – Act 2", "passives": [
        {"id": "cold34", "additional_text": "<b>{Priority:}\nfirst"}]}
    write_plans(planner, [plan])
    raw = (planner / "Act 2.build").read_bytes()
    assert b"\r" not in raw and not raw.startswith(codecs.BOM_UTF8)
    assert json.loads(raw.decode("utf-8")) == plan


@pytest.mark.parametrize("name, file", [
    ("Act 3: Vaal Guards", "Act 3- Vaal Guards.build"),
    ('Boss? "Yes"/No | <Maybe>*', "Boss- -Yes--No - -Maybe--.build"),
    ("Tab\there", "Tab-here.build"),
    ("Endgame. . .", "Endgame.build"),  # Windows drops trailing dots and spaces; the name reported must match
])
def test_a_file_name_swaps_what_windows_refuses_for_a_dash_but_the_plan_keeps_its_name(tmp_path, name, file):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    assert write_plans(planner, [{"name": name}])["plans"] == [{"name": name, "file": file}]
    assert _read(planner / file) == {"name": name}


def test_a_repeated_name_gets_a_number_in_the_plan_and_its_file(tmp_path):
    # A PoB can repeat a spec title, or hold several untitled specs; the dropdown has to tell them apart.
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    plans = [{"name": "Guide - Maps"}, {"name": "Guide - Act 1"}, {"name": "Guide - Maps"}, {"name": "Guide - Maps"}]
    assert write_plans(planner, plans)["plans"] == [
        {"name": "Guide - Maps", "file": "Guide - Maps.build"},
        {"name": "Guide - Act 1", "file": "Guide - Act 1.build"},
        {"name": "Guide - Maps (2)", "file": "Guide - Maps (2).build"},
        {"name": "Guide - Maps (3)", "file": "Guide - Maps (3).build"},
    ]
    assert _read(planner / "Guide - Maps (2).build") == {"name": "Guide - Maps (2)"}
    assert plans[2] == {"name": "Guide - Maps"}  # the caller's plans are left as they were


def test_names_repeat_as_the_file_system_sees_them_in_any_case_and_after_cleaning(tmp_path):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    plans = [{"name": "Guide - Maps"}, {"name": "guide - maps"}, {"name": "A: B"}, {"name": "A/ B"}]
    assert write_plans(planner, plans)["plans"] == [
        {"name": "Guide - Maps", "file": "Guide - Maps.build"},
        {"name": "guide - maps (2)", "file": "guide - maps (2).build"},
        {"name": "A: B", "file": "A- B.build"},
        {"name": "A/ B (2)", "file": "A- B (2).build"},
    ]


def test_nothing_is_written_while_any_file_is_already_there(tmp_path):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    planner.mkdir()
    (planner / "Guide - Act 2.build").write_text("old", encoding="utf-8")
    out = write_plans(planner, [{"name": "Guide - Act 1"}, {"name": "Guide - Act 2"}])
    assert (out["written"], out["existing"]) == (False, ["Guide - Act 2.build"])
    assert [p["file"] for p in out["plans"]] == ["Guide - Act 1.build", "Guide - Act 2.build"]
    assert [p.name for p in planner.iterdir()] == ["Guide - Act 2.build"]
    assert (planner / "Guide - Act 2.build").read_text(encoding="utf-8") == "old"


def test_overwrite_replaces_the_files_already_there_and_leaves_the_rest_alone(tmp_path):
    planner = _game(tmp_path / "Documents") / "BuildPlanner"
    planner.mkdir()
    (planner / "Guide - Act 2.build").write_text("old", encoding="utf-8")
    (planner / "Another Build.build").write_text("theirs", encoding="utf-8")
    plans = [{"name": "Guide - Act 1"}, {"name": "Guide - Act 2", "passives": ["cold34"]}]
    out = write_plans(planner, plans, overwrite=True)
    assert (out["written"], out["existing"]) == (True, ["Guide - Act 2.build"])
    assert _read(planner / "Guide - Act 2.build") == plans[1]
    assert (planner / "Another Build.build").read_text(encoding="utf-8") == "theirs"
