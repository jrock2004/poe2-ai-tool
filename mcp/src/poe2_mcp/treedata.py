"""Passive-tree names for parse_pob_code, from a committed snapshot of PoB2's tree data.

A PoB export carries allocated node *ids* only; names live in Path of Building PoE2's
`src/TreeData/<version>/tree.lua` (MIT-licensed; the underlying tree data is GGG's). That file is a
Lua table literal, so this module holds a small parser for exactly that subset and the extraction
into a compact JSON snapshot -- notables, keystones, and every ascendancy node; ordinary small nodes
are counted by the parser, not named. Regenerate per patch:

    python -m poe2_mcp.treedata path/to/tree.lua 0_5 "<source note>" src/poe2_mcp/data/tree_0_5.json

When Path of Building hasn't shipped a patch's tree yet, pass GGG's own export instead
(grindinggear/poe2-skilltree-export, `data.json`, published per patch): `from_ggg_export` reads it
into the same shape, and the snapshot comes out the same way. Regenerate from tree.lua once Path of
Building ships it.

Build-time only: nothing here touches the network, and runtime reads only the committed JSON.
"""
from __future__ import annotations

import functools
import json
import re
import sys
from importlib import resources
from typing import Any

_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<str>"(?:[^"\\]|\\.)*")
      | (?P<num>-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)
      | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<sym>[{}\[\]=,])
    )""",
    re.VERBOSE,
)
_VERSION_RE = re.compile(r"\d+_\d+")
_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r"}
# GGG's display markup in stat text: "<underline>{Fire Spell on Hit}", "[EnergyShield|Energy Shield]", "[Rune]".
_DISPLAY_TAG_RE = re.compile(r"<[^>]*>\{([^}]*)\}")
_DISPLAY_LINK_RE = re.compile(r"\[([^\]|]*)(?:\|([^\]]*))?\]")


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos, end = 0, len(text.rstrip())
    while pos < end:
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ValueError(f"Unexpected input at offset {pos}: {text[pos:pos + 20]!r}")
        kind = m.lastgroup
        assert kind is not None
        tokens.append((kind, m.group(kind)))
        pos = m.end()
    return tokens


def _unescape(literal: str) -> str:
    def sub(m: re.Match[str]) -> str:
        ch = m.group(1)
        if ch not in _ESCAPES:
            raise ValueError(f"Unsupported string escape: \\{ch}")
        return _ESCAPES[ch]

    return re.sub(r"\\(.)", sub, literal[1:-1], flags=re.DOTALL)


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self._tokens = tokens
        self._i = 0

    def peek(self) -> tuple[str, str] | None:
        return self._tokens[self._i] if self._i < len(self._tokens) else None

    def next(self) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise ValueError("Unexpected end of input")
        self._i += 1
        return tok

    def expect(self, sym: str) -> None:
        tok = self.next()
        if tok != ("sym", sym):
            raise ValueError(f"Expected {sym!r}, got {tok[1]!r}")

    def at_end(self) -> bool:
        return self.peek() is None

    def value(self) -> Any:
        kind, text = self.next()
        if kind == "sym" and text == "{":
            return self.table()
        if kind == "str":
            return _unescape(text)
        if kind == "num":
            return float(text) if any(c in text for c in ".eE") else int(text)
        if kind == "name" and text in ("true", "false"):
            return text == "true"
        raise ValueError(f"Unsupported value {text!r}")

    def table(self) -> Any:
        entries: dict[Any, Any] = {}
        next_index = 1
        while self.peek() != ("sym", "}"):
            tok = self.peek()
            after = self._tokens[self._i + 1] if self._i + 1 < len(self._tokens) else None
            if tok is not None and tok[0] == "name" and after == ("sym", "="):
                key: Any = self.next()[1]
                self.expect("=")
            elif tok == ("sym", "["):
                self.next()
                key = self.value()
                self.expect("]")
                self.expect("=")
            else:  # positional entry
                key, next_index = next_index, next_index + 1
            entries[key] = self.value()
            if self.peek() == ("sym", ","):
                self.next()
            elif self.peek() != ("sym", "}"):
                raise ValueError(f"Expected ',' or '}}', got {self.next()[1]!r}")
        self.expect("}")
        if list(entries) and set(entries) == set(range(1, len(entries) + 1)):
            return [entries[i] for i in range(1, len(entries) + 1)]
        return entries or []


def parse_lua_table(text: str) -> Any:
    """Parse a Lua table literal (optionally prefixed by `return`) into Python values.

    Supports the subset tree.lua uses: tables with `name=`, `[number]=`, and `["string"]=` keys;
    double-quoted strings with backslash escapes; integers and decimals (incl. negative); true/false.
    A table whose keys are exactly 1..n becomes a list (an empty table becomes []); any other table
    becomes a dict (number keys stay ints). Raises ValueError on anything outside that subset.
    """
    parser = _Parser(_tokenize(text))
    if parser.peek() == ("name", "return"):
        parser.next()
    result = parser.value()
    if not parser.at_end():
        raise ValueError(f"Trailing input after the table: {parser.next()[1]!r}")
    return result


def _clean_stat_line(line: str) -> str:
    """One line of GGG stat text as tree.lua has it: display markup and a leading bullet removed."""
    line = _DISPLAY_TAG_RE.sub(lambda m: m.group(1), line)
    line = _DISPLAY_LINK_RE.sub(lambda m: m.group(2) or m.group(1), line)
    return line.lstrip("•").lstrip()


def from_ggg_export(data: dict[str, Any]) -> dict[str, Any]:
    """Read GGG's tree export (grindinggear/poe2-skilltree-export, data.json) into the shape
    parse_lua_table gives for tree.lua -- the fields extraction reads -- so either source makes the
    same snapshot. Pure. What it smooths over:

    - Ascendancies are named only under `classes`. A start node carries an internal name, so it takes
      its ascendancy's name, as in tree.lua.
    - Nodes of an ascendancy with no name there are placeholders for one not in the game yet: dropped.
    - Stat text carries display markup and several lines to one string: cleaned and split.
    - Class starts are `classStartIndex`, free nodes `isFree`; ids are string keys, plus a `root`
      entry with no `skill`.

    A node GGG leaves unnamed stays unnamed -- borrowing an older snapshot's name could be wrong if
    GGG reused the id.
    """
    ascendancies = {
        a["id"]: a["name"]
        for c in data.get("classes") or []
        for a in c.get("ascendancies") or []
        if a.get("name")
    }
    nodes: dict[int, dict[str, Any]] = {}
    for node in (data.get("nodes") or {}).values():
        if "skill" not in node:
            continue  # the `root` entry
        ascendancy_id = node.get("ascendancyId")
        ascendancy = ascendancies.get(ascendancy_id)
        if ascendancy_id and not ascendancy:
            continue  # a placeholder for an ascendancy not in the game yet
        nodes[int(node["skill"])] = {
            "name": ascendancy if node.get("isAscendancyStart") else node.get("name"),
            "ascendancyName": ascendancy,
            "isKeystone": node.get("isKeystone"),
            "isNotable": node.get("isNotable"),
            "isMultipleChoiceOption": node.get("isMultipleChoiceOption"),
            "isAscendancyStart": node.get("isAscendancyStart"),
            "classesStart": node.get("classStartIndex") is not None,
            "isFreeAllocate": node.get("isFree"),
            "stats": [_clean_stat_line(line) for stat in node.get("stats") or [] for line in stat.split("\n")],
        }
    return {"nodes": nodes}


def extract_named_nodes(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Select the nodes worth naming from a parsed tree.lua: keystones, notables, ascendancy nodes.

    Returns {str(node id): {name, kind, ascendancy, stats}} where kind is the first that applies of
    'keystone' | 'notable' | 'choice' (an ascendancy choice option -- what the player picked under a
    choice-parent notable) | 'small'. 'choice' and 'small' only appear for ascendancy nodes, since
    ordinary small nodes are excluded. ascendancy is the ascendancy name or None, and stats is a list
    of stat lines ([] if none).
    """
    named: dict[str, dict[str, Any]] = {}
    nodes = tree.get("nodes") or {}
    for node_id in sorted(nodes):  # stable order -> reviewable diffs between patches
        node = nodes[node_id]
        ascendancy = node.get("ascendancyName")
        if not (node.get("isKeystone") or node.get("isNotable") or ascendancy):
            continue
        if node.get("isKeystone"):
            kind = "keystone"
        elif node.get("isNotable"):
            kind = "notable"
        elif node.get("isMultipleChoiceOption"):
            kind = "choice"
        else:
            kind = "small"
        stats = node.get("stats") or []
        named[str(node_id)] = {
            "name": node.get("name"),
            "kind": kind,
            "ascendancy": ascendancy,
            "stats": list(stats.values()) if isinstance(stats, dict) else list(stats),
        }
    return named


