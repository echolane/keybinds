from __future__ import annotations

from dataclasses import dataclass, field, replace, is_dataclass
from enum import Enum, auto
from typing import Callable, Optional, Union, Sequence, Set, Any

Callback = Callable[[], None]
Predicate = Callable[[Any, Any], bool]


class Trigger(Enum):
    """When to fire the callback."""
    ON_PRESS = auto()
    ON_RELEASE = auto()
    ON_CLICK = auto()
    ON_HOLD = auto()
    ON_REPEAT = auto()
    ON_DOUBLE_TAP = auto()
    ON_CHORD_COMPLETE = auto()
    ON_CHORD_RELEASED = auto()
    ON_SEQUENCE = auto()


class SuppressPolicy(Enum):
    """Whether/when to stop input from reaching Windows/other apps."""
    NEVER = auto()
    ALWAYS = auto()
    WHEN_MATCHED = auto()
    WHILE_ACTIVE = auto()
    WHILE_EVALUATING = auto()


class ChordPolicy(Enum):
    """How to treat extra keys while matching a chord."""
    RELAXED = auto()
    STRICT = auto()
    IGNORE_EXTRA_MODIFIERS = auto()


class OrderPolicy(Enum):
    """Whether key press order matters."""
    ANY = auto()
    STRICT = auto()
    STRICT_RECOVERABLE = auto()


class InjectedPolicy(Enum):
    """How to handle injected (synthetic) input events."""
    ALLOW = auto()    # process both physical and injected
    IGNORE = auto()   # ignore injected completely (treat as non-existent)
    ONLY = auto()     # react only to injected events


class FocusPolicy(Enum):
    """What to do when the window loses focus."""
    CANCEL_ON_BLUR = auto()
    PAUSE_ON_BLUR = auto()


@dataclass(frozen=True)
class Timing:
    chord_timeout_ms: int = 350
    debounce_ms: int = 0
    hold_ms: int = 350
    repeat_delay_ms: int = 350
    repeat_interval_ms: int = 60
    double_tap_window_ms: int = 300
    window_focus_cache_ms: int = 50
    cooldown_ms: int = 0


@dataclass(frozen=True)
class Constraints:
    chord_policy: ChordPolicy = ChordPolicy.IGNORE_EXTRA_MODIFIERS
    order_policy: OrderPolicy = OrderPolicy.ANY
    allow_os_key_repeat: bool = False
    max_fires: Optional[int] = None
    ignore_keys: Set[int] = field(default_factory=set)


@dataclass(frozen=True)
class Checks:
    predicates: Sequence[Predicate] = field(default_factory=tuple)

    def __iter__(self):
        return iter(self.predicates)

    @classmethod
    def coerce(cls, value: Union[Checks, Sequence[Predicate], Predicate, None]) -> Checks:
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if callable(value):
            return cls((value,))
        return cls(tuple(value))


@dataclass(frozen=True)
class BindConfig:
    trigger: Trigger = Trigger.ON_PRESS

    suppress: SuppressPolicy = SuppressPolicy.NEVER
    injected: InjectedPolicy = InjectedPolicy.ALLOW
    focus: FocusPolicy = FocusPolicy.CANCEL_ON_BLUR

    timing: Timing = field(default_factory=Timing)
    constraints: Constraints = field(default_factory=Constraints)
    checks: Checks = field(default_factory=Checks)

    def __post_init__(self):
        object.__setattr__(self, "checks", Checks.coerce(self.checks))


class MouseButton(Enum):
    LEFT = auto()
    RIGHT = auto()
    MIDDLE = auto()
    X1 = auto()
    X2 = auto()


@dataclass(frozen=True)
class MouseBindConfig:
    trigger: Trigger = Trigger.ON_CLICK

    suppress: SuppressPolicy = SuppressPolicy.NEVER
    injected: InjectedPolicy = InjectedPolicy.ALLOW
    focus: FocusPolicy = FocusPolicy.CANCEL_ON_BLUR

    timing: Timing = field(default_factory=Timing)
    constraints: Constraints = field(default_factory=Constraints)
    checks: Checks = field(default_factory=Checks)

    def __post_init__(self):
        object.__setattr__(self, "checks", Checks.coerce(self.checks))


# =========================================================
# Defaults used to detect "unset" fields during soft merge
# =========================================================

_DEFAULT_BIND = BindConfig()
_DEFAULT_MOUSE = MouseBindConfig()
_DEFAULT_TIMING = Timing()
_DEFAULT_CONSTRAINTS = Constraints()
_DEFAULT_CHECKS = Checks()


# =========================================================
# Dataclass merge helpers
# =========================================================

def _merge_dc_soft(lhs, rhs, default_obj):
    """
    Recursively merge dataclasses in "soft" mode.

    A field from rhs is applied only if it differs from the default value.
    This allows rhs to behave like a patch.
    """
    out = lhs

    for name in default_obj.__dataclass_fields__.keys():
        lval = getattr(lhs, name)
        rval = getattr(rhs, name)
        dval = getattr(default_obj, name)

        # Recurse into nested dataclasses
        if is_dataclass(lval) and is_dataclass(rval) and is_dataclass(dval):
            out = replace(out, **{name: _merge_dc_soft(lval, rval, dval)})
            continue

        # Apply only non-default values
        if rval != dval:
            out = replace(out, **{name: rval})

    return out


