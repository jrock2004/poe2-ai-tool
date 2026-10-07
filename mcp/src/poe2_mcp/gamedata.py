"""Game data for the tools, from pinned exports of the game's own files -- generated, never hand-edited.

Mod tiers, bases and their requirements come from repoe-fork/poe2 (`data/mods_by_base.json`,
`mods.json`, `base_items.json`), which is processed from GGG's game files; the data remains GGG's. So does
the in-game text of what PoE2's Currency Exchange trades (currency, omens, essences, runes...). Which items
those are comes from repoe-fork/dat-export's `CurrencyExchange` table: the game files still carry PoE1
items, and nothing in their records tells the two apart. This module turns them into one compact snapshot
per patch (`data/items_<patch>.json`) that the tools read at runtime: which mods each base can roll, each
tier's name, side, item-level gate and text, and each traded item's text. Regenerate per patch, from each
export's commit for that game version:

    python -m poe2_mcp.gamedata items <poe2-commit> <dat-export-commit> 0.5.5 src/poe2_mcp/data/items_0_5_5.json

Build-time only: the command line fetches the exports; nothing the tools call touches the network. Text
keeps the game's wording with its display markup stripped ("[Resistances|Fire Resistance]" -> "Fire
Resistance").
"""
from __future__ import annotations

import csv
import functools
import io
import json
import re
import sys
from importlib import resources
from typing import Any

import httpx

from .knowledge import patch_key

# Equipment, by mods_by_base's class names: what a player wears or wields that rolls prefixes/suffixes.
PLAYER_CLASSES = (
    "Amulets", "Belts", "Body Armours", "Boots", "Bows", "Bucklers", "Charms", "Claws", "Crossbows",
    "Daggers", "Flails", "Foci", "Gloves", "Helmets", "Jewels", "Life Flasks", "Mana Flasks",
    "One Hand Axes", "One Hand Maces", "One Hand Swords", "Quarterstaves", "Quivers", "Rings", "Sceptres",
    "Shields", "Spears", "Staves", "Talismans", "Traps", "Two Hand Axes", "Two Hand Maces",
    "Two Hand Swords", "Wands",
)
_SIDES = ("prefix", "suffix")
RAW_HOST = "https://raw.githubusercontent.com"
EXPORT_REPO = "repoe-fork/poe2"
EXPORT_FILES = ("mods_by_base", "mods", "base_items")
TABLES_REPO = "repoe-fork/dat-export"
TABLES_DIR = "current/poe2/heuristics/csv"
USER_AGENT = "poe2-ai-tools (game-data refresh; https://github.com/jrock2004/poe2-ai-tool)"
_COMMIT_RE = re.compile(r"[0-9a-f]{7,40}")
_PATCH_RE = re.compile(r"\d+\.\d+\.\d+[a-z]?")
_SNAPSHOT_PREFIX = "items_"
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


def build_texts(base_items: dict[str, Any], traded: set[str]) -> dict[str, dict[str, str]]:
    """The game's text for each item PoE2's Currency Exchange trades: name -> {"class", "text", "use"},
    by name. Pure.

    `traded` is the base ids the exchange lists (`fetch_exchange`). text is the item's description, use
    its directions ("Right click this item then left click a rare item to apply it."), each as a player
    reads it (`_game_text`), or "" if it has none. An item with neither is left out. A traded id that
    base_items doesn't have raises ValueError -- the two exports came from different game versions -- and
    so do two traded items with one name, since the text is looked up by name.
    """
    texts: dict[str, dict[str, str]] = {}
    ids: dict[str, str] = {}
    for base_id in sorted(traded):
        base = base_items.get(base_id)
        if base is None:
            raise ValueError(f"CurrencyExchange trades {base_id}, which base_items.json doesn't have")
        props = base.get("properties") or {}
        text, use = _game_text(props.get("description")), _game_text(props.get("directions"))
        if not (text or use):
            continue
        name = base["name"]
        if name in ids:
            raise ValueError(f"CurrencyExchange trades two items named {name!r}: {ids[name]} and {base_id}")
        ids[name] = base_id
        texts[name] = {"class": base["item_class"], "text": text, "use": use}
    return dict(sorted(texts.items()))


def _game_text(raw: str | None) -> str:
    """Item text as a player reads it: markup removed, each line trimmed, and the game's line breaks kept
    as LF (the export mixes in CRLF). Pure."""
    return "\n".join(clean_text(line).strip() for line in (raw or "").splitlines()).strip()


