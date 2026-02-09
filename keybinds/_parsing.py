from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set, Tuple

from ._constants import _MOD_GROUPS, SPECIAL_KEYS


def _token_to_vk_group(token: str) -> Set[int]:
    t = token.strip().lower()
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
    groups: Tuple[frozenset[int], ...]  # each element: acceptable vk codes
    allowed_union: frozenset[int]  # union(groups)


def parse_chord(expr: str) -> _ChordSpec:
    parts = [p.strip() for p in expr.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty chord")

    groups: List[frozenset[int]] = []
    union: Set[int] = set()
    for p in parts:
        g = frozenset(_token_to_vk_group(p))
        groups.append(g)
        union |= set(g)
    return _ChordSpec(tuple(groups), frozenset(union))


def parse_key_expr(expr: str) -> Tuple[_ChordSpec, ...]:
    steps = [s.strip() for s in expr.split(",") if s.strip()]
    if not steps:
        raise ValueError("empty key expression")
    return tuple(parse_chord(step) for step in steps)
