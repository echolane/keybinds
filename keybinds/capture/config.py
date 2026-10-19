from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Callable, Iterable, Optional, Union

from ..types import InjectedPolicy
from .models import CapturedKey, CapturedMouse


class ChordEndPolicy(Enum):
    FIRST_NON_MODIFIER = "first_non_modifier"
    ALL_RELEASED = "all_released"
    FIRST_RELEASED = "first_released"


class InterceptAction(IntEnum):
    PASS = 0
    SUPPRESS = 1


SuppressFilter = Union[
    bool,
    Iterable[str],
    Callable[[Union[CapturedKey, CapturedMouse]], bool],
]


@dataclass
class CaptureConfig:
    end_policy: ChordEndPolicy = ChordEndPolicy.FIRST_NON_MODIFIER
    side_specific_modifiers: bool = False
    cancel_key: Optional[str] = "esc"
    pause_binds: bool = True
    ignore_already_pressed: bool = True
    include_repeats: bool = False
    respect_caps_lock: bool = True
    injected: InjectedPolicy = InjectedPolicy.IGNORE
    hwnd: Optional[Union[int, str]] = None


@dataclass
class InterceptConfig:
    hook_timeout: float = 0.08
    default_action: InterceptAction = InterceptAction.PASS
    pause_binds: bool = False
    injected: InjectedPolicy = InjectedPolicy.ALLOW
    respect_caps_lock: bool = True
    hwnd: Optional[Union[int, str]] = None
