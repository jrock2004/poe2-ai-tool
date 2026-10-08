"""Find the folder the in-game Build Planner reads its plans from. File system only -- no network.

The game reads <Documents>\\My Games\\Path of Exile 2\\BuildPlanner and watches it while it runs. On Windows,
Documents is wherever its known folder points -- OneDrive moves it, e.g. to C:\\Users\\<name>\\OneDrive\\Documents
-- so it's asked for (SHGetKnownFolderPath) before the usual places are guessed. The game makes "Path of
Exile 2" on first launch; BuildPlanner may not exist yet, and nothing here makes it -- writing does.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

GAME_FOLDER = "Path of Exile 2"
PLANNER_FOLDER = "BuildPlanner"
_FOLDERID_DOCUMENTS = "FDD39AD0-238F-46AF-ADB4-6C85480369C7"


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
