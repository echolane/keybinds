from __future__ import annotations

from dataclasses import dataclass, field, replace, is_dataclass
from enum import Enum, auto
from typing import Callable, Optional, Union, Sequence, Set, Any, TypeVar, Awaitable


SyncCallback = Callable[[], None]
AsyncCallback = Callable[[], Awaitable[None]]
Callback = Union[SyncCallback, AsyncCallback]

Predicate = Callable[[Any, Any], bool]
CheckPredicate = Predicate


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


class TextBoundaryPolicy(Enum):
    """How text-based logical matchers treat word boundaries."""
    ANYWHERE = auto()
    WORD_START = auto()
    WORD_END = auto()
    WHOLE_WORD = auto()


class TextBackspacePolicy(Enum):
    """How text-based logical matchers react to Backspace."""
    EDIT_BUFFER = auto()
    IGNORE = auto()
    CLEAR_BUFFER = auto()
    CLEAR_WORD = auto()


class OsKeyRepeatPolicy(Enum):
    """How logical matchers react to OS auto-repeat keydown events."""
    IGNORE = auto()
    MATCH = auto()
    RESET = auto()


class ReplacementPolicy(Enum):
    """How text replacements should be applied when a text matcher fires."""
    REPLACE_ALL = auto()
    APPEND_SUFFIX = auto()
    MINIMAL_DIFF = auto()


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
class LogicalConfig:
    """Extra matching configuration for logical keyboard binds and text abbreviations."""

    case_sensitive: bool = True
    respect_caps_lock: bool = True

    ignore_modifier_keys: bool = True
    ignore_toggle_keys: bool = True

    text_ignore_ctrl_combos: bool = True
    text_ignore_alt_combos: bool = True
    text_ignore_win_combos: bool = True
    text_backspace_policy: TextBackspacePolicy = TextBackspacePolicy.EDIT_BUFFER
    # Legacy compatibility shim. If explicitly set, overrides text_backspace_policy.
    text_backspace_edits_buffer: Optional[bool] = None
    text_clear_buffer_on_non_text: bool = False
    text_boundary_policy: TextBoundaryPolicy = TextBoundaryPolicy.ANYWHERE
    os_key_repeat_policy: OsKeyRepeatPolicy = OsKeyRepeatPolicy.MATCH
    replacement_policy: ReplacementPolicy = ReplacementPolicy.MINIMAL_DIFF


@dataclass(frozen=True)
class Checks:
    predicates: Sequence[CheckPredicate] = field(default_factory=tuple)

    def __iter__(self):
        return iter(self.predicates)

    @classmethod
    def coerce(cls, value: Union[Checks, Sequence[CheckPredicate], CheckPredicate, None]) -> Checks:
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

    # ---- API: merges -------------------------------------------------

    def soft_merge(self, patch: BindConfig) -> BindConfig:
        """Apply only non-default fields from `patch` (patch semantics)."""
        if not isinstance(patch, BindConfig):
            raise TypeError(f"Expected BindConfig, got {type(patch)!r}")
        return _merge_soft(self, patch)

    def hard_merge(self, other: BindConfig) -> BindConfig:
        """Overwrite all fields from `other` (full override semantics)."""
        if not isinstance(other, BindConfig):
            raise TypeError(f"Expected BindConfig, got {type(other)!r}")
        return _merge_dc_hard(self, other)

    # ---- Operator sugar ---------------------------------------------

    def __add__(self, other: BindConfig) -> BindConfig:
        if not isinstance(other, BindConfig):
            return NotImplemented
        return self.soft_merge(other)

    def __or__(self, other: BindConfig) -> BindConfig:
        if not isinstance(other, BindConfig):
            return NotImplemented
        return self.hard_merge(other)


class MouseButton(Enum):
    LEFT = auto()
    RIGHT = auto()
    MIDDLE = auto()
    X1 = auto()
    X2 = auto()


