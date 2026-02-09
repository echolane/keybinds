"""keybinds presets + ready-to-use profiles.
Usage:

    from keybinds.presets import hold, repeat, ptt, tap_hold, silent_hotkey

    hook.bind("k", cb, config=hold(450))
    p = ptt(suppress=True)
    hook.bind("v", on,  config=p.press)
    hook.bind("v", off, config=p.release)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Union

from .types import (
    BindConfig,
    MouseBindConfig,
    Trigger,
    SuppressPolicy,
    Timing,
    Constraints,
    ChordPolicy,
    InjectedPolicy
)


# -----------------------------
# Generic helpers
# -----------------------------


def timing(
    *,
    hold_ms: Optional[int] = None,
    repeat_delay_ms: Optional[int] = None,
    repeat_interval_ms: Optional[int] = None,
    double_tap_window_ms: Optional[int] = None,
    chord_timeout_ms: Optional[int] = None,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
) -> Timing:
    """Build a Timing object with optional overrides."""
    t = Timing()
    if hold_ms is not None:
        t = replace(t, hold_ms=hold_ms)
    if repeat_delay_ms is not None:
        t = replace(t, repeat_delay_ms=repeat_delay_ms)
    if repeat_interval_ms is not None:
        t = replace(t, repeat_interval_ms=repeat_interval_ms)
    if double_tap_window_ms is not None:
        t = replace(t, double_tap_window_ms=double_tap_window_ms)
    if chord_timeout_ms is not None:
        t = replace(t, chord_timeout_ms=chord_timeout_ms)
    if cooldown_ms is not None:
        t = replace(t, cooldown_ms=cooldown_ms)
    if debounce_ms is not None:
        t = replace(t, debounce_ms=debounce_ms)
    return t


def strict_constraints() -> Constraints:
    """Convenience: strict chord constraints."""
    return Constraints(chord_policy=ChordPolicy.STRICT)


def suppress(mouse: bool = False) -> Union[BindConfig, MouseBindConfig]:
    """Convenience: suppress (WHILE_ACTIVE) on match."""
    cfg_class = MouseBindConfig if mouse else BindConfig
    return cfg_class(suppress=SuppressPolicy.WHILE_ACTIVE)


def ignore_injected(mouse: bool = False) -> BindConfig:
    """Convenience: ignore injected (synthetic) events."""
    cfg_class = MouseBindConfig if mouse else BindConfig
    return cfg_class(injected=InjectedPolicy.IGNORE)


# -----------------------------
# Keyboard presets (BindConfig)
# -----------------------------

def press(
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
    strict: bool = False,
) -> BindConfig:
    t = timing(cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return BindConfig(
        trigger=Trigger.ON_PRESS,
        suppress=suppress,
        timing=t,
        constraints=(strict_constraints() if strict else Constraints()),
    )


def release(
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
    strict: bool = False,
) -> BindConfig:
    t = timing(cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return BindConfig(
        trigger=Trigger.ON_RELEASE,
        suppress=suppress,
        timing=t,
        constraints=(strict_constraints() if strict else Constraints()),
    )


def chord_released(
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
    strict: bool = False,
) -> BindConfig:
    t = timing(cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return BindConfig(
        trigger=Trigger.ON_CHORD_RELEASED,
        suppress=suppress,
        timing=t,
        constraints=(strict_constraints() if strict else Constraints()),
    )


def click(
    tap_ms: int = 220,
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
    strict: bool = False,
) -> BindConfig:
    t = timing(hold_ms=tap_ms, cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return BindConfig(
        trigger=Trigger.ON_CLICK,
        suppress=suppress,
        timing=t,
        constraints=(strict_constraints() if strict else Constraints()),
    )


def hold(
    hold_ms: int = 400,
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
    strict: bool = False,
) -> BindConfig:
    t = timing(hold_ms=hold_ms, cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return BindConfig(
        trigger=Trigger.ON_HOLD,
        suppress=suppress,
        timing=t,
        constraints=(strict_constraints() if strict else Constraints()),
    )


def repeat(
    *,
    delay_ms: int = 200,
    interval_ms: int = 80,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
    strict: bool = False,
) -> BindConfig:
    t = timing(
        hold_ms=delay_ms,
        repeat_delay_ms=delay_ms,
        repeat_interval_ms=interval_ms,
        cooldown_ms=cooldown_ms,
        debounce_ms=debounce_ms,
    )
    return BindConfig(
        trigger=Trigger.ON_REPEAT,
        suppress=suppress,
        timing=t,
        constraints=(strict_constraints() if strict else Constraints()),
    )


def double_tap(
    window_ms: int = 300,
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
    strict: bool = False,
) -> BindConfig:
    t = timing(double_tap_window_ms=window_ms, cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return BindConfig(
        trigger=Trigger.ON_DOUBLE_TAP,
        suppress=suppress,
        timing=t,
        constraints=(strict_constraints() if strict else Constraints()),
    )


def sequence(
    timeout_ms: int = 550,
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
) -> BindConfig:
    t = timing(chord_timeout_ms=timeout_ms, cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return BindConfig(
        trigger=Trigger.ON_SEQUENCE,
        suppress=suppress,
        timing=t,
        constraints=Constraints(),
    )


# -----------------------------
# Mouse presets (MouseBindConfig)
# -----------------------------

def mouse_press(
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
) -> MouseBindConfig:
    t = timing(cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return MouseBindConfig(trigger=Trigger.ON_PRESS, suppress=suppress, timing=t)


def mouse_release(
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
) -> MouseBindConfig:
    t = timing(cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return MouseBindConfig(trigger=Trigger.ON_RELEASE, suppress=suppress, timing=t)


def mouse_click(
    tap_ms: int = 200,
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
) -> MouseBindConfig:
    t = timing(hold_ms=tap_ms, cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return MouseBindConfig(trigger=Trigger.ON_CLICK, suppress=suppress, timing=t)


def mouse_hold(
    hold_ms: int = 300,
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
) -> MouseBindConfig:
    t = timing(hold_ms=hold_ms, cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return MouseBindConfig(trigger=Trigger.ON_HOLD, suppress=suppress, timing=t)


def mouse_repeat(
    *,
    delay_ms: int = 180,
    interval_ms: int = 80,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
) -> MouseBindConfig:
    t = timing(
        hold_ms=delay_ms,
        repeat_delay_ms=delay_ms,
        repeat_interval_ms=interval_ms,
        cooldown_ms=cooldown_ms,
        debounce_ms=debounce_ms,
    )
    return MouseBindConfig(trigger=Trigger.ON_REPEAT, suppress=suppress, timing=t)


def mouse_double_tap(
    window_ms: int = 300,
    *,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: Optional[int] = None,
    debounce_ms: Optional[int] = None,
) -> MouseBindConfig:
    t = timing(double_tap_window_ms=window_ms, cooldown_ms=cooldown_ms, debounce_ms=debounce_ms)
    return MouseBindConfig(trigger=Trigger.ON_DOUBLE_TAP, suppress=suppress, timing=t)


# -----------------------------
# PROFILES (practical bundles)
# -----------------------------

@dataclass(frozen=True)
class TapHoldProfile:
    """One physical key: tap does A, hold does B."""
    tap: BindConfig
    hold: BindConfig


def tap_hold(
    *,
    tap_ms: int = 220,
    hold_ms: int = 450,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
    cooldown_ms: int = 100,
    debounce_ms: int = 0,
) -> TapHoldProfile:
    """Config bundle for the classic tap-vs-hold pattern."""
    return TapHoldProfile(
        tap=click(tap_ms, suppress=suppress, debounce_ms=debounce_ms),
        hold=hold(hold_ms, suppress=suppress, cooldown_ms=cooldown_ms, debounce_ms=debounce_ms),
    )


@dataclass(frozen=True)
class PTTProfile:
    """Push-to-talk: press enables, release disables."""
    press: BindConfig
    release: BindConfig


def ptt(
    *,
    suppress: bool = False,
    strict: bool = False,
) -> PTTProfile:
    """Push-to-talk defaults.

    If suppress=True, uses WHILE_ACTIVE (recommended so key doesn't leak while held).
    """
    sup = SuppressPolicy.WHILE_ACTIVE if suppress else SuppressPolicy.NEVER
    return PTTProfile(
        press=press(suppress=sup, strict=strict),
        release=release(suppress=sup, strict=strict),
    )


def silent_hotkey(
    *,
    strict: bool = False,
    aggressive: bool = False,
) -> BindConfig:
    """Hotkey that should not reach the focused app.

    - aggressive=False: suppress only when matched (safest UX)
    - aggressive=True: suppress while evaluating (hides chord during assembly)
    """
    return press(
        suppress=(SuppressPolicy.WHEN_MATCHED if not aggressive else SuppressPolicy.WHILE_EVALUATING),
        strict=strict,
    )


def hidden_chord(
    *,
    strict: bool = False,
    chord_timeout_ms: int = 450,
) -> BindConfig:
    """Chord intended to be completely hidden from apps while assembling."""
    return BindConfig(
        trigger=Trigger.ON_PRESS,
        suppress=SuppressPolicy.WHILE_EVALUATING,
        timing=timing(chord_timeout_ms=chord_timeout_ms),
        constraints=(strict_constraints() if strict else Constraints()),
    )


def game_autofire(
    *,
    delay_ms: int = 150,
    interval_ms: int = 60,
    suppress: bool = True,
) -> MouseBindConfig:
    """Mouse autofire profile (repeat while held).

    suppress=True uses WHILE_ACTIVE to block clicks reaching the app.
    """
    sup = SuppressPolicy.WHILE_ACTIVE if suppress else SuppressPolicy.NEVER
    return mouse_repeat(delay_ms=delay_ms, interval_ms=interval_ms, suppress=sup)


def rapid_double_tap(
    *,
    window_ms: int = 220,
    cooldown_ms: int = 150,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
) -> BindConfig:
    """Fast 'dash' style double tap with a short cooldown."""
    return double_tap(window_ms=window_ms, cooldown_ms=cooldown_ms, suppress=suppress)


def cheatcode_sequence(
    *,
    timeout_ms: int = 700,
    suppress: SuppressPolicy = SuppressPolicy.NEVER,
) -> BindConfig:
    """Sequence preset tuned for 'cheatcode' / multi-step combos."""
    return sequence(timeout_ms=timeout_ms, suppress=suppress)
