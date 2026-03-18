from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, List, Tuple, Union

from .._constants import _MOD_GROUPS, SPECIAL_KEYS
from .._parsing import _normalize_token


@dataclass(frozen=True)
class _LogicalVkGroup:
    vks: FrozenSet[int]


@dataclass(frozen=True)
class _LogicalCharGroup:
    char: str


LogicalGroup = Union[_LogicalVkGroup, _LogicalCharGroup]


@dataclass(frozen=True)
class _LogicalChordSpec:
    groups: Tuple[LogicalGroup, ...]
    allowed_vk_union: FrozenSet[int]
    allowed_chars: FrozenSet[str]


_ESCAPE_MAP = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "\\": "\\",
    "+": "+",
    ",": ",",
}


def _unescape_token(value: str) -> str:
    out: List[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= len(value):
            raise ValueError("dangling escape in logical token")
        nxt = value[i + 1]
        out.append(_ESCAPE_MAP.get(nxt, nxt))
        i += 2
    return "".join(out)


def _split_top_level(expr: str, sep: str) -> List[str]:
    parts: List[str] = []
    buf: List[str] = []
    escape = False

    for ch in expr:
        if escape:
            buf.append(ch)
            escape = False
            continue
        if ch == "\\":
            buf.append(ch)
            escape = True
            continue
        if ch == sep:
            parts.append("".join(buf))
            buf.clear()
            continue
        buf.append(ch)

    if escape:
        raise ValueError(f"dangling escape in expression: {expr!r}")

    parts.append("".join(buf))
    return parts


def _escape_char_token(ch: str) -> str:
    if len(ch) != 1:
        raise ValueError("expected a single character")
    if ch == "\\":
        return r"\\"
    if ch == "+":
        return r"\+"
    if ch == ",":
        return r"\,"
    if ch == "\n":
        return r"\n"
    if ch == "\r":
        return r"\r"
    if ch == "\t":
        return r"\t"
    return ch


def _token_to_logical_group(token: str) -> LogicalGroup:
    raw = token
    if raw == "":
        raise ValueError("empty key token")

    stripped = raw.strip()

    # LogicalBind is character-first: any single resulting character should be
    # treated as a logical character, not as a physical OEM VK key. Named tokens
    # like "space", "enter", "comma", "plus" still map to VK groups.
    unescaped_raw = _unescape_token(raw)
    if len(unescaped_raw) == 1:
        return _LogicalCharGroup(unescaped_raw)

    if stripped:
        unescaped_stripped = _unescape_token(stripped)
        norm = _normalize_token(unescaped_stripped)
        if norm in _MOD_GROUPS:
            return _LogicalVkGroup(frozenset(_MOD_GROUPS[norm]))
        if norm in SPECIAL_KEYS:
            return _LogicalVkGroup(frozenset({SPECIAL_KEYS[norm]}))
        if len(unescaped_stripped) == 1:
            return _LogicalCharGroup(unescaped_stripped)

    raise ValueError(f"Unknown logical key token: {token!r}")


def parse_logical_chord(expr: str) -> _LogicalChordSpec:
    expr = expr.strip()
    if not expr:
        raise ValueError("empty chord")

    parts = _split_top_level(expr, "+")
    if any(p == "" for p in parts):
        raise ValueError(f"invalid chord syntax: {expr!r}")

    groups: List[LogicalGroup] = []
    allowed_vks = set()
    allowed_chars = set()

    for part in parts:
        g = _token_to_logical_group(part)
        groups.append(g)
        if isinstance(g, _LogicalVkGroup):
            allowed_vks.update(g.vks)
        else:
            allowed_chars.add(g.char)

    return _LogicalChordSpec(tuple(groups), frozenset(allowed_vks), frozenset(allowed_chars))


def parse_logical_expr(expr: str) -> Tuple[_LogicalChordSpec, ...]:
    expr = expr.strip()
    if not expr:
        raise ValueError("empty logical expression")

    steps = _split_top_level(expr, ",")
    if any(s == "" for s in steps):
        raise ValueError(f"invalid logical expression syntax: {expr!r}")

    try:
        return tuple(parse_logical_chord(step) for step in steps)
    except ValueError as exc:
        raise ValueError(f"invalid logical expression: {expr!r}") from exc


def text_to_logical_expr(text: str) -> str:
    if not text:
        raise ValueError("text must not be empty")
    return ",".join(_escape_char_token(ch) for ch in text)


__all__ = [
    "_LogicalVkGroup",
    "_LogicalCharGroup",
    "_LogicalChordSpec",
    "parse_logical_chord",
    "parse_logical_expr",
    "text_to_logical_expr",
]
