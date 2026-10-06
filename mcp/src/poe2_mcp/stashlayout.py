"""Stash-tab slot layouts for reading screenshots, from a committed snapshot of PoE2's game data.

The special stash tabs (Currency, Essence, Ritual, ...) are fixed layouts: each slot always holds
the same item, held or not. GGG's `<Tab>StashTabLayout` tables say which item sits where; we take
them from repoe-fork/dat-export's CSV export (the data is GGG's). That export names columns by
heuristic, and some guesses are wrong or missing, so the per-tab column map here is the verified
reading -- and a rename fails loudly rather than misreading.

Regenerate per patch from a local checkout (or download) of the export's CSV folder:

    python -m poe2_mcp.stashlayout path/to/current/poe2/heuristics/csv 0_5_5 "<source note>" src/poe2_mcp/data/stash_layouts_0_5_5.json

Build-time only: nothing here touches the network, and runtime reads only the committed JSON.
"""
from __future__ import annotations

import csv
import functools
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from typing import Any

TABS = ("abyss", "breach", "currency", "delirium", "essence", "expedition", "fragment", "ritual", "socketable")

_GEOMETRY = ("x", "y", "w", "h", "size")
_COMMON = {"item": "StoredItem", "x": "XOffset", "y": "YOffset", "w": "Width", "h": "Height", "size": "SlotSize"}

# Slot field -> the export's column name for it. "show"/"hide" is the visibility flag, whichever way
# round the table stores it. A field a tab leaves out stays None (hidden_when_empty: False).
_COLUMNS: dict[str, dict[str, str]] = {
    "currency": {**_COMMON, "show": "ShowIfEmpty", "group": "SlotGroup"},
    "essence": {**_COMMON, "show": "ShowIfEmpty"},
    "ritual": {**_COMMON, "show": "ShowIfEmpty", "label": "MiniIcon"},
    "delirium": {**_COMMON, "show": "ShowIfEmpty"},
    # SubGroup is a page (runes, soul cores, idols, ...): slots overlap across pages, never within one.
    "socketable": {**_COMMON, "show": "ShowIfEmpty", "sub_tab": "SubGroup"},
    "abyss": {**_COMMON, "hide": "HideIfEmpty"},
    # Unnamed in the export.
    "breach": {"item": "BaseItemType", "x": "i32_24", "y": "i32_28", "w": "i32_44", "h": "i32_48",
               "size": "i32_32"},
    # The export swaps these two: "Tab" holds the slot size, "SlotSize" holds the sub-tab.
    "fragment": {**_COMMON, "item": "BaseItemType", "size": "Tab", "sub_tab": "SlotSize", "hide": "HideIfEmpty"},
    "expedition": {**_COMMON, "item": "BaseItemType", "size": "Tab", "sub_tab": "SlotSize", "hide": "HideIfEmpty"},
}
_RANGES = {"x": (0, 1000), "y": (0, 1000), "w": (1, 4), "h": (1, 4), "size": (40, 120)}
_LABEL_PREFIX = "RitualStashIcon"
_CRAFTING_SLOT = "CraftingSlot"
_SNAPSHOT_PREFIX = "stash_layouts_"
_VERSION_RE = re.compile(r"\d+_\d+_\d+")


@dataclass(frozen=True)
class Slot:
    key: str                 # last segment of the row's Id, e.g. "CurrencyRerollRare", "Generic3", "CraftingSlot"
    item: str | None         # None: no fixed item -- an open slot or the crafting slot
    x: int                   # offsets and size are in the tab's own pixels (~900 wide)
    y: int
    w: int                   # in slots
    h: int
    size: int                # one slot's side, in pixels
    hidden_when_empty: bool  # the slot only appears while the player holds the item
    sub_tab: int | None      # fragment, expedition, socketable: which page of the tab
    group: int | None        # currency SlotGroup
    label: str | None        # ritual group icon, e.g. "Exalted"


def normalize(tab: str, rows: Iterable[Mapping[str, str]], item_names: Mapping[int, str]) -> list[Slot]:
    """One Slot per exported row of `tab`'s layout table, in row order.

    `rows` are the CSV rows as read (header -> text); `item_names` maps BaseItemTypes rownum -> Name.
    Raises ValueError on an unknown tab, a missing column, an item index with no name, or geometry
    out of range (offsets 0-1000, size 40-120, width/height 1-4) -- each a sign the table changed.
    """
    if tab not in _COLUMNS:
        raise ValueError(f"unknown stash tab {tab!r}; expected one of {', '.join(TABS)}")
    columns = _COLUMNS[tab]
    return [_slot(tab, columns, row, item_names) for row in rows]


