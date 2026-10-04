"""Per-patch game knowledge (trials, farming, crafting): bundled copies plus local refreshes.

The bundled files ship in this package (knowledge/<topic>.md) and are what the maintainer reviewed.
`/poe2-new-league` can refresh a topic for the player through save(); that copy lands in the per-user
data dir (store.py), outside the install, so it survives updates. load() returns whichever copy is
newer by its header -- patch first, then refreshed date, ties to bundled -- so a later update that
ships newer knowledge wins over a stale local refresh on its own.

Each file starts with a machine-readable header (the prose freshness stamp below it is for readers):

    ---
    patch: 0.5.5d
    refreshed: 2026-10-04
    ---
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Literal

TOPICS = ("trials", "farming", "crafting")

_HEADER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_PATCH = re.compile(r"^(\d+(?:\.\d+)*)([a-z]?)$")


@dataclass(frozen=True)
class Stamp:
    patch: str
    refreshed: date


@dataclass(frozen=True)
class Knowledge:
    topic: str
    text: str
    source: Literal["bundled", "local"]
    stamp: Stamp


def patch_key(patch: str) -> tuple:
    """Sort key for a patch: "0.5.5d" -> ((0, 5, 5), "d"). Pure. Trailing zero parts are dropped, so
    "1.0" == "1.0.0"; a hotfix letter sorts after its base patch. Anything else raises ValueError."""
    m = _PATCH.match(patch.strip())
    if not m:
        raise ValueError(f'"{patch}" is not a patch version like 0.5.5 or 0.5.5d')
    parts = [int(p) for p in m.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return (tuple(parts), m.group(2))


def parse_stamp(text: str) -> Stamp | None:
    """The header at the very top of text, or None if it's missing or malformed. Pure."""
    m = _HEADER.match(text)
    if not m:
        return None
    fields = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    try:
        patch = fields["patch"]
        patch_key(patch)
        return Stamp(patch=patch, refreshed=date.fromisoformat(fields["refreshed"]))
    except (KeyError, ValueError):
        return None


def choose(bundled: Knowledge, local: Knowledge | None) -> Knowledge:
    """The newer copy: patch first, then refreshed date; a tie goes to bundled. Pure."""
    if local is None:
        return bundled

    def key(k: Knowledge) -> tuple:
        return (patch_key(k.stamp.patch), k.stamp.refreshed)

    return local if key(local) > key(bundled) else bundled


def _check_topic(topic: str) -> None:
    if topic not in TOPICS:
        raise ValueError(f'Unknown knowledge topic "{topic}". Topics: {", ".join(TOPICS)}')


def _local_path(topic: str, root: Path) -> Path:
    return root / "knowledge" / f"{topic}.md"


def _bundled(topic: str) -> Knowledge:
    path = resources.files("poe2_mcp").joinpath("knowledge").joinpath(f"{topic}.md")  # 3.10-safe
    text = path.read_text(encoding="utf-8")
    stamp = parse_stamp(text)
    if stamp is None:
        raise RuntimeError(f"bundled knowledge/{topic}.md has no valid header -- fix it in the repo")
    return Knowledge(topic=topic, text=text, source="bundled", stamp=stamp)


def load(topic: str, root: Path) -> Knowledge:
    """The newer of the bundled and local copies. A local copy with a bad or missing header is ignored."""
    _check_topic(topic)
    bundled = _bundled(topic)
    try:
        text = _local_path(topic, root).read_text(encoding="utf-8")
    except FileNotFoundError:
        return bundled
    stamp = parse_stamp(text)
    local = Knowledge(topic=topic, text=text, source="local", stamp=stamp) if stamp else None
    return choose(bundled, local)


def save(topic: str, text: str, root: Path) -> Knowledge:
    """Write a local refresh of topic. Raises ValueError -- writing nothing -- if the header is missing
    or bad, or if the copy isn't newer than bundled (load() would ignore it). Writes utf-8, LF."""
    _check_topic(topic)
    text = text.replace("\r\n", "\n")
    stamp = parse_stamp(text)
    if stamp is None:
        raise ValueError(
            "text must start with a header: ---, patch: <e.g. 0.6.0>, refreshed: <YYYY-MM-DD>, ---"
        )
    bundled = _bundled(topic)
    local = Knowledge(topic=topic, text=text, source="local", stamp=stamp)
    if choose(bundled, local) is not local:
        raise ValueError(
            f"{topic} refresh (patch {stamp.patch}, {stamp.refreshed}) is not newer than the bundled "
            f"copy (patch {bundled.stamp.patch}, {bundled.stamp.refreshed}); it would be ignored"
        )
    path = _local_path(topic, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return local
