"""Find the folder the in-game Build Planner reads its plans from, and read, write and remove plans in it.
File system only -- no network.

The game reads <Documents>\\My Games\\Path of Exile 2\\BuildPlanner and watches it while it runs. On Windows,
Documents is wherever its known folder points -- OneDrive moves it, e.g. to C:\\Users\\<name>\\OneDrive\\Documents
-- so it's asked for (SHGetKnownFolderPath) before the usual places are guessed. The game makes "Path of
Exile 2" on first launch; BuildPlanner may not exist yet, and only writing makes it.
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from . import store

GAME_FOLDER = "Path of Exile 2"
PLANNER_FOLDER = "BuildPlanner"
_FOLDERID_DOCUMENTS = "FDD39AD0-238F-46AF-ADB4-6C85480369C7"
_NOT_IN_FILE_NAMES = re.compile(r'[<>:"/\\|?*\x00-\x1f]')  # what Windows refuses in a file name


def known_documents_folder() -> Path | None:
    """Windows' Documents known folder, wherever OneDrive or the player moved it; None off Windows, or if
    the call fails."""
    if sys.platform != "win32":
        return None
    import ctypes

    folder_id = ctypes.create_string_buffer(uuid.UUID(_FOLDERID_DOCUMENTS).bytes_le, 16)  # a GUID's layout
    path = ctypes.c_void_p()
    try:
        result = ctypes.WinDLL("shell32").SHGetKnownFolderPath(folder_id, 0, None, ctypes.byref(path))
        return Path(ctypes.wstring_at(path.value)) if result == 0 and path.value else None
    except OSError:
        return None
    finally:
        if path.value:
            ctypes.WinDLL("ole32").CoTaskMemFree(path)  # the caller frees it, whether the call worked or not


def documents_folders() -> list[Path]:
    """Where Documents may be, in order: the known folder, %USERPROFILE%\\Documents,
    %USERPROFILE%\\OneDrive\\Documents, then ~/Documents (on Windows the same as the second, so dropped;
    elsewhere the only one). Unset ones are skipped; a folder found twice is listed once."""
    found = [known_documents_folder()]
    profile = os.environ.get("USERPROFILE")
    if profile:
        found += [Path(profile) / "Documents", Path(profile) / "OneDrive" / "Documents"]
    try:
        found.append(Path.home() / "Documents")
    except RuntimeError:  # no home directory to be found
        pass
    folders: list[Path] = []
    for folder in found:
        if folder is not None and folder not in folders:
            folders.append(folder)
    return folders


def find_planner_folder(saved: str | None, documents: list[Path]) -> Path | None:
    """The saved planner folder while its game folder is still there; else the BuildPlanner folder in the
    first of `documents` that has My Games\\Path of Exile 2; else None. Never makes a folder."""
    if saved and Path(saved).parent.is_dir():
        return Path(saved)
    for folder in documents:
        game = folder / "My Games" / GAME_FOLDER
        if game.is_dir():
            return game / PLANNER_FOLDER
    return None


def accept_folder(path: str) -> Path:
    """The planner folder a player named: their "Path of Exile 2" folder, or the BuildPlanner folder in it
    (made or not). Spaces and the quotes Explorer's "Copy as path" adds are stripped; names match in any
    case. Anything else -- a relative path, another folder, a game folder that isn't there -- raises
    ValueError, so nothing is ever written somewhere the game won't read. Makes nothing."""
    given = Path(path.strip().strip('"').strip())
    planner = given if given.name.casefold() == PLANNER_FOLDER.casefold() else given / PLANNER_FOLDER
    game = planner.parent
    if not (given.is_absolute() and game.name.casefold() == GAME_FOLDER.casefold() and game.is_dir()):
        raise ValueError(
            f"{given} isn't a {GAME_FOLDER} folder. Pick Documents\\My Games\\{GAME_FOLDER}, or the "
            f"{PLANNER_FOLDER} folder inside it."
        )
    return planner


def write_plans(folder: Path, plans: list[dict[str, Any]], *, overwrite: bool = False) -> dict[str, Any]:
    """Write each plan (a Build Planner Build, from buildplanner.plan_build) to <its name>.build in folder.

    A file name swaps what Windows refuses for "-" and drops trailing dots and spaces; the plan keeps its
    name. Names repeat as the file system sees them -- in any case, after that cleaning -- and a repeat
    gets " (2)", " (3)", ... in both its name and its file; the caller's plans are left as they were.

    Never overwrites silently: if any file is already there, nothing is written unless `overwrite`.
    Files of other plans are left alone; nothing is deleted. Makes the BuildPlanner folder, never the
    game folder above it (FileNotFoundError when that's gone). UTF-8, "\\n", each file swapped in whole.

    Returns {"written", "existing": [file names already there], "plans": [{"name", "file"}]} with every
    plan, in order, whether or not it was written.
    """
    named: list[tuple[dict[str, Any], str]] = []
    taken: set[str] = set()
    for plan in plans:
        name, file, n = plan["name"], _file_name(plan["name"]), 1
        while file.casefold() in taken:
            n += 1
            name = f"{plan['name']} ({n})"
            file = _file_name(name)
        taken.add(file.casefold())
        named.append(({**plan, "name": name}, file))

    existing = [file for _, file in named if (folder / file).exists()]
    written = overwrite or not existing
    if written:
        folder.mkdir(exist_ok=True)  # no parents: a game folder that's gone is an error, not made here
        for plan, file in named:
            store.write_json(folder / file, plan)
    return {"written": written, "existing": existing,
            "plans": [{"name": plan["name"], "file": file} for plan, file in named]}


def _file_name(name: str) -> str:
    return _NOT_IN_FILE_NAMES.sub("-", name).rstrip(". ") + ".build"


def read_plans(folder: Path) -> list[dict[str, Any]]:
    """Every plan in folder, by file name in any case: [{"file", "plan"}]. Other tools and the player keep
    files here too, so what isn't a plan -- not a .build file, not a JSON object with a name, not UTF-8 -- is
    skipped, not judged. A byte-order mark is fine. A folder not made yet has no plans."""
    if not folder.is_dir():
        return []
    plans = []
    for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
        if path.suffix.casefold() != ".build" or not path.is_file():
            continue
        try:
            plan = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(plan, dict) and isinstance(plan.get("name"), str):
            plans.append({"file": path.name, "plan": plan})
    return plans


def remove_plans(folder: Path, files: list[str]) -> list[str]:
    """Remove the named plan files from folder; returns the ones removed, in order.

    Each must be a plain .build file name -- no folder, nothing Windows refuses in a name -- or ValueError,
    and nothing is removed. A file already gone (the player may have deleted it by hand) is skipped, and so
    is a folder; nothing else in folder is touched.
    """
    for name in files:
        if not name.casefold().endswith(".build") or _NOT_IN_FILE_NAMES.search(name):
            raise ValueError(f"{name!r} isn't a plan file name; nothing was removed")
    removed = []
    for name in dict.fromkeys(files):
        path = folder / name
        if path.is_file():
            path.unlink()
            removed.append(name)
    return removed