def _slot(tab: str, columns: Mapping[str, str], row: Mapping[str, str], item_names: Mapping[int, str]) -> Slot:
    def cell(field: str) -> str:
        column = columns[field]
        if column not in row:
            raise ValueError(f"{tab}: column {column!r} (for {field}) is missing -- did the export rename it?")
        return row[column]

    key = row.get("Id", "").rsplit("/", 1)[-1]
    geometry = {field: int(cell(field)) for field in _GEOMETRY}
    for field, value in geometry.items():
        low, high = _RANGES[field]
        if not low <= value <= high:
            raise ValueError(f"{tab}: {key} has {field}={value}, outside {low}-{high} -- did the table change?")

    item = None
    if cell("item") != "":
        index = int(cell("item"))
        if index not in item_names:
            raise ValueError(f"{tab}: {key} stores item {index}, which has no name in BaseItemTypes")
        item = item_names[index]

    if "show" in columns:
        hidden = cell("show") == ""
    elif "hide" in columns:
        hidden = cell("hide") != ""
    else:
        hidden = False

    label = None
    if "label" in columns:  # an art path, e.g. ".../RitualStash/RitualStashIconExalted" -> "Exalted"
        label = cell("label").rsplit("/", 1)[-1].removeprefix(_LABEL_PREFIX) or None

    return Slot(
        key=key,
        item=item,
        **geometry,
        hidden_when_empty=hidden,
        sub_tab=int(cell("sub_tab")) if "sub_tab" in columns else None,
        group=int(cell("group")) if "group" in columns else None,
        label=label,
    )


def overlaps(slots: Sequence[Slot]) -> list[tuple[Slot, Slot]]:
    """Pairs of slots on the same sub-tab whose footprints (x, y, w*size, h*size) intersect.

    Touching edges don't count. Pure; pairs come in input order.
    """
    def box(s: Slot) -> tuple[int, int, int, int]:
        return s.x, s.y, s.x + s.w * s.size, s.y + s.h * s.size

    pairs = []
    for i, a in enumerate(slots):
        ax0, ay0, ax1, ay1 = box(a)
        for b in slots[i + 1:]:
            if a.sub_tab != b.sub_tab:
                continue
            bx0, by0, bx1, by1 = box(b)
            if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                pairs.append((a, b))
    return pairs


def reading_view(slots: Sequence[Slot]) -> dict[str, Any]:
    """How a screenshot of the tab reads, for naming each slot by position.

    - `rows`: the always-shown slots in reading order -- by sub-tab, then top to bottom, each row left
      to right. A slot joins the current row when its top is within half a slot of the row's first
      slot; otherwise it starts a new row. Open slots stay in (item null) so positions add up. Each
      slot is {key, item}, plus w/h when over 1 and label when set.
    - `onlyWhenHeld`: hidden-when-empty slots -- {key, item, subTab} -- which appear only while held.
    - `craftingSlot`: whether the tab has one; it is left out of `rows` (never stash, never read).
    - `overlaps`: [keyA, keyB] pairs from `overlaps`, minus pairs where both slots are hidden-when-
      empty with no fixed item (Delirium's stacked map slots).
    Pure.
    """
    shown = sorted(
        (s for s in slots if not s.hidden_when_empty and s.key != _CRAFTING_SLOT),
        key=lambda s: (_page(s), s.y, s.x),
    )
    rows: list[list[Slot]] = []
    for s in shown:
        first = rows[-1][0] if rows else None
        if first is not None and first.sub_tab == s.sub_tab and s.y - first.y <= first.size / 2:
            rows[-1].append(s)
        else:
            rows.append([s])

    return {
        "rows": [
            {"subTab": row[0].sub_tab, "slots": [_view_slot(s) for s in sorted(row, key=lambda s: s.x)]}
            for row in rows
        ],
        "onlyWhenHeld": [
            {"key": s.key, "item": s.item, "subTab": s.sub_tab} for s in slots if s.hidden_when_empty
        ],
        "craftingSlot": any(s.key == _CRAFTING_SLOT for s in slots),
        "overlaps": [[a.key, b.key] for a, b in overlaps(slots) if not (_stacked(a) and _stacked(b))],
    }


def _page(s: Slot) -> int:
    return -1 if s.sub_tab is None else s.sub_tab


