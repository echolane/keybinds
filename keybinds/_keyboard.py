from __future__ import annotations

import threading
import time
from traceback import print_exc
from typing import Callable, Optional, Set, TYPE_CHECKING

from . import winput

from .types import Callback, BindConfig, ChordPolicy, SuppressPolicy, InjectedPolicy, Trigger
from ._constants import (
    WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP,
    is_modifier_vk,
)
from ._parsing import _ChordSpec, parse_key_expr
from ._utils import get_window

if TYPE_CHECKING:
    from ._state import InputState


class Bind:
    """Policy-driven keyboard bind."""

    def __init__(
        self,
        expr: str,
        callback: Callback,
        *,
        config: Optional[BindConfig] = None,
        hwnd: Optional[int] = None,
        dispatch: Optional[Callable[[Callable[[], None]], None]] = None,
    ) -> None:
        self.expr = expr
        self.callback = callback
        self.config = config or BindConfig()
        self.steps = parse_key_expr(expr)
        self.is_sequence = len(self.steps) > 1
        self.window = get_window(hwnd)
        self._dispatch = dispatch or (lambda fn: fn())

        # focus caching
        self._focus_cache: bool = True
        self._focus_last_check_ms: int = 0

        # runtime state
        self._seq_index: int = 0
        self._seq_last_ms: int = 0

        self._last_fire_ms: int = 0
        self._last_event_ms: int = 0
        self._fires: int = 0

        self._click_down_ms: Optional[int] = None
        self._repeat_active: bool = False
        self._armed: bool = False
        self._was_full: bool = False
        self._tap_count: int = 0
        self._tap_last_ms: int = 0
        self._hold_token: int = 0

        # for ON_CHORD_RELEASED semantics
        self._had_full: bool = False
        self._release_armed: bool = False
        self._invalidated: bool = False

        self._lock = threading.RLock()

    def reset(self) -> None:
        self._seq_index = 0
        self._seq_last_ms = 0
        self._click_down_ms = None
        self._tap_count = 0
        self._tap_last_ms = 0
        self._hold_token = 0
        self._armed = False
        self._was_full = False
        self._had_full = False
        self._release_armed: bool = False
        self._invalidated = False
        self._repeat_active = False

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

    def _checks_ok(self, event: winput.KeyboardEvent, state: InputState) -> bool:
        for pred in self.config.checks:
            try:
                if not pred(event, state):
                    return False
            except Exception:
                return False
        return True

    def _cooldown_ok(self, now_ms: int) -> bool:
        cd = self.config.timing.cooldown_ms
        return cd <= 0 or (now_ms - self._last_fire_ms) >= cd

    def _debounce_ok(self, now_ms: int) -> bool:
        db = self.config.timing.debounce_ms
        return db <= 0 or (now_ms - self._last_event_ms) >= db

    def _max_fires_ok(self) -> bool:
        mx = self.config.constraints.max_fires
        return mx is None or self._fires < mx

    def _step_timeout_ok(self, now_ms: int) -> bool:
        to = self.config.timing.chord_timeout_ms
        if not self.is_sequence or self._seq_index == 0:
            return True
        return (now_ms - self._seq_last_ms) <= to

    def _match_chord(self, chord: _ChordSpec, pressed: Set[int]) -> bool:
        cpol = self.config.constraints.chord_policy

        for g in chord.groups:
            if not (pressed & set(g)):
                return False

        if cpol == ChordPolicy.RELAXED:
            return True

        if cpol == ChordPolicy.IGNORE_EXTRA_MODIFIERS:
            required_any = set(chord.allowed_union)
            for vk in pressed:
                if vk in required_any:
                    continue
                if is_modifier_vk(vk):
                    continue
                return False
            return True

        # STRICT
        required_any = set(chord.allowed_union)
        ignored = self.config.constraints.ignore_keys
        for vk in pressed:
            if vk in ignored:
                continue
            if vk not in required_any:
                return False
        return True

    def _fire_async(self) -> None:
        cb = self.callback

        def _run() -> None:
            try:
                cb()
            except Exception:
                print_exc()

        self._dispatch(_run)

    def handle(self, event: winput.KeyboardEvent, state: "InputState") -> int:
        # Keep hook path tiny: avoid heavy work unless needed.
        with self._lock:
            now_ms = int(event.time)

            if self.window is not None and not self._window_ok():
                self.reset()
                return winput.WP_CONTINUE

            if self.config.checks.predicates and not self._checks_ok(event, state):
                return winput.WP_CONTINUE

            if not self._debounce_ok(now_ms):
                return winput.WP_CONTINUE

            if not self._step_timeout_ok(now_ms):
                self.reset()

            self._last_event_ms = now_ms

            inj = bool(getattr(event, "injected", False))
            pol = self.config.injected
            if pol == InjectedPolicy.IGNORE and inj:
                return winput.WP_CONTINUE
            if pol == InjectedPolicy.ONLY and not inj:
                return winput.WP_CONTINUE

            chord = self.steps[self._seq_index]

            # Choose matching domain based on injected policy.
            if pol == InjectedPolicy.IGNORE:
                pressed = state.pressed_keys  # physical-only
            elif pol == InjectedPolicy.ONLY:
                pressed = state.pressed_keys_injected or set()  # injected-only
            else:
                # ALLOW: match in the event's domain (do not use pressed_keys_all).
                if inj:
                    inj_keys = state.pressed_keys_injected or set()
                    phys_mods = {vk for vk in state.pressed_keys if is_modifier_vk(vk)}
                    pressed = inj_keys | phys_mods
                else:
                    pressed = state.pressed_keys

            is_down = event.action in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up = event.action in (WM_KEYUP, WM_SYSKEYUP)
            is_repeat = bool(getattr(event, "_sb_is_repeat", False))
            fresh_down = is_down and not is_repeat

            prev_full = self._was_full
            full = self._match_chord(chord, pressed)
            self._armed = full

            # Track activation cycle: once chord was fully pressed.
            if full:
                self._had_full = True

            # Rearm ON_RELEASE every time chord becomes full (not_full -> full).
            if full and not prev_full:
                self._release_armed = True

            # Is any chord key still held?
            any_chord_key_pressed = False
            for vk in chord.allowed_union:
                if vk in pressed:
                    any_chord_key_pressed = True
                    break

            vk_evt = int(event.vkCode)

            flags = winput.WP_CONTINUE

            # --- WHILE_ACTIVE / WHILE_EVALUATING (only these differ) ---
            sup = self.config.suppress
            relevant = (vk_evt in chord.allowed_union) or is_modifier_vk(vk_evt)

            if sup == SuppressPolicy.ALWAYS:
                flags |= winput.WP_DONT_PASS_INPUT_ON

            elif sup == SuppressPolicy.WHILE_ACTIVE:
                # suppress only when chord is fully active
                if self._armed and relevant:
                    flags |= winput.WP_DONT_PASS_INPUT_ON

            elif sup == SuppressPolicy.WHILE_EVALUATING:
                # suppress already during chord evaluation (partial progress)
                in_progress = full or prev_full
                if not in_progress:
                    for vk in chord.allowed_union:
                        if vk in pressed:
                            in_progress = True
                            break
                    if not in_progress:
                        for vk in pressed:
                            if is_modifier_vk(vk):
                                in_progress = True
                                break
                if in_progress and relevant:
                    flags |= winput.WP_DONT_PASS_INPUT_ON
            # --- end suppress ---

            trig = self.config.trigger

            def fire_if_allowed(ts_ms: int) -> bool:
                if self._cooldown_ok(ts_ms) and self._max_fires_ok():
                    self._fires += 1
                    self._last_fire_ms = ts_ms
                    self._fire_async()
                    return True
                return False

            # Sequence
            if self.is_sequence:
                if full and fresh_down:
                    self._seq_last_ms = now_ms
                    if self._seq_index == len(self.steps) - 1:
                        if trig in (Trigger.ON_SEQUENCE, Trigger.ON_PRESS, Trigger.ON_CHORD_COMPLETE):
                            if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                                flags |= winput.WP_DONT_PASS_INPUT_ON
                        self.reset()
                    else:
                        self._seq_index += 1

                self._was_full = full
                if not any_chord_key_pressed:
                    self._had_full = False
                    self._release_armed = False
                return flags

            # -------------------------
            # Single chord triggers
            # -------------------------

            if trig == Trigger.ON_PRESS and full and fresh_down:
                # Fires on fresh keydown while chord is full
                if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                    flags |= winput.WP_DONT_PASS_INPUT_ON

            elif trig == Trigger.ON_CHORD_COMPLETE and full and fresh_down and not prev_full:
                # Fires only on transition NOT_FULL -> FULL
                if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                    flags |= winput.WP_DONT_PASS_INPUT_ON

            elif trig == Trigger.ON_RELEASE:
                # Fires after a completion (full) happened; rearmed each time the chord becomes full again.
                # Example: hold Ctrl, tap E -> callback on each E release.
                if self._had_full and self._release_armed and is_up and (vk_evt in chord.allowed_union):
                    if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                        flags |= winput.WP_DONT_PASS_INPUT_ON
                    self._release_armed = False

            elif trig == Trigger.ON_CHORD_RELEASED:
                # Fires when ALL chord keys are released AFTER chord was fully pressed.
                if self._had_full and is_up and (vk_evt in chord.allowed_union) and (not any_chord_key_pressed):
                    if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                        flags |= winput.WP_DONT_PASS_INPUT_ON
                    # end cycle
                    self._had_full = False
                    self._release_armed = False

            elif trig == Trigger.ON_CLICK:
                if full and fresh_down:
                    self._click_down_ms = now_ms
                elif is_up and self._click_down_ms is not None:
                    dur = now_ms - self._click_down_ms
                    self._click_down_ms = None
                    if dur <= self.config.timing.hold_ms:
                        if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                            flags |= winput.WP_DONT_PASS_INPUT_ON

            elif trig == Trigger.ON_HOLD:
                if full and fresh_down:
                    hold_ms = self.config.timing.hold_ms
                    chord0 = chord
                    pressed0 = pressed

                    self._hold_token += 1
                    token = self._hold_token

                    def _hold() -> None:
                        time.sleep(max(0, hold_ms) / 1000.0)
                        with self._lock:
                            if token != self._hold_token or not self._window_ok():
                                return
                            if self._match_chord(chord0, pressed0):
                                now2 = int(time.monotonic() * 1000)
                                fire_if_allowed(now2)

                    threading.Thread(target=_hold, daemon=True).start()

            elif trig == Trigger.ON_REPEAT:
                if full and is_down and not self._repeat_active:
                    self._repeat_active = True
                    delay_s = max(self.config.timing.hold_ms, self.config.timing.repeat_delay_ms) / 1000.0
                    interval_s = max(1, self.config.timing.repeat_interval_ms) / 1000.0
                    chord0 = chord
                    pressed0 = pressed

                    def _repeat() -> None:
                        time.sleep(max(0.0, delay_s))
                        while True:
                            with self._lock:
                                if not self._match_chord(chord0, pressed0) or not self._window_ok():
                                    self._repeat_active = False
                                    break
                                now2 = int(time.monotonic() * 1000)
                                fire_if_allowed(now2)
                            time.sleep(interval_s)

                    threading.Thread(target=_repeat, daemon=True).start()

            elif trig == Trigger.ON_DOUBLE_TAP and full and fresh_down:
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

            # end cycle if fully released
            if not any_chord_key_pressed:
                self._had_full = False
                self._release_armed = False

            self._was_full = full
            return flags
