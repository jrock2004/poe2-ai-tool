"""Game data for the tools, from a pinned export of the game's own files -- generated, never hand-edited.

Mod tiers, bases and their requirements come from repoe-fork/poe2 (`data/mods_by_base.json`,
`mods.json`, `base_items.json`), which is processed from GGG's game files; the data remains GGG's. This
module turns them into one compact snapshot per patch (`data/items_<patch>.json`) that the tools read at
runtime: which mods each base can roll, and each tier's name, side, item-level gate and text. Regenerate
per patch, from the export commit for that game version:

    python -m poe2_mcp.gamedata items <commit> 0.5.5 src/poe2_mcp/data/items_0_5_5.json

Build-time only: the command line fetches the export; nothing the tools call touches the network. Text
keeps the game's wording with its display markup stripped ("[Resistances|Fire Resistance]" -> "Fire
Resistance").
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

import httpx

# Equipment, by mods_by_base's class names: what a player wears or wields that rolls prefixes/suffixes.
PLAYER_CLASSES = (
    "Amulets", "Belts", "Body Armours", "Boots", "Bows", "Bucklers", "Charms", "Claws", "Crossbows",
    "Daggers", "Flails", "Foci", "Gloves", "Helmets", "Jewels", "Life Flasks", "Mana Flasks",
    "One Hand Axes", "One Hand Maces", "One Hand Swords", "Quarterstaves", "Quivers", "Rings", "Sceptres",
    "Shields", "Spears", "Staves", "Talismans", "Traps", "Two Hand Axes", "Two Hand Maces",
    "Two Hand Swords", "Wands",
)
_SIDES = ("prefix", "suffix")
EXPORT_REPO = "https://raw.githubusercontent.com/repoe-fork/poe2"
EXPORT_FILES = ("mods_by_base", "mods", "base_items")
USER_AGENT = "poe2-ai-tools (game-data refresh; https://github.com/jrock2004/poe2-ai-tool)"
_COMMIT_RE = re.compile(r"[0-9a-f]{7,40}")
_PATCH_RE = re.compile(r"\d+\.\d+\.\d+[a-z]?")
# The game's display markup: "<underline>{Fire Spell on Hit}", "[EnergyShield|Energy Shield]", "[Rune]".
_DISPLAY_TAG_RE = re.compile(r"<[^>]*>\{([^}]*)\}")
_DISPLAY_LINK_RE = re.compile(r"\[([^\]|]*)(?:\|([^\]]*))?\]")


def clean_text(line: str) -> str:
    """Game text as a player reads it, with the display markup removed. Pure."""
    line = _DISPLAY_TAG_RE.sub(lambda m: m.group(1), line)
    return _DISPLAY_LINK_RE.sub(lambda m: m.group(2) or m.group(1), line)


def build_items(
    mods_by_base: dict[str, Any],
    mods: dict[str, Any],
    base_items: dict[str, Any],
    classes: tuple[str, ...] = PLAYER_CLASSES,
) -> dict[str, Any]:
    """The item snapshot from the parsed export files. Pure.

    Returns {"groups", "bases", "mods"}:
    - groups: each distinct mod pool, {"prefix"|"suffix": {family: [tier ids in item-level order]}}.
      Tag groups that roll the same mods share one pool.
    - bases: name -> variants [{"class", "group" (index into groups), "requirements": {level, str, dex,
      int}}]. Released bases of `classes` only. Same-named bases that roll the same pool with the same
      requirements are one variant; the rest stay apart, lowest level first.
    - mods: tier id -> {"name", "side", "level" (the item-level gate), "family", "text"}, for the tiers
      some pool uses.

    Only prefixes and suffixes: corruption and unique mods aren't rolled by crafting currency. A tier
    or base that the other file doesn't have raises ValueError -- the export changed shape.
    """
    groups: list[dict[str, Any]] = []
    group_index: dict[str, int] = {}
    used: set[str] = set()
    variants: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {}

    for item_class in sorted(c for c in mods_by_base if c in classes):
        for tags in sorted(mods_by_base[item_class]):
            entry = mods_by_base[item_class][tags]
            pool: dict[str, Any] = {}
            for side in _SIDES:
                families: dict[str, list[str]] = {}
                for family, tiers in sorted((entry["mods"].get(side) or {}).items()):
                    for tier in tiers:
                        if tier not in mods:
                            raise ValueError(f"{item_class} / {tags} lists tier {tier}, which mods.json doesn't have")
                    families[family] = sorted(tiers, key=lambda t: (tiers[t], t))
                    used.update(tiers)
                pool[side] = families
            group = group_index.setdefault(json.dumps(pool, sort_keys=True), len(groups))
            if group == len(groups):
                groups.append(pool)

            for base_id in entry["bases"]:
                base = base_items.get(base_id)
                if base is None:
                    raise ValueError(f"{item_class} / {tags} lists base {base_id}, which base_items.json doesn't have")
                if base.get("release_state") != "released":
                    continue
                req = base.get("requirements") or {}
                requirements = {"level": req.get("level", 0), "str": req.get("strength", 0),
                                "dex": req.get("dexterity", 0), "int": req.get("intelligence", 0)}
                variant = {"class": item_class, "group": group, "requirements": requirements}
                variants.setdefault(base["name"], {})[(group, *requirements.values())] = variant

    bases = {
        name: sorted(found.values(), key=lambda v: (v["requirements"]["level"], v["group"]))
        for name, found in sorted(variants.items())
    }
    tiers = {
        tier: {
            "name": mods[tier].get("name"),
            "side": mods[tier].get("generation_type"),
            "level": mods[tier].get("required_level"),
            "family": mods[tier].get("type"),
            "text": clean_text(mods[tier].get("text") or ""),
        }
        for tier in sorted(used)
    }
    return {"groups": groups, "bases": bases, "mods": tiers}


def render_items(items: dict[str, Any], patch: str, source: str) -> str:
    """The snapshot JSON text: patch, source, then one pool, base and tier per line, so a per-patch
    regeneration reads as a small diff. Pure; ends with a newline."""

    def rows(pairs: Any) -> str:
        return ",\n".join(f"  {key}{json.dumps(value, ensure_ascii=False)}" for key, value in pairs)

    return (
        "{\n"
        f'"patch": {json.dumps(patch)},\n'
        f'"source": {json.dumps(source)},\n'
        '"groups": [\n' + rows(("", g) for g in items["groups"]) + "\n],\n"
        '"bases": {\n' + rows((f"{json.dumps(n)}: ", v) for n, v in items["bases"].items()) + "\n},\n"
        '"mods": {\n' + rows((f"{json.dumps(t)}: ", m) for t, m in items["mods"].items()) + "\n}\n"
        "}\n"
    )


def fetch_export(commit: str, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    """Download repoe-fork/poe2's export at `commit`: {"mods_by_base", "mods", "base_items" (parsed),
    "game_version"}. Build-time only -- the command line runs it, the tools never do.

    `commit` must be a commit hash: a branch or tag can move, and the snapshot has to name exactly the
    export it came from. An HTTP error raises RuntimeError.
    """
    if not _COMMIT_RE.fullmatch(commit or ""):
        raise ValueError(f"Expected a commit hash (7-40 hex characters), not {commit!r}: a branch or tag can move")
    with httpx.Client(base_url=f"{EXPORT_REPO}/{commit}/", headers={"User-Agent": USER_AGENT},
                      timeout=60.0, transport=transport) as client:

        def get(path: str) -> httpx.Response:
            resp = client.get(path)
            if resp.status_code != 200:
                raise RuntimeError(f"repoe-fork/poe2@{commit} {path} -> HTTP {resp.status_code}")
            return resp

        export: dict[str, Any] = {name: get(f"data/{name}.json").json() for name in EXPORT_FILES}
        export["game_version"] = get("version.txt").text.strip()
    return export


def main(argv: list[str]) -> None:
    """CLI: gamedata items <commit> <patch> <out.json> -- fetch the export at <commit> and write the item
    snapshot for game patch <patch> (e.g. 0.5.5) to <out.json>.

    Writes the file itself (UTF-8, no BOM, LF) instead of printing for a shell redirect: Windows
    PowerShell 5.1's `>` would write UTF-16, and text mode on Windows would turn LF into CRLF.
    """
    if len(argv) != 4 or argv[0] != "items":
        sys.exit("usage: python -m poe2_mcp.gamedata items <commit> <patch> <out.json>")
    _, commit, patch, out = argv
    if not _PATCH_RE.fullmatch(patch):
        sys.exit(f"patch must be a game patch like 0.5.5 (or a hotfix like 0.5.5e), not {patch!r}")
    export = fetch_export(commit)
    items = build_items(export["mods_by_base"], export["mods"], export["base_items"])
    source = f"repoe-fork/poe2@{commit} (game {export['game_version']}) -- data is GGG's"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_items(items, patch, source))


if __name__ == "__main__":
    main(sys.argv[1:])