def render_items(items: dict[str, Any], patch: str, source: str) -> str:
    """The snapshot JSON text: patch, source, then one pool, base, tier and item text per line, so a
    per-patch regeneration reads as a small diff. Pure; ends with a newline."""

    def rows(pairs: Any) -> str:
        return ",\n".join(f"  {key}{json.dumps(value, ensure_ascii=False)}" for key, value in pairs)

    return (
        "{\n"
        f'"patch": {json.dumps(patch)},\n'
        f'"source": {json.dumps(source)},\n'
        '"groups": [\n' + rows(("", g) for g in items["groups"]) + "\n],\n"
        '"bases": {\n' + rows((f"{json.dumps(n)}: ", v) for n, v in items["bases"].items()) + "\n},\n"
        '"mods": {\n' + rows((f"{json.dumps(t)}: ", m) for t, m in items["mods"].items()) + "\n},\n"
        '"texts": {\n' + rows((f"{json.dumps(n)}: ", t) for n, t in items["texts"].items()) + "\n}\n"
        "}\n"
    )


def mod_tiers(
    items: dict[str, Any], base: str, search: str | None = None, item_level: int | None = None
) -> dict[str, Any]:
    """Which mods `base` can roll, from a loaded snapshot: {"base", "patch", "variants"}. Pure.

    `base` matches a base name in any case; an unknown one returns base None and up to 8 `suggestions`
    (see `_suggest`). Each variant of the name comes back with its class, requirements and
    families -- prefixes first, then suffixes -- each with every tier: name, itemLevel, text. `search`
    keeps the families whose name or any tier's text contains it (any case); a found base with no
    matching family is the answer "that can't roll here". With `item_level`, each tier says whether it
    `canRoll` on an item of that level.
    """
    if item_level is not None and item_level < 1:
        raise ValueError(f"item_level must be at least 1 (the item's item level), got {item_level}")
    wanted = base.strip().lower()
    name = next((n for n in items["bases"] if n.lower() == wanted), None)
    if name is None:
        return {"base": None, "patch": items["patch"], "variants": [], "suggestions": _suggest(items["bases"], wanted)}

    needle = (search or "").strip().lower()
    variants = []
    for variant in items["bases"][name]:
        pool = items["groups"][variant["group"]]
        families = []
        for side in _SIDES:
            for family, tier_ids in pool[side].items():
                tiers = [items["mods"][t] for t in tier_ids]
                if needle and needle not in family.lower() and not any(needle in t["text"].lower() for t in tiers):
                    continue
                rows = []
                for tier in tiers:
                    row = {"name": tier["name"], "itemLevel": tier["level"], "text": tier["text"]}
                    if item_level is not None:
                        row["canRoll"] = tier["level"] <= item_level
                    rows.append(row)
                families.append({"family": family, "side": side, "tiers": rows})
        variants.append({"class": variant["class"], "requirements": variant["requirements"], "families": families})
    return {"base": name, "patch": items["patch"], "variants": variants}


def _suggest(names: Any, wanted: str) -> list[str]:
    """Up to 8 base names for a lowercase name that matched none: those that contain it, or, when none
    does (an old or mistyped full name), those sharing the most whole words with it -- fewer words
    first, as the closer match, then by name. Pure."""
    hits = sorted(n for n in names if wanted in n.lower())
    if hits:
        return hits[:8]
    words = set(wanted.split())
    ranked = sorted((-len(words & set(n.lower().split())), len(n.split()), n) for n in names)
    return [n for shared, _, n in ranked if shared < 0][:8]


def newest_snapshot(names: Any) -> str | None:
    """The `items_<patch>.json` name with the highest patch, or None. Pure. Ordered by patch, not text
    (0.5.10 after 0.5.5; a hotfix letter after its base patch); other names are ignored."""
    best, best_key = None, None
    for name in names:
        if not (name.startswith(_SNAPSHOT_PREFIX) and name.endswith(".json")):
            continue
        try:
            key = patch_key(name[len(_SNAPSHOT_PREFIX):-len(".json")].replace("_", "."))
        except ValueError:
            continue
        if best_key is None or key > best_key:
            best, best_key = name, key
    return best


@functools.lru_cache(maxsize=None)
def load_items() -> dict[str, Any] | None:
    """The newest committed item snapshot, or None if there isn't one. Loaded once."""
    data = resources.files("poe2_mcp").joinpath("data")
    name = newest_snapshot(entry.name for entry in data.iterdir())
    return json.loads(data.joinpath(name).read_text(encoding="utf-8")) if name else None


