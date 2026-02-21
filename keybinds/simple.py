from __future__ import annotations

from collections.abc import Callable
from typing import Any

from keybinds import get_default_hook as get_hook, join
from keybinds.bind import Hook
from keybinds.decorators import bind_key
from keybinds.types import (
    BindConfig,
    SuppressPolicy,
    Trigger,
    Timing,
)


def _build_config(
    *,
    release: bool = False,
    hold: int | None = None,
    repeat: int | None = None,
    sequence: bool = False,
    double_tap: bool = False,
    suppress: bool = False,
    # optional timings:
    delay: int | None = None,    # repeat initial delay (ms)
    timeout: int | None = None,  # sequence timeout / chord timeout (ms)
    double_tap_window: int | None = None,
) -> BindConfig:
    """
    Convert simple flags into BindConfig.

    Priority:
        hold > repeat > sequence > double_tap > release > press(default)
    """
    # Count mutually-exclusive trigger-ish flags
    exclusive_flags = [
        release,
        hold is not None,
        repeat is not None,
        sequence,
        double_tap,
    ]
    if sum(bool(x) for x in exclusive_flags) > 1:
        raise ValueError(
            "Conflicting flags: use only one of "
            "release / hold / repeat / sequence / double_tap"
        )

    trigger = Trigger.ON_PRESS
    timing_kwargs: dict[str, int] = {}

    if hold is not None:
        trigger = Trigger.ON_HOLD
        timing_kwargs["hold_ms"] = int(hold)

    elif repeat is not None:
        trigger = Trigger.ON_REPEAT
        timing_kwargs["repeat_interval_ms"] = int(repeat)
        # initial delay before repeat starts
        if delay is not None:
            timing_kwargs["repeat_delay_ms"] = int(delay)

    elif sequence:
        trigger = Trigger.ON_SEQUENCE
        if timeout is not None:
            timing_kwargs["chord_timeout_ms"] = int(timeout)

    elif double_tap:
        trigger = Trigger.ON_DOUBLE_TAP
        if double_tap_window is not None:
            timing_kwargs["double_tap_window_ms"] = int(double_tap_window)

    elif release:
        trigger = Trigger.ON_RELEASE

    cfg = BindConfig(trigger=trigger)

    if timing_kwargs:
        cfg = cfg + BindConfig(timing=Timing(**timing_kwargs))  # soft merge

    if suppress:
        cfg = cfg + BindConfig(suppress=SuppressPolicy.WHEN_MATCHED)

    return cfg


def hotkey(
    expr: str,
    *,
    release: bool = False,
    hold: int | None = None,
    repeat: int | None = None,
    sequence: bool = False,
    double_tap: bool = False,
    suppress: bool = False,
    # optional ergonomics:
    delay: int | None = None,
    timeout: int | None = None,
    double_tap_window: int | None = None,
    hwnd: int | None = None,
    hook: Hook | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Simple decorator API for common keyboard hotkeys.

    Examples:
        @hotkey("ctrl+e")
        @hotkey("v", release=True)
        @hotkey("f", hold=400)
        @hotkey("space", repeat=80, delay=200)
        @hotkey("g,k,i", sequence=True, timeout=600)
        @hotkey("d", double_tap=True, double_tap_window=250)
        @hotkey("ctrl+r", suppress=True)
    """
    target_hook = hook or get_hook()

    cfg = _build_config(
        release=release,
        hold=hold,
        repeat=repeat,
        sequence=sequence,
        double_tap=double_tap,
        suppress=suppress,
        delay=delay,
        timeout=timeout,
        double_tap_window=double_tap_window,
    )

    return bind_key(expr, config=cfg, hwnd=hwnd, hook=target_hook)


def wait(timeout: float | None = None, *, hook: Hook | None = None) -> bool:
    """Proxy to Hook.wait(timeout)."""
    return (hook or get_hook()).wait(timeout=timeout)


def close(*, hook: Hook | None = None) -> None:
    """Close the simple-layer hook frontend/workers."""
    (hook or get_hook()).close()


def run(*, hook: Hook | None = None) -> None:
    """Alias for join()."""
    join(hook=hook)
