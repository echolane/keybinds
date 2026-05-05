from __future__ import annotations

import threading
import time
from typing import Callable, Optional, Union, Tuple

from . import winput

from .types import Callback, MouseBindConfig, MouseButton, SuppressPolicy, InjectedPolicy, Trigger
from ._constants import (
    WM_LBUTTONDOWN, WM_LBUTTONUP,
    WM_RBUTTONDOWN, WM_RBUTTONUP,
    WM_MBUTTONDOWN, WM_MBUTTONUP,
    WM_XBUTTONDOWN, WM_XBUTTONUP,
)
from .diagnostics import _DiagnosticsManager, _EventTrace
from ._base_bind import BaseBind
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


class MouseBind(BaseBind[winput.MouseEvent]):
    def __init__(
        self,
        button: Union[MouseButton, str],
        callback: Callback,
        *,
        config: Optional[MouseBindConfig] = None,
        hwnd: Optional[int] = None,
        dispatch: Optional[Callable[..., None]] = None,
        diagnostics: Optional[_DiagnosticsManager] = None,
    ) -> None:
        super().__init__(callback, config=config or MouseBindConfig(), hwnd=hwnd, dispatch=dispatch, diagnostics=diagnostics)
        self.button = _normalize_mouse_button(button)
        self._set_diagnostics_identity(self.button.name.lower(), "mouse")

        self._down_ms: Optional[int] = None
        self._press_suppress_up: bool = False
        self._tap_count: int = 0
        self._tap_last_ms: int = 0
        self._armed: bool = False

    def _checks_ok(self, event: winput.MouseEvent, state: InputState, trace: Optional[_EventTrace] = None) -> bool:
        return super()._checks_ok(event, state, trace=trace)

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

    def reset(self) -> None:
        self._down_ms = None
        self._press_suppress_up = False
        self._tap_count = 0
        self._tap_last_ms = 0
        self._hold_token += 1
        self._armed = False

    def _get_pressed_for_policy(self, state: InputState, *, inj: bool) -> set[MouseButton]:
        pol = self.config.injected
        if pol == InjectedPolicy.IGNORE:
            return set(state.pressed_mouse)
        if pol == InjectedPolicy.ONLY:
            return set(state.pressed_mouse_injected or ())
        if inj:
            return set(state.pressed_mouse_injected or ())
        return set(state.pressed_mouse)

    def is_pressed(self) -> bool:
        from ._backend import _GlobalBackend

        with self._lock:
            if not self._window_ok(force=True):
                return False
            state = _GlobalBackend.instance().current_state_snapshot()
            pressed = self._get_pressed_for_policy(state, inj=bool(state.pressed_mouse_injected))
            return self.button in pressed

    def handle(self, event: winput.MouseEvent, state: InputState) -> int:
        # Mouse move/wheel is extremely frequent; this is called only after Hook filtered.
        with self._lock:
            trace = self._trace(event)
            now_ms = int(event.time)

            if not self._window_ok(trace=trace):
                return winput.WP_CONTINUE
            if self.config.checks.predicates and not self._checks_ok(event, state, trace=trace):
                return winput.WP_CONTINUE
            if not self._xbutton_match(event):
                return winput.WP_CONTINUE

            inj = bool(getattr(event, "injected", False))
            pol = self.config.injected
            if pol == InjectedPolicy.IGNORE and inj:
                trace.skip("injected_ignored")
                return winput.WP_CONTINUE
            if pol == InjectedPolicy.ONLY and not inj:
                trace.skip("injected_only_but_physical")
                return winput.WP_CONTINUE

            down_act, up_act = self._actions_for_button()
            is_down = event.action == down_act
            is_up = event.action == up_act

            # Not our button event -> ignore silently for diagnostics.
            if not is_down and not is_up:
                return winput.WP_CONTINUE

            # --- CHANGED: keep previous armed state for suppress semantics ---
            was_armed = self._armed
            # --- END CHANGED ---

            if is_down:
                self._armed = True
            if is_up:
                self._armed = False

            if was_armed and not self._armed and self.config.trigger in (Trigger.ON_HOLD, Trigger.ON_REPEAT):
                self._hold_token += 1

            trace.note(
                "decision",
                "candidate_state",
                is_down=is_down,
                is_up=is_up,
                armed=self._armed,
                was_armed=was_armed,
                button=self.button.name.lower(),
            )

            flags = winput.WP_CONTINUE
            sup = self.config.suppress

            if sup == SuppressPolicy.ALWAYS:
                flags |= winput.WP_DONT_PASS_INPUT_ON
                trace.suppress("suppressed_always")

            elif sup == SuppressPolicy.WHILE_ACTIVE:
                if self._armed:
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_while_active")

            elif sup == SuppressPolicy.WHILE_EVALUATING:
                # suppress DOWN and the paired UP for this click/gesture
                if self._armed or was_armed:
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_while_evaluating")

            elif self.config.suppress == SuppressPolicy.WHEN_MATCHED and is_up and self._press_suppress_up:
                flags |= winput.WP_DONT_PASS_INPUT_ON
                trace.suppress("suppressed_when_matched")
                self._press_suppress_up = False

            trig = self.config.trigger
            trig_name = trig.name.lower()

            def fire_if_allowed(ts_ms: int):
                if not self.can_fire_now(ts_ms, trace=trace):
                    return None
                self._fires += 1
                self._last_fire_ms = ts_ms
                dispatch_trace = trace.fire(trigger=trig_name)
                self._fire(dispatch_trace)
                return dispatch_trace

            if trig == Trigger.ON_PRESS and is_down:
                fired = fire_if_allowed(now_ms)
                if fired is not None and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_when_matched", trigger=trig_name)
                    self._press_suppress_up = True  # button up suppress

            elif trig == Trigger.ON_RELEASE:
                if (
                    is_down
                    and self.config.suppress == SuppressPolicy.WHEN_MATCHED
                    and self.can_fire_now(now_ms)
                ):
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_when_matched", trigger=trig_name)
                    self._press_suppress_up = True

                if is_up:
                    fire_if_allowed(now_ms)

            elif trig == Trigger.ON_CLICK:
                if is_down:
                    self._down_ms = now_ms
                    trace.note("decision", "click_started")
                elif is_up and self._down_ms is not None:
                    dur = now_ms - self._down_ms
                    self._down_ms = None
                    if dur <= self.config.timing.hold_ms:
                        fire_if_allowed(now_ms)
                    else:
                        trace.skip("hold_not_long_enough", duration_ms=dur, hold_ms=self.config.timing.hold_ms)

            elif trig == Trigger.ON_HOLD and is_down:
                hold_ms = self.config.timing.hold_ms

                self._hold_token += 1
                token = self._hold_token
                trace.note("decision", "hold_timer_started", hold_ms=hold_ms)

                def _hold() -> None:
                    time.sleep(max(0, hold_ms) / 1000.0)
                    with self._lock:
                        if token != self._hold_token:
                            trace.skip("hold_timer_cancelled", reason_detail="token_changed")
                            return
                        if not self._armed:
                            trace.skip("hold_timer_cancelled", reason_detail="button_released")
                            return
                        if not self._window_ok(force=True, trace=trace):
                            trace.skip("hold_timer_cancelled", reason_detail="window_mismatch")
                            return

                        now2 = int(time.monotonic() * 1000)
                        trace.note("decision", "hold_timer_fired")
                        fire_if_allowed(now2)

                threading.Thread(target=_hold, daemon=True).start()

            elif trig == Trigger.ON_REPEAT and is_down:
                delay_s = max(self.config.timing.hold_ms, self.config.timing.repeat_delay_ms) / 1000.0
                interval_s = max(1, self.config.timing.repeat_interval_ms) / 1000.0

                self._hold_token += 1
                token = self._hold_token
                trace.note(
                    "decision",
                    "repeat_started",
                    repeat_delay_ms=int(delay_s * 1000),
                    repeat_interval_ms=int(interval_s * 1000),
                )

                def _repeat() -> None:
                    time.sleep(max(0.0, delay_s))
                    while True:
                        with self._lock:
                            if token != self._hold_token:
                                trace.skip("repeat_cancelled", reason_detail="token_changed")
                                break
                            if not self._armed:
                                trace.skip("repeat_cancelled", reason_detail="button_released")
                                break
                            if not self._window_ok(force=True, trace=trace):
                                trace.skip("repeat_cancelled", reason_detail="window_mismatch")
                                break

                            now2 = int(time.monotonic() * 1000)
                            trace.note("decision", "repeat_tick")
                            fire_if_allowed(now2)
                        time.sleep(interval_s)

                threading.Thread(target=_repeat, daemon=True).start()

            elif trig in (Trigger.ON_DOUBLE_TAP, Trigger.ON_TRIPLE_TAP) and is_down:
                required_taps = 2 if trig == Trigger.ON_DOUBLE_TAP else 3
                win = (
                    self.config.timing.double_tap_window_ms
                    if trig == Trigger.ON_DOUBLE_TAP
                    else self.config.timing.triple_tap_window_ms
                )
                if (now_ms - self._tap_last_ms) <= win:
                    self._tap_count += 1
                else:
                    self._tap_count = 1
                self._tap_last_ms = now_ms
                progress_reason = "double_tap_progress" if trig == Trigger.ON_DOUBLE_TAP else "triple_tap_progress"
                trace.note(
                    "decision",
                    progress_reason,
                    tap_count=self._tap_count,
                    required_taps=required_taps,
                    window_ms=win,
                )
                if self._tap_count >= required_taps:
                    self._tap_count = 0
                    fired = fire_if_allowed(now_ms)
                    if fired is not None and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                        flags |= winput.WP_DONT_PASS_INPUT_ON
                        trace.suppress("suppressed_when_matched", trigger=trig_name)
                        self._press_suppress_up = True

            return flags