def extract_uncounted(tree: dict[str, Any]) -> list[int]:
    """Allocated-but-free node ids, sorted: what PoB's CountAllocNodes skips when counting points.

    Class starts (`classesStart`), ascendancy starts (`isAscendancyStart`), ascendancy choice options
    (`isMultipleChoiceOption` -- the parent costs the point, the chosen option doesn't), and
    `isFreeAllocate` nodes. They appear in a PoB export's `nodes` but cost no passive point.
    """
    nodes = tree.get("nodes") or {}
    return sorted(
        node_id
        for node_id, node in nodes.items()
        if node.get("classesStart")
        or node.get("isAscendancyStart")
        or node.get("isMultipleChoiceOption")
        or node.get("isFreeAllocate")
    )


@functools.lru_cache(maxsize=None)
def load_snapshot(version: str | None) -> dict[str, Any] | None:
    """The committed snapshot for a tree version -- {"nodes", "uncounted", ...} -- or None if none.

    `version` comes from pasted PoB XML, so it is validated (digits_digits, e.g. '0_5') before it
    becomes part of a file path; anything else -- including suffixed variants -- returns None, and
    the caller falls back to ids only. Loaded once per version and cached.
    """
    if not version or not _VERSION_RE.fullmatch(version):
        return None
    path = resources.files("poe2_mcp").joinpath("data").joinpath(f"tree_{version}.json")  # 3.10-safe
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def render_snapshot(tree: dict[str, Any], version: str, source: str) -> str:
    """The snapshot JSON text for a parsed tree (tree.lua, or GGG's export via from_ggg_export):
    treeVersion, source, uncounted, then one named node per line (so a per-patch regeneration reads as
    a small diff). Pure; ends with a newline.
    """
    lines = [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}"
             for k, v in extract_named_nodes(tree).items()]
    return (
        "{\n"
        f'"treeVersion": {json.dumps(version)},\n'
        f'"source": {json.dumps(source)},\n'
        f'"uncounted": {json.dumps(extract_uncounted(tree))},\n'
        '"nodes": {\n' + ",\n".join(lines) + "\n}\n}\n"
    )


def main(argv: list[str]) -> None:
    """CLI: treedata <tree.lua | data.json> <treeVersion> <source note> <out.json> -- writes the
    snapshot file. A .json input is read as GGG's tree export, anything else as tree.lua.

    Writes the file itself (UTF-8, no BOM, LF) instead of printing for a shell redirect: Windows
    PowerShell 5.1's `>` would write UTF-16, and text mode on Windows would turn LF into CRLF.
    """
    if len(argv) != 4:
        sys.exit("usage: python -m poe2_mcp.treedata <tree.lua | data.json> <treeVersion> <source note> <out.json>")
    path, version, source, out = argv
    with open(path, encoding="utf-8") as f:
        text = f.read()
    tree = from_ggg_export(json.loads(text)) if path.lower().endswith(".json") else parse_lua_table(text)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_snapshot(tree, version, source))


if __name__ == "__main__":
    main(sys.argv[1:])
