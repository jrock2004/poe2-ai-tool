"""Passive-tree names for parse_pob_code, from a committed snapshot of PoB2's tree data.

A PoB export carries allocated node *ids* only; names live in Path of Building PoE2's
`src/TreeData/<version>/tree.lua` (MIT-licensed; the underlying tree data is GGG's). That file is a
Lua table literal, so this module holds a small parser for exactly that subset and the extraction
into a compact JSON snapshot -- notables, keystones, and every ascendancy node; ordinary small nodes
are counted by the parser, not named. Regenerate per patch:

    python -m poe2_mcp.treedata path/to/tree.lua 0_5 "<source note>" > src/poe2_mcp/data/tree_0_5.json

Build-time only: nothing here touches the network, and runtime reads only the committed JSON.
"""
from __future__ import annotations

import json
import re
import sys
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
_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r"}


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


def extract_named_nodes(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Select the nodes worth naming from a parsed tree.lua: keystones, notables, ascendancy nodes.

    Returns {str(node id): {name, kind, ascendancy, stats}} where kind is 'keystone' | 'notable' |
    'small' ('small' only appears for ascendancy nodes -- ordinary small nodes are excluded),
    ascendancy is the ascendancy name or None, and stats is a list of stat lines ([] if none).
    """
    named: dict[str, dict[str, Any]] = {}
    nodes = tree.get("nodes") or {}
    for node_id in sorted(nodes):  # stable order -> reviewable diffs between patches
        node = nodes[node_id]
        ascendancy = node.get("ascendancyName")
        if not (node.get("isKeystone") or node.get("isNotable") or ascendancy):
            continue
        kind = "keystone" if node.get("isKeystone") else "notable" if node.get("isNotable") else "small"
        stats = node.get("stats") or []
        named[str(node_id)] = {
            "name": node.get("name"),
            "kind": kind,
            "ascendancy": ascendancy,
            "stats": list(stats.values()) if isinstance(stats, dict) else list(stats),
        }
    return named


def main(argv: list[str]) -> None:
    """CLI: treedata <tree.lua> <treeVersion> <source note> -> snapshot JSON on stdout."""
    if len(argv) != 3:
        sys.exit("usage: python -m poe2_mcp.treedata <tree.lua> <treeVersion> <source note>")
    path, version, source = argv
    with open(path, encoding="utf-8") as f:
        tree = parse_lua_table(f.read())
    snapshot = {"treeVersion": version, "source": source, "nodes": extract_named_nodes(tree)}
    # One node per line keeps a per-patch regeneration reviewable as a diff.
    lines = [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in snapshot["nodes"].items()]
    sys.stdout.write(
        "{\n"
        f'"treeVersion": {json.dumps(version)},\n'
        f'"source": {json.dumps(source)},\n'
        '"nodes": {\n' + ",\n".join(lines) + "\n}\n}\n"
    )


if __name__ == "__main__":
    main(sys.argv[1:])
