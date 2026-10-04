"""The player's persistent state -- profile, roster, currency, league records -- as one JSON document
in the per-user data dir (store.py), shared by every Claude client and kept across updates.

The skills own the shapes (poe2-core's shared model); this module only stores them. Skills change
the document with an RFC 7396 JSON Merge Patch: objects merge recursively, null deletes a key, arrays
and scalars replace. It enforces just the two things that would otherwise corrupt state silently:
only the known top-level sections, and at most one active character.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from . import store

SECTIONS = ("player", "characters", "currency", "leagues")
STATE_FILE = "state.json"
VERSION = 1


def empty_state() -> dict[str, Any]:
    return {"version": VERSION, **{section: {} for section in SECTIONS}}


def merge_patch(target: Any, patch: Any) -> Any:
    """RFC 7396 merge of patch into target. Pure; never mutates its inputs."""
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    result = copy.deepcopy(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


def apply_update(state: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """state with patch merged in. Pure. Raises ValueError for a non-object patch or an unknown
    top-level key (including `version`, which the server owns). Setting `active: true` on a character
    clears it on every other character."""
    if not isinstance(patch, dict):
        raise ValueError("patch must be a JSON object keyed by section")
    unknown = [key for key in patch if key not in SECTIONS]
    if unknown:
        raise ValueError(
            f"Unknown state section(s): {', '.join(unknown)}. Sections: {', '.join(SECTIONS)}"
        )
    for section in SECTIONS:
        if section in patch and not isinstance(patch[section], dict):
            raise ValueError(f'section "{section}" must be patched with an object')

    new = merge_patch(state, patch)

    activated = [
        name
        for name, fields in (patch.get("characters") or {}).items()
        if isinstance(fields, dict) and fields.get("active") is True
    ]
    if activated:
        keep = activated[-1]
        for name, character in new["characters"].items():
            if name != keep and isinstance(character, dict) and character.get("active"):
                character["active"] = False
    return new


def load(root: Path) -> dict[str, Any]:
    """root/state.json, or the empty state if missing; missing sections are filled in. Corrupt JSON
    raises, naming the path."""
    stored = store.read_json(root / STATE_FILE)
    return {**empty_state(), **stored}


def update(root: Path, patch: dict[str, Any]) -> dict[str, Any]:
    """Apply patch to the saved state and write it; nothing is written if the patch is rejected."""
    new = apply_update(load(root), patch)
    store.write_json(root / STATE_FILE, new)
    return new
