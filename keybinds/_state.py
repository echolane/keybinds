from __future__ import annotations

from dataclasses import dataclass
from typing import Set, Optional

from .types import MouseButton


@dataclass(frozen=True)
class InputState:
    # "physical" (non-injected)
    pressed_keys: Set[int]
    pressed_mouse: Set[MouseButton]

    # "all" (physical + injected). Optional to keep old call sites working.
    pressed_keys_all: Optional[Set[int]] = None
    pressed_mouse_all: Optional[Set[MouseButton]] = None

    # injected-only (synthetic). Optional.
    pressed_keys_injected: Optional[Set[int]] = None
    pressed_mouse_injected: Optional[Set[MouseButton]] = None