def _fetch_files(repo: str, commit: str, paths: list[str],
                 transport: httpx.BaseTransport | None) -> list[httpx.Response]:
    """Each of `paths` in GitHub repo `repo` at `commit`, in order, from GitHub's raw file host.

    `commit` must be a commit hash: a branch or tag can move, and the snapshot has to name exactly the
    export it came from. An HTTP error raises RuntimeError.
    """
    if not _COMMIT_RE.fullmatch(commit or ""):
        raise ValueError(f"Expected a commit hash (7-40 hex characters), not {commit!r}: a branch or tag can move")
    responses = []
    with httpx.Client(base_url=f"{RAW_HOST}/{repo}/{commit}/", headers={"User-Agent": USER_AGENT},
                      timeout=60.0, transport=transport) as client:
        for path in paths:
            resp = client.get(path)
            if resp.status_code != 200:
                raise RuntimeError(f"{repo}@{commit} {path} -> HTTP {resp.status_code}")
            responses.append(resp)
    return responses


def fetch_export(commit: str, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    """Download repoe-fork/poe2's export at `commit`: {"mods_by_base", "mods", "base_items" (parsed),
    "game_version"}. Build-time only -- the command line runs it, the tools never do. A commit hash only;
    an HTTP error raises RuntimeError (see `_fetch_files`).
    """
    *files, version = _fetch_files(
        EXPORT_REPO, commit, [*(f"data/{name}.json" for name in EXPORT_FILES), "version.txt"], transport)
    export: dict[str, Any] = {name: resp.json() for name, resp in zip(EXPORT_FILES, files)}
    export["game_version"] = version.text.strip()
    return export


def fetch_exchange(commit: str, transport: httpx.BaseTransport | None = None) -> set[str]:
    """The base item ids PoE2's Currency Exchange trades, from repoe-fork/dat-export at `commit`: its
    `CurrencyExchange` table, each row's Item a `BaseItemTypes` row. Build-time only, like `fetch_export`.

    Every row counts, enabled in challenge leagues or not: what Standard trades is in the game. A row
    naming an item BaseItemTypes doesn't have raises ValueError -- the export changed shape.
    """
    tables = [f"{TABLES_DIR}/{table}.csv" for table in ("CurrencyExchange", "BaseItemTypes")]
    exchange, item_types = _fetch_files(TABLES_REPO, commit, tables, transport)
    ids = {row["rownum"]: row["Id"] for row in csv.DictReader(io.StringIO(item_types.text))}
    traded = set()
    for row in csv.DictReader(io.StringIO(exchange.text)):
        if row["Item"] not in ids:
            raise ValueError(
                f"CurrencyExchange row {row['rownum']} trades item {row['Item']}, which BaseItemTypes doesn't have")
        traded.add(ids[row["Item"]])
    return traded


def main(argv: list[str]) -> None:
    """CLI: gamedata items <poe2-commit> <dat-export-commit> <patch> <out.json> -- fetch repoe-fork/poe2's
    export and dat-export's exchange table at their commits, and write the item snapshot for game patch
    <patch> (e.g. 0.5.5) to <out.json>.

    Writes the file itself (UTF-8, no BOM, LF) instead of printing for a shell redirect: Windows
    PowerShell 5.1's `>` would write UTF-16, and text mode on Windows would turn LF into CRLF.
    """
    if len(argv) != 5 or argv[0] != "items":
        sys.exit("usage: python -m poe2_mcp.gamedata items <poe2-commit> <dat-export-commit> <patch> <out.json>")
    _, commit, tables_commit, patch, out = argv
    if not _PATCH_RE.fullmatch(patch):
        sys.exit(f"patch must be a game patch like 0.5.5 (or a hotfix like 0.5.5e), not {patch!r}")
    export = fetch_export(commit)
    items = build_items(export["mods_by_base"], export["mods"], export["base_items"])
    items["texts"] = build_texts(export["base_items"], fetch_exchange(tables_commit))
    source = (f"{EXPORT_REPO}@{commit} (game {export['game_version']}), "
              f"{TABLES_REPO}@{tables_commit} CurrencyExchange -- data is GGG's")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_items(items, patch, source))


if __name__ == "__main__":
    main(sys.argv[1:])
