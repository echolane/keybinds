from __future__ import annotations

import threading
import time
from traceback import print_exc
from typing import Callable, Optional, Union, Tuple, TYPE_CHECKING

from . import winput

from .types import Callback, MouseBindConfig, MouseButton, SuppressPolicy, InjectedPolicy, Trigger
from ._constants import (
    WM_LBUTTONDOWN, WM_LBUTTONUP,
    WM_RBUTTONDOWN, WM_RBUTTONUP,
    WM_MBUTTONDOWN, WM_MBUTTONUP,
    WM_XBUTTONDOWN, WM_XBUTTONUP,
)
from ._utils import get_window

if TYPE_CHECKING:
    from ._state import InputState


def _normalize_mouse_button(btn: object) -> MouseButton:
    if isinstance(btn, MouseButton):
        return btn
    if isinstance(btn, str):
        s = btn.strip().lower()
        aliases = {
            "left": MouseButton.LEFT,
            "lmb": MouseButton.LEFT,
            "right": MouseButton.RIGHT,
            "rmb": MouseButton.RIGHT,
            "middle": MouseButton.MIDDLE,
            "mmb": MouseButton.MIDDLE,
            "x1": MouseButton.X1,
            "mouse4": MouseButton.X1,
            "x2": MouseButton.X2,
            "mouse5": MouseButton.X2,
        }
        if s in aliases:
            return aliases[s]
    raise ValueError(f"Unknown mouse button: {btn!r}")


