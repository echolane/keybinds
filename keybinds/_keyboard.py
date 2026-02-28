from __future__ import annotations

import threading
import time
from typing import Callable, Optional, Set, TYPE_CHECKING

from . import winput

from .types import (
    Callback,
    BindConfig,
    ChordPolicy,
    SuppressPolicy,
    InjectedPolicy,
    OrderPolicy,
    Trigger
)
from ._constants import (
    WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP,
    is_modifier_vk,
)
from ._parsing import _ChordSpec, parse_key_expr
from ._base_bind import BaseBind

if TYPE_CHECKING:
    from ._state import InputState


class _StrictOrderState:
    """
    Runtime state for strict ordered-chord matching (one chord / one sequence step).

    Supports two modes:
    - STRICT_ORDER:
      any order violation invalidates the whole chord-cycle until all chord keys are released.
    - STRICT_ORDER_RECOVERABLE:
      tail rebuild mistakes are recoverable while the locked prefix is still held.

    Model:
    - Chord order is defined by chord.groups indices: 0, 1, 2, ...
    - Current pressed chord groups must form a prefix [0..k].
    - Before first full match:
      first-seen groups must appear in order (0 -> 1 -> 2 -> ...).
    - After first full match:
      a locked prefix is established (all groups except the last one).
      The user may rebuild only the right-side tail.
      The locked prefix may shrink only by releasing keys from right to left.

    Examples for Ctrl+Shift+X:
    - Allowed:
      * Ctrl+Shift+X
      * X up -> X down
      * X up -> Shift up -> Shift down -> X down (Ctrl still held)
    - Invalid (fatal):
      * Shift+Ctrl+X
      * Ctrl up while Shift+X are still held (locked prefix broken)
    - Invalid (recoverable only in RECOVERABLE mode):
      * after releasing Shift+X, pressing X before Shift (malformed tail)
    """

    __slots__ = (
        "invalid",
        "seen_groups",
        "seen_set",
        "locked_prefix_len",  # None before first success; after success = len(groups)-1 and may shrink
        "attempt_invalid",  # recoverable local error for current tail rebuild attempt
    )

    def __init__(self) -> None:
        self.invalid: bool = False
        self.attempt_invalid: bool = False
        self.seen_groups: list[int] = []
        self.seen_set: Set[int] = set()
        self.locked_prefix_len: Optional[int] = None

    def reset(self) -> None:
        self.invalid = False
        self.attempt_invalid: bool = False
        self.seen_groups.clear()
        self.seen_set.clear()
        self.locked_prefix_len = None

    # ---------- helpers ----------
    def group_index_for_vk(self, chord: _ChordSpec, vk: int) -> Optional[int]:
        for i, g in enumerate(chord.groups):
            if vk in g:
                return i
        return None

    def pressed_group_indices(self, chord: _ChordSpec, pressed: Set[int]) -> list[int]:
        out: list[int] = []
        for i, g in enumerate(chord.groups):
            if any(vk in pressed for vk in g):
                out.append(i)
        return out

    @staticmethod
    def _is_prefix_indices(idxs: list[int]) -> bool:
        return idxs == list(range(len(idxs)))

    # ---------- state transitions ----------
    def on_event(
        self,
        chord: "_ChordSpec",
        pressed: Set[int],
        *,
        vk_evt: int,
        is_up: bool,
        fresh_down: bool,
        recoverable: bool = False,
    ) -> None:
        """
        `pressed` must be post-event state.

        Modes:
        - STRICT (recoverable=False):
            any order violation invalidates the whole chord-cycle.
        - STRICT_RECOVERABLE (recoverable=True):
            tail rebuild mistakes can be retried while a valid locked prefix is still held.
            Fatal only if locked prefix itself is broken.
        """
        if self.invalid:
            return

        # ---- helpers on current post-event state ----
        pressed_idxs = self.pressed_group_indices(chord, pressed)   # e.g. [0], [0,1], [0,1,2], [0,2], ...
        is_prefix = self._is_prefix_indices(pressed_idxs)

        # ---- maintain lock (after first success only) ----
        # locked_prefix_len means groups [0:locked_prefix_len] are the locked prefix.
        # It may shrink only as the user releases the tail from the right.
        if self.locked_prefix_len is not None:
            if is_prefix and len(pressed_idxs) < self.locked_prefix_len:
                self.locked_prefix_len = len(pressed_idxs)

        if recoverable and self.locked_prefix_len is not None:
            # Clear local tail-attempt error only when user has returned to a VALID prefix state
            # at or above the tail base (or earlier), e.g. [0] for Ctrl+Shift+X after releasing Shift+X.
            if is_prefix and len(pressed_idxs) <= self.locked_prefix_len:
                self.attempt_invalid = False

        # ---- prefix invariant handling ----
        if not is_prefix:
            # Before first success any non-prefix state is fatal.
            if self.locked_prefix_len is None:
                self.invalid = True
                return

            # After first success:
            # - If locked prefix is broken -> fatal
            # - If locked prefix is still intact and only tail is malformed -> recoverable in RECOVERABLE mode
            prefix_ok = pressed_idxs[: self.locked_prefix_len] == list(range(self.locked_prefix_len))

            if not prefix_ok:
                # Example: Ctrl+Shift+X, then Ctrl up while Shift+X still held => [1,2]
                self.invalid = True
                return

            # Locked prefix still held; malformed tail (e.g. [0,2]) is a local tail-attempt error.
            if recoverable:
                self.attempt_invalid = True
                return
            else:
                self.invalid = True
                return

        # Non-chord key does not affect order bookkeeping beyond prefix checks above.
        if vk_evt not in chord.allowed_union:
            return

        gi = self.group_index_for_vk(chord, vk_evt)
        if gi is None:
            return

        # ---- keydown semantics ----
        if fresh_down:
            if self.locked_prefix_len is None:
                # Before first success: first-seen groups must arrive in order 0,1,2,...
                if gi not in self.seen_set:
                    expected = len(self.seen_groups)
                    if gi != expected:
                        self.invalid = True
                        return
                    self.seen_groups.append(gi)
                    self.seen_set.add(gi)
                # Re-press before first success is tolerated if state invariant is ok.
                return

            # After first success:
            # Groups in locked prefix may NOT be re-pressed (they must remain continuously held).
            if gi < self.locked_prefix_len:
                self.invalid = True
                return

            # Tail rebuild order (left-to-right from locked_prefix_len).
            # We only enforce this when current state is prefix-shaped; malformed tail is handled above.
            if is_prefix:
                # post-event pressed is prefix [0..k], so the newly pressed group must be the rightmost (k)
                expected_gi = len(pressed_idxs) - 1
                if gi != expected_gi:
                    if recoverable:
                        self.attempt_invalid = True
                    else:
                        self.invalid = True
                    return

        # ---- keyup semantics ----
        # No extra per-key logic needed here beyond:
        # - prefix handling above
        # - locked_prefix_len shrink above
        # - recoverable attempt reset above

    def allows_full(self, chord: _ChordSpec, pressed: Set[int], *, recoverable: bool = False) -> bool:
        if self.invalid:
            return False
        if recoverable and self.attempt_invalid:
            return False
        idxs = self.pressed_group_indices(chord, pressed)
        return self._is_prefix_indices(idxs)

    def on_full_rising_edge(self, chord: _ChordSpec) -> None:
        if self.locked_prefix_len is None:
            # Lock all but the last group.
            self.locked_prefix_len = max(0, len(chord.groups) - 1)


