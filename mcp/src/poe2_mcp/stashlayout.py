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
import json
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

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