@dataclass(frozen=True)
class MouseBindConfig:
    trigger: Trigger = Trigger.ON_PRESS

    suppress: SuppressPolicy = SuppressPolicy.NEVER
    injected: InjectedPolicy = InjectedPolicy.ALLOW
    focus: FocusPolicy = FocusPolicy.CANCEL_ON_BLUR

    timing: Timing = field(default_factory=Timing)
    constraints: Constraints = field(default_factory=Constraints)
    checks: Checks = field(default_factory=Checks)

    def __post_init__(self):
        object.__setattr__(self, "checks", Checks.coerce(self.checks))

    def soft_merge(self, patch: MouseBindConfig) -> MouseBindConfig:
        """Apply only non-default fields from `patch` (patch semantics)."""
        if not isinstance(patch, MouseBindConfig):
            raise TypeError(f"Expected MouseBindConfig, got {type(patch)!r}")
        return _merge_soft(self, patch)

    def hard_merge(self, other: MouseBindConfig) -> MouseBindConfig:
        """Overwrite all fields from `other` (full override semantics)."""
        if not isinstance(other, MouseBindConfig):
            raise TypeError(f"Expected MouseBindConfig, got {type(other)!r}")
        return _merge_dc_hard(self, other)

    # ---- Operator sugar ---------------------------------------------

    def __add__(self, other: MouseBindConfig) -> MouseBindConfig:
        if not isinstance(other, MouseBindConfig):
            return NotImplemented
        return self.soft_merge(other)

    def __or__(self, other: MouseBindConfig) -> MouseBindConfig:
        if not isinstance(other, MouseBindConfig):
            return NotImplemented
        return self.hard_merge(other)


# =========================================================
# Defaults used to detect "unset" fields during soft merge
# =========================================================

_DEFAULT_BIND = BindConfig()
_DEFAULT_MOUSE = MouseBindConfig()
_DEFAULT_TIMING = Timing()
_DEFAULT_CONSTRAINTS = Constraints()
_DEFAULT_LOGICAL = LogicalConfig()
_DEFAULT_CHECKS = Checks()


# =========================================================
# Dataclass merge helpers
# =========================================================

TBind = TypeVar("TBind", BindConfig, MouseBindConfig)


def _merge_dc_hard(lhs, rhs):
    """
    Recursively merge dataclasses in "hard" mode.

    All fields from rhs overwrite lhs, including default values.
    This behaves like a full override.
    """
    out = lhs

    for name in lhs.__dataclass_fields__.keys():  # type: ignore[attr-defined]
        lval = getattr(lhs, name)
        rval = getattr(rhs, name)

        if is_dataclass(lval) and is_dataclass(rval):
            out = replace(out, **{name: _merge_dc_hard(lval, rval)})
        else:
            out = replace(out, **{name: rval})

    return out


def _merge_dc_soft(lhs, rhs, default_obj):
    """
    Recursively merge dataclasses in "soft" mode.

    A field from rhs is applied only if it differs from the default value.
    This allows rhs to behave like a patch.
    """
    out = lhs

    for name in default_obj.__dataclass_fields__.keys():  # type: ignore[attr-defined]
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


def _merge_soft(lhs: TBind, rhs: TBind) -> TBind:
    out = lhs

    default_bind = _DEFAULT_BIND if isinstance(out, BindConfig) else _DEFAULT_MOUSE

    if rhs.trigger != default_bind.trigger:
        out = replace(out, trigger=rhs.trigger)

    if rhs.suppress != default_bind.suppress:
        out = replace(out, suppress=rhs.suppress)

    if rhs.injected != default_bind.injected:
        out = replace(out, injected=rhs.injected)

    if rhs.focus != default_bind.focus:
        out = replace(out, focus=rhs.focus)

    out = replace(out, timing=_merge_dc_soft(out.timing, rhs.timing, _DEFAULT_TIMING))
    out = replace(out, constraints=_merge_dc_soft(out.constraints, rhs.constraints, _DEFAULT_CONSTRAINTS))
    out = replace(out, checks=_merge_dc_soft(out.checks, rhs.checks, _DEFAULT_CHECKS))

    return out