class MouseBind:
    def __init__(
        self,
        button: Union[MouseButton, str],
        callback: Callback,
        *,
        config: Optional[MouseBindConfig] = None,
        hwnd: Optional[int] = None,
        dispatch: Optional[Callable[[Callable[[], None]], None]] = None,
    ) -> None:
        self.button = _normalize_mouse_button(button)
        self.callback = callback
        self.config = config or MouseBindConfig()
        self.window = get_window(hwnd)
        self._dispatch = dispatch or (lambda fn: fn())

        self._focus_cache: bool = True
        self._focus_last_check_ms: int = 0

        self._down_ms: Optional[int] = None
        self._tap_count: int = 0
        self._tap_last_ms: int = 0
        self._repeat_active: bool = False
        self._armed: bool = False

        self._fires: int = 0
        self._last_fire_ms: int = 0
        self._lock = threading.RLock()

        # for ON_RELEASE + WHEN_MATCHED paired suppress
        self._suppress_next_up: bool = False

    def _window_ok(self) -> bool:
        if self.window is None:
            return True
        now_ms = int(time.monotonic() * 1000)
        if (now_ms - self._focus_last_check_ms) < self.config.timing.window_focus_cache_ms:
            return self._focus_cache
        self._focus_last_check_ms = now_ms
        try:
            self._focus_cache = bool(self.window.is_focused())
        except Exception:
            self._focus_cache = False
        return self._focus_cache

    def _checks_ok(self, event: winput.MouseEvent, state: InputState) -> bool:
        for pred in self.config.checks:
            try:
                if not pred(event, state):
                    return False
            except Exception:
                print_exc()
                return False
        return True

    def _cooldown_ok(self, now_ms: int) -> bool:
        cd = self.config.timing.cooldown_ms
        return cd <= 0 or (now_ms - self._last_fire_ms) >= cd

    def _max_fires_ok(self) -> bool:
        mx = self.config.constraints.max_fires
        return mx is None or self._fires < mx

    def _fire_async(self) -> None:
        cb = self.callback

        def _run() -> None:
            try:
                cb()
            except Exception:
                print_exc()

        self._dispatch(_run)

    def _actions_for_button(self) -> Tuple[int, int]:
        if self.button == MouseButton.LEFT:
            return WM_LBUTTONDOWN, WM_LBUTTONUP
        if self.button == MouseButton.RIGHT:
            return WM_RBUTTONDOWN, WM_RBUTTONUP
        if self.button == MouseButton.MIDDLE:
            return WM_MBUTTONDOWN, WM_MBUTTONUP
        return WM_XBUTTONDOWN, WM_XBUTTONUP

    def _xbutton_match(self, event: winput.MouseEvent) -> bool:
        if event.action not in (WM_XBUTTONDOWN, WM_XBUTTONUP):
            return True
        try:
            which = int(getattr(event, "additional_data", 0) or 0)
        except Exception:
            which = 0
        if self.button == MouseButton.X1:
            return which == 1
        if self.button == MouseButton.X2:
            return which == 2
        return True

    def handle(self, event: winput.MouseEvent, state: "InputState") -> int:
        # Mouse move/wheel is extremely frequent; this is called only after Hook filtered.
        with self._lock:
            now_ms = int(event.time)

            if self.window is not None and not self._window_ok():
                return winput.WP_CONTINUE
            if self.config.checks.predicates and not self._checks_ok(event, state):
                return winput.WP_CONTINUE
            if not self._xbutton_match(event):
                return winput.WP_CONTINUE

            inj = bool(getattr(event, "injected", False))
            pol = self.config.injected
            if pol == InjectedPolicy.IGNORE and inj:
                return winput.WP_CONTINUE
            if pol == InjectedPolicy.ONLY and not inj:
                return winput.WP_CONTINUE

            down_act, up_act = self._actions_for_button()
            is_down = event.action == down_act
            is_up = event.action == up_act

            # Not our button event -> ignore.
            if not is_down and not is_up:
                return winput.WP_CONTINUE

            # --- CHANGED: keep previous armed state for suppress semantics ---
            was_armed = self._armed
            # --- END CHANGED ---

            if is_down:
                self._armed = True
            if is_up:
                self._armed = False
                self._repeat_active = False

            flags = winput.WP_CONTINUE
            sup = self.config.suppress

            if sup == SuppressPolicy.ALWAYS:
                flags |= winput.WP_DONT_PASS_INPUT_ON

            elif sup == SuppressPolicy.WHILE_ACTIVE:
                if self._armed:
                    flags |= winput.WP_DONT_PASS_INPUT_ON

            elif sup == SuppressPolicy.WHILE_EVALUATING:
                # suppress DOWN and the paired UP for this click/gesture
                if self._armed or was_armed:
                    flags |= winput.WP_DONT_PASS_INPUT_ON

            trig = self.config.trigger

            def fire_if_allowed(ts_ms: int) -> bool:
                if self._cooldown_ok(ts_ms) and self._max_fires_ok():
                    self._fires += 1
                    self._last_fire_ms = ts_ms
                    self._fire_async()
                    return True
                return False

            if trig == Trigger.ON_PRESS and is_down:
                if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                    flags |= winput.WP_DONT_PASS_INPUT_ON

            elif trig == Trigger.ON_RELEASE and is_up:
                if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                    flags |= winput.WP_DONT_PASS_INPUT_ON

            elif trig == Trigger.ON_CLICK:
                if is_down:
                    self._down_ms = now_ms
                elif is_up and self._down_ms is not None:
                    dur = now_ms - self._down_ms
                    self._down_ms = None
                    if dur <= self.config.timing.hold_ms:
                        if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                            flags |= winput.WP_DONT_PASS_INPUT_ON

            elif trig == Trigger.ON_HOLD and is_down:
                hold_ms = self.config.timing.hold_ms

                def _hold() -> None:
                    time.sleep(max(0, hold_ms) / 1000.0)
                    with self._lock:
                        if self._armed:
                            now2 = int(time.monotonic() * 1000)
                            fire_if_allowed(now2)

                threading.Thread(target=_hold, daemon=True).start()

            elif trig == Trigger.ON_REPEAT and is_down and not self._repeat_active:
                self._repeat_active = True
                delay_s = max(self.config.timing.hold_ms, self.config.timing.repeat_delay_ms) / 1000.0
                interval_s = max(1, self.config.timing.repeat_interval_ms) / 1000.0

                def _repeat() -> None:
                    time.sleep(max(0.0, delay_s))
                    while True:
                        with self._lock:
                            if not self._armed:
                                self._repeat_active = False
                                break
                            now2 = int(time.monotonic() * 1000)
                            fire_if_allowed(now2)
                        time.sleep(interval_s)

                threading.Thread(target=_repeat, daemon=True).start()

            elif trig == Trigger.ON_DOUBLE_TAP and is_down:
                win = self.config.timing.double_tap_window_ms
                if (now_ms - self._tap_last_ms) <= win:
                    self._tap_count += 1
                else:
                    self._tap_count = 1
                self._tap_last_ms = now_ms
                if self._tap_count >= 2:
                    self._tap_count = 0
                    if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                        flags |= winput.WP_DONT_PASS_INPUT_ON

            return flags