def _stacked(s: Slot) -> bool:
    """A slot the game fills on demand: shown only while held, with no fixed item."""
    return s.hidden_when_empty and s.item is None


def _view_slot(s: Slot) -> dict[str, Any]:
    out: dict[str, Any] = {"key": s.key, "item": s.item}
    if s.w > 1 or s.h > 1:
        out["w"], out["h"] = s.w, s.h
    if s.label:
        out["label"] = s.label
    return out


@functools.lru_cache(maxsize=None)
def load_snapshot(version: str) -> dict[str, Any] | None:
    """The committed snapshot for a version like '0_5_5', or None if none (or the version is malformed)."""
    if not _VERSION_RE.fullmatch(version):
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


def stash_layout(tab: str) -> dict[str, Any]:
    """`reading_view` of `tab` from the newest snapshot, plus tab, version, patch ('0.5.5'), and source.

    An unknown tab or no snapshot returns {"valid": False, "error", "note"}, like parse_pob_code.
    """
    if tab not in TABS:
        return {"valid": False, "error": f"unknown stash tab {tab!r}", "note": f"Use one of: {', '.join(TABS)}."}
    version = latest_version()
    snapshot = load_snapshot(version) if version else None
    if snapshot is None:
        return {"valid": False, "error": "no stash-layout snapshot is installed",
                "note": "Regenerate one with `python -m poe2_mcp.stashlayout` (see CONTRIBUTING.md)."}
    return {
        "tab": tab,
        "version": version,
        "patch": version.replace("_", "."),
        "source": snapshot["source"],
        **reading_view([_slot_from_json(d) for d in snapshot["tabs"][tab]]),
    }


def _data_dir():
    return resources.files("poe2_mcp").joinpath("data")


def _slot_from_json(d: Mapping[str, Any]) -> Slot:
    return Slot(
        key=d["key"], item=d["item"], x=d["x"], y=d["y"], w=d["w"], h=d["h"], size=d["size"],
        hidden_when_empty=d["hiddenWhenEmpty"], sub_tab=d["subTab"], group=d["group"], label=d["label"],
    )


def _slot_json(s: Slot) -> dict[str, object]:
    return {
        "key": s.key, "item": s.item, "x": s.x, "y": s.y, "w": s.w, "h": s.h, "size": s.size,
        "hiddenWhenEmpty": s.hidden_when_empty, "subTab": s.sub_tab, "group": s.group, "label": s.label,
    }


def render_snapshot(tabs: Mapping[str, Sequence[Slot]], version: str, source: str) -> str:
    """The snapshot JSON text: version, source, then each tab's slots one per line, tabs in TABS
    order (so a per-patch regeneration reads as a small diff). Pure; ends with a newline.
    """
    blocks = []
    for tab in TABS:
        lines = [f"    {json.dumps(_slot_json(s), ensure_ascii=False)}" for s in tabs[tab]]
        blocks.append(f"  {json.dumps(tab)}: [\n" + ",\n".join(lines) + "\n  ]")
    return (
        "{\n"
        f'"version": {json.dumps(version)},\n'
        f'"source": {json.dumps(source)},\n'
        '"tabs": {\n' + ",\n".join(blocks) + "\n}\n}\n"
    )


def _read_csv(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(argv: list[str]) -> None:
    """CLI: stashlayout <csv dir> <version> <source note> <out.json> -- writes the snapshot file.

    Reads `<Tab>StashTabLayout.csv` for each of TABS plus `BaseItemTypes.csv` from the export's CSV
    folder. Writes the file itself (UTF-8, no BOM, LF) instead of printing for a shell redirect:
    Windows PowerShell 5.1's `>` would write UTF-16. Prints a per-tab summary, overlaps included,
    for the person regenerating to check.
    """
    if len(argv) != 4:
        sys.exit("usage: python -m poe2_mcp.stashlayout <csv dir> <version> <source note> <out.json>")
    folder, version, source, out = argv
    names = {int(r["rownum"]): r["Name"] for r in _read_csv(os.path.join(folder, "BaseItemTypes.csv"))}
    tabs = {
        tab: normalize(tab, _read_csv(os.path.join(folder, f"{tab.capitalize()}StashTabLayout.csv")), names)
        for tab in TABS
    }
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_snapshot(tabs, version, source))
    for tab, slots in tabs.items():
        pairs = overlaps(slots)
        print(f"{tab}: {len(slots)} slots, {len(pairs)} overlapping pairs")


if __name__ == "__main__":
    main(sys.argv[1:])
