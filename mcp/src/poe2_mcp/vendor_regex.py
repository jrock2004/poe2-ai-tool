"""Build a PoE2 vendor search-box regex from a build's wants: a curated fragment table plus a pure composer.

How the in-game search box reads a string (confirmed against poe2.re's generator and a working 247-char
string): case-insensitive; each line of the item's text is matched on its own (`^`/`$` anchor to a line);
`|` is OR inside one quoted group; a space between quoted groups is AND; a leading `!` negates the whole
group; at most 250 characters, quotes and spaces included.

The composed string is up to three ANDed groups, in this order:

    "!<hide>"   -- never highlight these item classes, or an item carrying an avoided mod
    "<want>"    -- a wanted mod, or a class wanted on any roll (e.g. every sceptre)
    "<gate>"    -- the item is in a slot the build uses, has a wanted defence, or has an any-base mod

Fragments are hand-picked, not computed: each is checked against the trade stat list in tests. Pure and
offline -- the judgment of *what* to want lives in the poe2-vendor-regex skill.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

LIMIT = 250

# Item class -> fragment matched after "Item Class: " (the composer adds the `s: ` prefix).
# Not yet checked against a list of the game's item classes -- the trade stat list doesn't carry one.
CLASSES: dict[str, str] = {
    "sceptre": "sc",
    "amulet": "am",
    "ring": "ri",
    "belt": "be",
    "wand": "wa",
    "staff": "st",
    "quarterstaff": "qua",
    "spear": "spe",
    "crossbow": "cr",
    "bow": "bow",
    "quiver": "qui",
    "one_hand_mace": "on",
    "two_hand_mace": "tw",
}

# Defence type -> fragment for its property line on the base (e.g. "Energy Shield: 32").
DEFENCES: dict[str, str] = {
    "energy_shield": "ield:",
}

# Mod -> fragment. "{n}" marks where a min_value pattern goes; a mod without it takes no min_value.
# Each is checked against the trade stat list in tests (test_vendor_regex.py, TARGETS / TRAPS).
MODS: dict[str, str] = {
    "movement_speed": "{n}% i.*mov",
    "spirit": "o sp",
    "minion_skills": "ion sk",
    "max_energy_shield": "m energy",
    "increased_energy_shield": "d energy s",
    "resistance": "% to.*res",
    "max_life": "{n} to m.*m life",
    "minion_life_recovery": "y to min",
    "charges_per_second": "ges per s",
    "flask_removes_recovery": "^removes",   # a flask downside -- meant for `avoid`
}

# "{n}" mod -> its tiers as (item level needed, highest value at that tier), ascending. The highest roll at an
# item level caps the min_value pattern -- below 100 that keeps it short; at 100+ it also matches any
# 3-digit number -- and a min_value no tier can reach at that level is reported as unreachable.
# Source: poe2db.tw embedded mod data (us/Boots_*, Gloves_int, Helmets_int, Body_Armours_*, Rings, Amulets,
# Belts, Shields_str), patch 0.5.5, regular tiers only (no essence/desecrated -- vendors don't sell them).
# Life uses the same item-level gates on every slot; slots differ only in their top tier, so this is the
# highest across slots (body armour). Refresh per patch: CONTRIBUTING.md.
TIERS: dict[str, tuple[tuple[int, int], ...]] = {
    "movement_speed": ((1, 10), (16, 15), (33, 20), (46, 25), (65, 30), (82, 35)),
    "max_life": ((1, 19), (6, 29), (16, 39), (24, 59), (33, 69), (38, 84), (46, 99), (54, 119), (60, 149),
                 (65, 174), (70, 189), (75, 199), (80, 214)),
}


@dataclass(frozen=True)
class Want:
    key: str                     # a MODS key
    min_value: int | None = None  # only for mods whose fragment has "{n}"
    any_base: bool = False       # also passes the gate: highlight it on any base the hide group allows


@dataclass(frozen=True)
class VendorRegex:
    regex: str
    length: int
    dropped: tuple[str, ...]     # Want keys left out to fit the limit, in the order they were dropped
    unreachable: tuple[str, ...]  # Want keys whose min_value no tier can roll at item_level


def build_vendor_regex(
    *,
    want: Sequence[Want],
    want_classes: Sequence[str] = (),
    hide_classes: Sequence[str] = (),
    slot_classes: Sequence[str] = (),
    slot_defences: Sequence[str] = (),
    avoid: Sequence[str] = (),
    item_level: int | None = None,
    limit: int = LIMIT,
) -> VendorRegex:
    """Compose the search string. Pure.

    `want` is highest priority first; when the string is over `limit`, wants are dropped from the end
    (from both the want and gate groups) until it fits. Classes, defences and the hide group are never
    dropped -- if they alone exceed the limit, raise ValueError. With no slot_classes and no
    slot_defences there is no gate group. `avoid` (MODS keys, any value) joins the hide group, so an
    item with an avoided mod never lights; like classes, it is never dropped. Unknown keys, or a
    min_value on a mod without "{n}", raise ValueError.

    `item_level` is the level of the items the vendor sells. Each numeric want is capped at the highest
    roll at that level (TIERS); a want whose min_value can't roll there is left out and listed in
    `unreachable`. Without it, the cap is the mod's highest roll overall, and a min_value above that
    raises ValueError.
    """
    if item_level is not None and item_level < 1:
        raise ValueError(f"item_level {item_level} must be 1 or more")
    _check(want_classes, CLASSES, "item class")
    _check(hide_classes, CLASSES, "item class")
    _check(slot_classes, CLASSES, "item class")
    _check(slot_defences, DEFENCES, "defence")
    unreachable = [w.key for w in want if not _can_roll(w, item_level)]
    want = [w for w in want if w.key not in unreachable]
    fragments = [_mod_fragment(w, item_level) for w in want]
    avoided = [_mod_fragment(Want(key)) for key in avoid]

    wants = list(zip(want, fragments))
    dropped: list[str] = []
    while True:
        regex = _compose(wants, want_classes, hide_classes, avoided, slot_classes, slot_defences)
        if len(regex) <= limit:
            return VendorRegex(regex=regex, length=len(regex), dropped=tuple(dropped),
                               unreachable=tuple(unreachable))
        if not wants:
            raise ValueError(f"classes, defences and avoided mods alone are {len(regex)} characters, over the {limit} limit")
        dropped.append(wants.pop()[0].key)


def _check(keys: Sequence[str], table: dict[str, str], kind: str) -> None:
    for key in keys:
        if key not in table:
            raise ValueError(f'unknown {kind} "{key}"; known: {", ".join(table)}')


def _top(key: str, item_level: int | None) -> int | None:
    """The highest value `key` can roll at item_level (any level if None), or None if it has no TIERS."""
    tiers = TIERS.get(key)
    if not tiers:
        return None
    return max(v for lvl, v in tiers if item_level is None or lvl <= item_level)


def _can_roll(w: Want, item_level: int | None) -> bool:
    """False only when item_level is given and no tier there reaches w.min_value."""
    if item_level is None or w.min_value is None or w.key not in TIERS:
        return True
    return w.min_value <= _top(w.key, item_level)


def _mod_fragment(w: Want, item_level: int | None = None) -> str:
    _check([w.key], MODS, "mod")
    fragment = MODS[w.key]
    if "{n}" not in fragment:
        if w.min_value is not None:
            raise ValueError(f'"{w.key}" takes no min_value')
        return fragment
    return fragment.replace("{n}", _at_least(w.min_value or 0, _top(w.key, item_level)))


def _at_least(n: int, top: int | None = None) -> str:
    """A pattern for an integer >= n, searched for anywhere in a line. Pure.

    Unanchored, so a smaller number can't match by containing a qualifying substring: every 1-2 digit
    pattern needs the whole number, and any 3+ digit number (all >= 100 > n) matches via \\d{3}.
    `top` is the highest value the mod can roll; below 100 the pattern stops there (n..top) and drops
    \\d{3}. It shortens the pattern -- it doesn't exclude values above top, which can't occur."""
    if not 0 <= n <= 99:
        raise ValueError(f"min_value {n} is outside 0-99")
    if top is not None and top <= 99:
        if n > top:
            raise ValueError(f"min_value {n} is above the highest roll, {top}")
        return _between(n, top)
    if n <= 1:
        return "\\d"
    tens, ones = divmod(n, 10)
    if tens == 0:
        return f"([{n}-9]|\\d\\d)"
    alts = [f"{tens}{_digits(ones)}"] if ones else [f"{_digits(tens)}\\d"]
    if ones and tens < 9:
        alts.append(f"{_digits(tens + 1)}\\d")
    alts.append("\\d{3}")
    return f"({'|'.join(alts)})"


def _between(lo: int, hi: int) -> str:
    """A pattern for an integer in lo..hi (both 0-99), one alternative per tens digit; whole tens in the
    middle collapse into one ("[3-5]\\d")."""
    alts: list[str] = []
    full: list[int] = []   # a run of tens digits whose ones go 0-9
    for tens in range(lo // 10, hi // 10 + 1):
        a = lo % 10 if tens == lo // 10 else 0
        b = hi % 10 if tens == hi // 10 else 9
        if tens and (a, b) == (0, 9):
            full.append(tens)
            continue
        if full:
            alts.append(f"{_span(full[0], full[-1])}\\d")
            full = []
        alts.append(f"{tens or ''}{_span(a, b)}")
    if full:
        alts.append(f"{_span(full[0], full[-1])}\\d")
    return alts[0] if len(alts) == 1 else f"({'|'.join(alts)})"


def _span(a: int, b: int) -> str:
    """A character class for one digit in a..b."""
    return str(a) if a == b else ("\\d" if (a, b) == (0, 9) else f"[{a}-{b}]")


def _digits(low: int) -> str:
    """A character class for one digit >= low."""
    return str(low) if low == 9 else ("\\d" if low == 0 else f"[{low}-9]")


def _classes(keys: Sequence[str]) -> str | None:
    if not keys:
        return None
    frags = [CLASSES[k] for k in keys]
    return f"s: {frags[0]}" if len(frags) == 1 else f"s: ({'|'.join(frags)})"


def _group(terms: list[str | None], negate: bool = False) -> str | None:
    terms = [t for t in terms if t]
    if not terms:
        return None
    return f'"{"!" if negate else ""}{"|".join(terms)}"'


def _compose(
    wants: list[tuple[Want, str]],
    want_classes: Sequence[str],
    hide_classes: Sequence[str],
    avoided: list[str],
    slot_classes: Sequence[str],
    slot_defences: Sequence[str],
) -> str:
    groups = [
        _group([_classes(hide_classes), *avoided], negate=True),
        _group([_classes(want_classes), *(f for _, f in wants)]),
    ]
    if slot_classes or slot_defences:
        groups.append(_group([
            _classes(slot_classes),
            *(DEFENCES[d] for d in slot_defences),
            *(f for w, f in wants if w.any_base),
        ]))
    return " ".join(g for g in groups if g)