class Bind(BaseBind):
    """Policy-driven keyboard bind."""

    def __init__(
        self,
        expr: str,
        callback: Callback,
        *,
        config: Optional[BindConfig] = None,
        hwnd: Optional[int] = None,
        dispatch: Optional[Callable[[Callback], None]] = None,
    ) -> None:
        super().__init__(callback, config=config or BindConfig(), hwnd=hwnd, dispatch=dispatch)
        self.expr = expr
        self.steps = parse_key_expr(expr)
        self.is_sequence = len(self.steps) > 1

        # runtime state
        self._seq_index: int = 0
        self._seq_last_ms: int = 0

        self._last_event_ms: int = 0

        self._click_down_ms: Optional[int] = None
        self._armed: bool = False
        self._was_full: bool = False
        self._tap_count: int = 0
        self._tap_last_ms: int = 0

        # for ON_CHORD_RELEASED semantics
        self._had_full: bool = False
        self._release_armed: bool = False
        self._invalidated: bool = False

        self._strict_order = _StrictOrderState()

    def reset(self) -> None:
        self._seq_index = 0
        self._seq_last_ms = 0
        self._click_down_ms = None
        self._tap_count = 0
        self._tap_last_ms = 0
        self._hold_token += 1
        self._armed = False
        self._was_full = False
        self._had_full = False
        self._release_armed: bool = False
        self._invalidated = False
        self._repeat_active = False
        self._strict_order.reset()

    def _debounce_ok(self, now_ms: int) -> bool:
        db = self.config.timing.debounce_ms
        return db <= 0 or (now_ms - self._last_event_ms) >= db

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

    def handle(self, event: winput.KeyboardEvent, state: InputState) -> int:
        # Keep hook path tiny: avoid heavy work unless needed.
        with self._lock:
            now_ms = int(event.time)

            if self.window is not None and not self._window_ok():
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

            vk_evt = int(event.vkCode)
            is_down = event.action in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up = event.action in (WM_KEYUP, WM_SYSKEYUP)
            is_repeat = bool(getattr(event, "_sb_is_repeat", False))
            fresh_down = is_down and (self.config.constraints.allow_os_key_repeat or not is_repeat)

            opol = self.config.constraints.order_policy
            is_strict = opol in (OrderPolicy.STRICT, OrderPolicy.STRICT_RECOVERABLE)
            is_recoverable = (opol == OrderPolicy.STRICT_RECOVERABLE)

            if is_strict:
                self._strict_order.on_event(
                    chord,
                    pressed,
                    vk_evt=vk_evt,
                    is_up=is_up,
                    fresh_down=fresh_down,
                    recoverable=is_recoverable
                )

            prev_full = self._was_full
            full = self._match_chord(chord, pressed)
            if is_strict and full:
                if not self._strict_order.allows_full(chord, pressed, recoverable=is_recoverable):
                    full = False

            if is_strict and full and not prev_full:
                self._strict_order.on_full_rising_edge(chord)

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
                    self._fire()
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
                        self._strict_order.reset()

                self._was_full = full
                if not any_chord_key_pressed:
                    self._had_full = False
                    self._release_armed = False
                    self._strict_order.reset()
                return flags

            # -------------------------
            # Single chord triggers
            # -------------------------

            if trig == Trigger.ON_PRESS and full and fresh_down and (vk_evt in chord.allowed_union):
                # Fires on fresh keydown while chord is full
                if fire_if_allowed(now_ms) and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                    flags |= winput.WP_DONT_PASS_INPUT_ON

            elif trig == Trigger.ON_CHORD_COMPLETE and full and fresh_down and not prev_full and (vk_evt in chord.allowed_union):
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
                    self._strict_order.reset()

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
                            if token != self._hold_token or not self._window_ok(force=True):
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
                                if not self._match_chord(chord0, pressed0) or not self._window_ok(force=True):
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
                self._strict_order.reset()

            self._was_full = full
            return flags
