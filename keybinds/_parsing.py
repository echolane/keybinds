from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set, Tuple, FrozenSet

from ._constants import _MOD_GROUPS, SPECIAL_KEYS


def _normalize_token(t: str) -> str:
    t = t.strip().lower()
    t = " ".join(t.split())  # remove extra spaces
    if t != "-":
        t = t.replace("-", " ")

    aliases = {
        "left shift": "lshift",
        "right shift": "rshift",
        "left ctrl": "lctrl",
        "left control": "lctrl",
        "right ctrl": "rctrl",
        "right control": "rctrl",
        "left alt": "lalt",
        "right alt": "ralt",
    }
    return aliases.get(t, t.replace(" ", ""))


def _token_to_vk_group(token: str) -> Set[int]:
    t = _normalize_token(token)
    if not t:
        raise ValueError("empty key token")

    if t in _MOD_GROUPS:
        return set(_MOD_GROUPS[t])

    if t in SPECIAL_KEYS:
        return {SPECIAL_KEYS[t]}

    # single char letters/digits
    if len(t) == 1:
        c = t.upper()
        if "A" <= c <= "Z":
            return {ord(c)}  # VK_A..VK_Z
        if "0" <= c <= "9":
            return {ord(c)}  # VK_0..VK_9

    raise ValueError(f"Unknown key token: {token!r}")


@dataclass(frozen=True)
class _ChordSpec:
    groups: Tuple[FrozenSet[int], ...]  # each element: acceptable vk codes
    allowed_union: FrozenSet[int]  # union(groups)


def parse_chord(expr: str) -> _ChordSpec:
    expr = expr.strip()
    if not expr:
        raise ValueError("empty chord")

    parts = [p.strip() for p in expr.split("+")]
    if any(not p for p in parts):
        raise ValueError(f"invalid chord syntax: {expr!r}")

    groups: List[FrozenSet[int]] = []
    union: Set[int] = set()

    for p in parts:
        try:
            g = frozenset(_token_to_vk_group(p))
        except ValueError as e:
            raise ValueError(f"unknown key token: {p!r}") from e

        groups.append(g)
        union |= g

    return _ChordSpec(tuple(groups), frozenset(union))


def parse_key_expr(expr: str) -> Tuple[_ChordSpec, ...]:
    expr = expr.strip()
    if not expr:
        raise ValueError("empty key expression")

    steps = [s.strip() for s in expr.split(",")]
    if any(not s for s in steps):
        raise ValueError(f"invalid key expression syntax: {expr!r}")

    try:
        return tuple(parse_chord(step) for step in steps)
    except ValueError as e:
        raise ValueError(f"invalid key expression: {expr!r}") from e
