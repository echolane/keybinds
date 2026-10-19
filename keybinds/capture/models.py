from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple


@dataclass(frozen=True, eq=False)
class CapturedKey:
    vk: int
    scan_code: int
    token: str
    char: Optional[str]
    action: str
    is_modifier: bool
    injected: bool
    timestamp: float

    @property
    def is_printable(self) -> bool:
        return self.char is not None

    def __str__(self) -> str:
        return self.token

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            matches_token = self.token == other.lower()
            matches_char = self.char is not None and self.char == other
            if matches_token or matches_char:
                return True
            try:
                from .convert import token_to_vk

                return token_to_vk(other) == self.vk
            except (ValueError, TypeError):
                return False
        if isinstance(other, int):
            return self.vk == other
        if isinstance(other, CapturedKey):
            return self.vk == other.vk and self.action == other.action
        return NotImplemented

    __hash__ = None


@dataclass(frozen=True)
class CapturedChord:
    keys: Tuple[CapturedKey, ...]

    @property
    def physical_expr(self) -> str:
        modifiers = [key.token for key in self.keys if key.is_modifier]
        regular_keys = [key.token for key in self.keys if not key.is_modifier]
        return "+".join(modifiers + regular_keys)

    @property
    def logical_expr(self) -> str:
        parts = []
        for key in self.keys:
            if key.is_modifier or not key.char:
                parts.append(key.token)
            elif key.char in ("+", ","):
                parts.append("\\" + key.char)
            else:
                parts.append(key.char)
        return "+".join(parts)

    @property
    def tokens(self) -> Tuple[str, ...]:
        return tuple(key.token for key in self.keys)

    @property
    def vks(self) -> FrozenSet[int]:
        return frozenset(key.vk for key in self.keys)

    @property
    def modifiers(self) -> Tuple[str, ...]:
        return tuple(key.token for key in self.keys if key.is_modifier)

    def __str__(self) -> str:
        return self.physical_expr

    def __bool__(self) -> bool:
        return bool(self.keys)


@dataclass(frozen=True, eq=False)
class CapturedMouse:
    button: str
    action: str
    x: int
    y: int
    wheel_delta: int
    injected: bool
    timestamp: float

    def __str__(self) -> str:
        return self.button

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.button == other.lower()
        if isinstance(other, CapturedMouse):
            return (
                self.button,
                self.action,
                self.x,
                self.y,
                self.wheel_delta,
                self.injected,
                self.timestamp,
            ) == (
                other.button,
                other.action,
                other.x,
                other.y,
                other.wheel_delta,
                other.injected,
                other.timestamp,
            )
        return NotImplemented

    __hash__ = None