def _merge_dc_hard(lhs, rhs):
    """
    Recursively merge dataclasses in "hard" mode.

    All fields from rhs overwrite lhs, including default values.
    This behaves like a full override.
    """
    out = lhs

    for name in lhs.__dataclass_fields__.keys():
        lval = getattr(lhs, name)
        rval = getattr(rhs, name)

        if is_dataclass(lval) and is_dataclass(rval):
            out = replace(out, **{name: _merge_dc_hard(lval, rval)})
        else:
            out = replace(out, **{name: rval})

    return out


# =========================================================
# BindConfig merge logic
# =========================================================

def merge_bind_soft(lhs: BindConfig, rhs: BindConfig) -> BindConfig:
    """
    Soft merge for BindConfig.
    Only non-default fields from rhs are applied.
    """
    out = lhs

    if rhs.trigger != _DEFAULT_BIND.trigger:
        out = replace(out, trigger=rhs.trigger)

    if rhs.suppress != _DEFAULT_BIND.suppress:
        out = replace(out, suppress=rhs.suppress)

    if rhs.injected != _DEFAULT_BIND.injected:
        out = replace(out, injected=rhs.injected)

    if rhs.focus != _DEFAULT_BIND.focus:
        out = replace(out, focus=rhs.focus)

    out = replace(out, timing=_merge_dc_soft(out.timing, rhs.timing, _DEFAULT_TIMING))
    out = replace(out, constraints=_merge_dc_soft(out.constraints, rhs.constraints, _DEFAULT_CONSTRAINTS))
    out = replace(out, checks=_merge_dc_soft(out.checks, rhs.checks, _DEFAULT_CHECKS))

    return out


def merge_bind_hard(lhs: BindConfig, rhs: BindConfig) -> BindConfig:
    """
    Hard merge for BindConfig.
    All fields from rhs overwrite lhs.
    """
    return _merge_dc_hard(lhs, rhs)


# =========================================================
# MouseBindConfig merge logic
# =========================================================

def merge_mouse_soft(lhs: MouseBindConfig, rhs: MouseBindConfig) -> MouseBindConfig:
    """
    Soft merge for MouseBindConfig.
    Only non-default fields from rhs are applied.
    """
    out = lhs

    if rhs.trigger != _DEFAULT_MOUSE.trigger:
        out = replace(out, trigger=rhs.trigger)

    if rhs.suppress != _DEFAULT_MOUSE.suppress:
        out = replace(out, suppress=rhs.suppress)

    if rhs.injected != _DEFAULT_MOUSE.injected:
        out = replace(out, injected=rhs.injected)

    if rhs.focus != _DEFAULT_MOUSE.focus:
        out = replace(out, focus=rhs.focus)

    out = replace(out, timing=_merge_dc_soft(out.timing, rhs.timing, _DEFAULT_TIMING))
    out = replace(out, constraints=_merge_dc_soft(out.constraints, rhs.constraints, _DEFAULT_CONSTRAINTS))
    out = replace(out, checks=_merge_dc_soft(out.checks, rhs.checks, _DEFAULT_CHECKS))

    return out


def merge_mouse_hard(lhs: MouseBindConfig, rhs: MouseBindConfig) -> MouseBindConfig:
    """
    Hard merge for MouseBindConfig.
    All fields from rhs overwrite lhs.
    """
    return _merge_dc_hard(lhs, rhs)


# =========================================================
# Operator sugar
#
# +  -> soft merge (patch semantics)
# |  -> hard merge (full override semantics)
# =========================================================

def _bind_add(self: BindConfig, other: BindConfig) -> BindConfig:
    if not isinstance(other, BindConfig):
        return NotImplemented
    return merge_bind_soft(self, other)


def _bind_or(self: BindConfig, other: BindConfig) -> BindConfig:
    if not isinstance(other, BindConfig):
        return NotImplemented
    return merge_bind_hard(self, other)


def _mouse_add(self: MouseBindConfig, other: MouseBindConfig) -> MouseBindConfig:
    if not isinstance(other, MouseBindConfig):
        return NotImplemented
    return merge_mouse_soft(self, other)


def _mouse_or(self: MouseBindConfig, other: MouseBindConfig) -> MouseBindConfig:
    if not isinstance(other, MouseBindConfig):
        return NotImplemented
    return merge_mouse_hard(self, other)


BindConfig.__add__ = _bind_add          # type: ignore[attr-defined]
BindConfig.__or__ = _bind_or           # type: ignore[attr-defined]
MouseBindConfig.__add__ = _mouse_add   # type: ignore[attr-defined]
MouseBindConfig.__or__ = _mouse_or     # type: ignore[attr-defined]
