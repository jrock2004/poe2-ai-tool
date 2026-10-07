"""The campaign's permanent rewards (resistances, spirit, weapon-set points...), from a committed snapshot.

PoE2's game data holds the reward values (dat-export `QuestStaticRewards`) but not which boss, item or
shrine gives each one, nor which rewards are a pick-one choice. Path of Building 2 keeps that list by
hand, named and with its choices marked, in `src/Data/QuestRewards.lua`; we take it from there. Its values
matched the 0.5.5 game data when this snapshot was made (see the snapshot's source note).

Regenerate per patch from a download of that file at a pinned commit:

    python -m poe2_mcp.campaign path/to/QuestRewards.lua 0_5_5 "<source note>" \\
        src/poe2_mcp/data/campaign_0_5_5.json

Nothing here touches the network: the CLI reads a downloaded file, and `campaign_rewards` (behind the
tool of that name) reads only the committed JSON.
"""
from __future__ import annotations

import functools
import json
import re
import sys
from collections.abc import Mapping, Sequence
from importlib import resources
from typing import Any

from .treedata import parse_lua_table

_SNAPSHOT_PREFIX = "campaign_"
_VERSION_RE = re.compile(r"\d+_\d+_\d+")
_REQUIRED = ("Act", "Description", "Area", "Info", "AreaLevel")
# PoB-only fields: Act is a sort key (the file is in campaign order already), useConfig a PoB UI switch.
_KNOWN = {*_REQUIRED, "Stat", "Options", "questPoints", "useConfig"}


def parse_quest_rewards(lua_text: str) -> list[dict[str, Any]]:
    """PoB2's QuestRewards.lua as rewards, in the file's (campaign) order. Pure.

    Each is {"part" ("Act 1", "Interlude 2", "Epilog"), "area", "from" (the boss, item or shrine),
    "areaLevel", then "stat" or "options" (a pick-one reward), and "weaponSetPoints" when it gives some}.
    A text keeps its line breaks but not PoB's indenting tabs. A reward with an unknown or missing field,
    or with both or neither of Stat and Options, raises ValueError -- the file changed shape.
    """
    entries = parse_lua_table(lua_text)
    if not isinstance(entries, list):
        raise ValueError("QuestRewards.lua should be a list of rewards")
    return [_reward(entry) for entry in entries]


def _reward(entry: Mapping[str, Any]) -> dict[str, Any]:
    name = entry.get("Info", "a reward")
    unknown = sorted(set(entry) - _KNOWN)
    if unknown:
        raise ValueError(f"{name} has unknown field(s) {', '.join(unknown)}")
    missing = [field for field in _REQUIRED if field not in entry]
    if missing:
        raise ValueError(f"{name} is missing {', '.join(missing)}")
    if ("Stat" in entry) == ("Options" in entry):
        raise ValueError(f"{name} should have exactly one of Stat and Options")
    reward: dict[str, Any] = {
        "part": entry["Description"], "area": entry["Area"], "from": entry["Info"], "areaLevel": entry["AreaLevel"],
    }
    if "Stat" in entry:
        reward["stat"] = _text(entry["Stat"])
    else:
        reward["options"] = [_text(option) for option in entry["Options"]]
    if "questPoints" in entry:
        reward["weaponSetPoints"] = entry["questPoints"]
    return reward


def _text(text: str) -> str:
    return "\n".join(line.strip() for line in text.split("\n"))


@functools.lru_cache(maxsize=None)
def load_snapshot(version: str) -> dict[str, Any] | None:
    """The committed snapshot for a version like '0_5_5', or None if none (or the version is malformed)."""
    if not version or not _VERSION_RE.fullmatch(version):
        return None
    path = _data_dir().joinpath(f"{_SNAPSHOT_PREFIX}{version}.json")  # one argument: 3.10-safe
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def latest_version() -> str | None:
    """The newest committed snapshot's version, e.g. '0_5_5', or None if there are none."""
    versions = [
        name[len(_SNAPSHOT_PREFIX):-len(".json")]
        for name in (p.name for p in _data_dir().iterdir())
        if name.startswith(_SNAPSHOT_PREFIX) and name.endswith(".json")
    ]
    versions = [v for v in versions if _VERSION_RE.fullmatch(v)]
    return max(versions, key=lambda v: tuple(int(n) for n in v.split("_")), default=None)


def campaign_rewards(search: str | None = None) -> dict[str, Any]:
    """The newest snapshot's rewards: {"patch" ('0.5.5'), "source", "total", "matches"}, in campaign order.

    Without `search`, every reward. With it, those whose part, area, source, stat or any option contains it
    -- in any case, with line breaks read as spaces. A match is the whole reward, so a pick-one keeps all its
    options. No snapshot returns {"valid": False, "error", "note"}, like stash_layout.
    """
    version = latest_version()
    snapshot = load_snapshot(version) if version else None
    if snapshot is None:
        return {"valid": False, "error": "no campaign snapshot is installed",
                "note": "Regenerate one with `python -m poe2_mcp.campaign` (see CONTRIBUTING.md)."}
    needle = _flat(search or "")
    matches = [reward for reward in snapshot["rewards"]
               if not needle or any(needle in _flat(text) for text in _searched(reward))]
    return {"patch": version.replace("_", "."), "source": snapshot["source"], "total": len(matches),
            "matches": matches}


def _searched(reward: Mapping[str, Any]) -> list[str]:
    return [reward["part"], reward["area"], reward["from"], reward.get("stat", ""), *reward.get("options", ())]


def _flat(text: str) -> str:
    """Lowercase, with each run of whitespace -- line breaks included -- as one space. Pure."""
    return " ".join(text.lower().split())


def _data_dir():
    return resources.files("poe2_mcp").joinpath("data")


def render_snapshot(rewards: Sequence[Mapping[str, Any]], version: str, source: str) -> str:
    """The snapshot JSON text: version, source, then the rewards one per line (so a per-patch
    regeneration reads as a small diff). Pure; ends with a newline.
    """
    lines = [f"  {json.dumps(reward, ensure_ascii=False)}" for reward in rewards]
    return (
        "{\n"
        f'"version": {json.dumps(version)},\n'
        f'"source": {json.dumps(source)},\n'
        '"rewards": [\n' + ",\n".join(lines) + "\n]\n}\n"
    )


def main(argv: list[str]) -> None:
    """CLI: campaign <QuestRewards.lua> <version> <source note> <out.json> -- writes the snapshot file.

    Writes the file itself (UTF-8, no BOM, LF) instead of printing for a shell redirect: Windows
    PowerShell 5.1's `>` would write UTF-16. Prints a summary for the person regenerating to check.
    """
    if len(argv) != 4:
        sys.exit("usage: python -m poe2_mcp.campaign <QuestRewards.lua> <version> <source note> <out.json>")
    path, version, source, out = argv
    with open(path, encoding="utf-8") as f:
        rewards = parse_quest_rewards(f.read())
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_snapshot(rewards, version, source))
    choices = sum("options" in reward for reward in rewards)
    points = sum(reward.get("weaponSetPoints", 0) for reward in rewards)
    print(f"{len(rewards)} rewards, {choices} with options, {points} weapon-set points")


if __name__ == "__main__":
    main(sys.argv[1:])
