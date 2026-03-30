"""Logical keyboard bind implementation.

This module contains the runtime matcher behind ``Hook.bind_logical(...)``.
It sits between low-level hook events and high-level logical expressions such
as ``ctrl+A``, ``\\,`` or mixed sequences like ``ctrl+A,shift+B``.

What this module is responsible for
-----------------------------------
- parse-time data from :mod:`keybinds.logical.parsing` is consumed here
- physical keyboard events are translated into logical characters using
  :class:`LogicalTranslator`
- current pressed-state is re-evaluated on every event so matching follows the
  *current* layout and modifiers instead of cached VK -> char guesses
- normal bind mechanics from :class:`BaseBind` still apply: triggers,
  suppression, injected-input policy, cooldown, timing and diagnostics

What it does *not* do
---------------------
- it is not the text-stream matcher used by ``bind_text(...)`` or
  ``add_abbreviation(...)``; those live in :mod:`keybinds.logical.abbreviation`
- it does not try to preserve a textual editing history; it only reasons about
  the current event, the current pressed keys and the active logical sequence

Useful entry points when reading the code
----------------------------------------
- ``handle()``: main event pipeline
- ``_handle_text_sequence()``: fast path for char-only sequences like ``a,b,c``
- ``_compute_pressed_chars_snapshot()``: rebuilds logical chars for the current
  pressed keys using the current layout/modifier state
- ``_match_chord()``: checks one logical chord against current VK + char state
- ``_LogicalStrictOrderState``: enforces STRICT / STRICT_RECOVERABLE order

Developer note
--------------
This module is intentionally implementation-heavy. For a guided explanation of
the state fields, matching pipeline, and common debugging paths, see
``Developer Notes - Logical.md`` in the project root.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Optional, Set, Dict, List, Tuple

from .. import winput
from ..types import (
    Callback,
    BindConfig,
    ChordPolicy,
    SuppressPolicy,
    InjectedPolicy,
    OrderPolicy,
    Trigger,
    LogicalConfig,
    OsKeyRepeatPolicy,
    TextBackspacePolicy,
)
from .._constants import (
    WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP,
    VK_SHIFT, VK_LSHIFT, VK_RSHIFT, VK_CAPITAL, VK_NUMLOCK, VK_SCROLL,
    VK_CONTROL, VK_LCONTROL, VK_RCONTROL, VK_MENU, VK_LMENU, VK_RMENU,
    VK_LWIN, VK_RWIN, VK_BACK,
    is_modifier_vk,
)
from .parsing import _LogicalChordSpec, _LogicalVkGroup, _LogicalCharGroup, parse_logical_expr, text_to_logical_expr
from .translate import LogicalTranslator
from ..diagnostics import _DiagnosticsManager
from .._base_bind import BaseBind
from .._state import InputState


_LOGICAL_TOGGLE_KEYS = {VK_CAPITAL, VK_NUMLOCK, VK_SCROLL}


def _is_logical_ignorable_vk(vk: int, logical_config: LogicalConfig) -> bool:
    if logical_config.ignore_modifier_keys and is_modifier_vk(vk):
        return True
    if logical_config.ignore_toggle_keys and vk in _LOGICAL_TOGGLE_KEYS:
        return True
    return False



class _LogicalStrictOrderState:
    __slots__ = (
        "invalid",
        "attempt_invalid",
        "seen_groups",
        "seen_set",
        "locked_prefix_len",
    )

    def __init__(self) -> None:
        self.invalid = False
        self.attempt_invalid = False
        self.seen_groups: List[int] = []
        self.seen_set: Set[int] = set()
        self.locked_prefix_len: Optional[int] = None

    def reset(self) -> None:
        self.invalid = False
        self.attempt_invalid = False
        self.seen_groups.clear()
        self.seen_set.clear()
        self.locked_prefix_len = None

    def group_index_for_event(self, chord: _LogicalChordSpec, vk_evt: int, event_char: Optional[str], normalize) -> Optional[int]:
        evt = normalize(event_char) if event_char is not None else None
        for i, g in enumerate(chord.groups):
            if isinstance(g, _LogicalVkGroup) and vk_evt in g.vks:
                return i
            if isinstance(g, _LogicalCharGroup) and evt == normalize(g.char):
                return i
        return None

    def pressed_group_indices(self, chord: _LogicalChordSpec, pressed_vks: Set[int], pressed_chars: Set[str], normalize) -> List[int]:
        norm_pressed = {normalize(ch) for ch in pressed_chars}
        out: List[int] = []
        for i, g in enumerate(chord.groups):
            if isinstance(g, _LogicalVkGroup):
                if pressed_vks & set(g.vks):
                    out.append(i)
            elif normalize(g.char) in norm_pressed:
                out.append(i)
        return out

    @staticmethod
    def _is_prefix_indices(idxs: List[int]) -> bool:
        return idxs == list(range(len(idxs)))

    def on_event(
        self,
        chord: _LogicalChordSpec,
        pressed_vks: Set[int],
        pressed_chars: Set[str],
        *,
        vk_evt: int,
        event_char: Optional[str],
        fresh_down: bool,
        normalize,
        recoverable: bool = False,
    ) -> None:
        if self.invalid:
            return

        pressed_idxs = self.pressed_group_indices(chord, pressed_vks, pressed_chars, normalize)
        is_prefix = self._is_prefix_indices(pressed_idxs)

        if self.locked_prefix_len is not None:
            if is_prefix and len(pressed_idxs) < self.locked_prefix_len:
                self.locked_prefix_len = len(pressed_idxs)

        if recoverable and self.locked_prefix_len is not None:
            if is_prefix and len(pressed_idxs) <= self.locked_prefix_len:
                self.attempt_invalid = False

        if not is_prefix:
            if self.locked_prefix_len is None:
                self.invalid = True
                return

            prefix_ok = pressed_idxs[: self.locked_prefix_len] == list(range(self.locked_prefix_len))
            if not prefix_ok:
                self.invalid = True
                return

            if recoverable:
                self.attempt_invalid = True
                return
            self.invalid = True
            return

        gi = self.group_index_for_event(chord, vk_evt, event_char, normalize)
        if gi is None:
            return

        if fresh_down:
            if self.locked_prefix_len is None:
                if gi not in self.seen_set:
                    expected = len(self.seen_groups)
                    if gi != expected:
                        self.invalid = True
                        return
                    self.seen_groups.append(gi)
                    self.seen_set.add(gi)
                return

            if gi < self.locked_prefix_len:
                self.invalid = True
                return

            if is_prefix:
                expected_gi = len(pressed_idxs) - 1
                if gi != expected_gi:
                    if recoverable:
                        self.attempt_invalid = True
                    else:
                        self.invalid = True
                    return

    def allows_full(self, chord: _LogicalChordSpec, pressed_vks: Set[int], pressed_chars: Set[str], normalize, *, recoverable: bool = False) -> bool:
        if self.invalid:
            return False
        if recoverable and self.attempt_invalid:
            return False
        idxs = self.pressed_group_indices(chord, pressed_vks, pressed_chars, normalize)
        return self._is_prefix_indices(idxs)

    def on_full_rising_edge(self, chord: _LogicalChordSpec) -> None:
        if self.locked_prefix_len is None:
            self.locked_prefix_len = max(0, len(chord.groups) - 1)


class LogicalBind(BaseBind[winput.KeyboardEvent]):
    """Runtime matcher for layout-aware logical keyboard expressions.

    ``LogicalBind`` evaluates expressions produced by ``parse_logical_expr()``.
    Each step is a logical chord made of VK groups and/or logical characters.
    On every hook event the bind:

    1. reads the current pressed VK state from :class:`InputState`
    2. resolves modifiers and active layout
    3. translates pressed keys into logical characters
    4. matches the current chord or advances/resets the current sequence

    The class has a dedicated char-only text-sequence path for expressions such
    as ``a,b,c``. That path is still part of ``bind_logical(...)``; it is not
    the same matcher used by ``bind_text(...)``.
    """

    def __init__(
        self,
        expr: str,
        callback: Callback,
        *,
        config: Optional[BindConfig] = None,
        hwnd: Optional[int] = None,
        dispatch: Optional[Callable[..., None]] = None,
        diagnostics: Optional[_DiagnosticsManager] = None,
        logical_config: Optional[LogicalConfig] = None,
    ) -> None:
        super().__init__(callback, config=config or BindConfig(), hwnd=hwnd, dispatch=dispatch, diagnostics=diagnostics)
        self.expr = expr
        self.logical_config = logical_config or LogicalConfig()
        self._set_diagnostics_identity(self.expr, "keyboard")
        self.steps = parse_logical_expr(expr)
        self.is_sequence = len(self.steps) > 1

        self._translator = LogicalTranslator()
        self._caps_on = self._translator.capslock_on()

        self._seq_index = 0
        self._seq_last_ms = 0
        self._last_event_ms = 0
        self._click_down_ms: Optional[int] = None
        self._armed = False
        self._was_full = False
        self._tap_count = 0
        self._tap_last_ms = 0
        self._press_suppress_vk: Optional[int] = None
        self._had_full = False
        self._release_armed = False
        self._invalidated = False
        self._strict_order = _LogicalStrictOrderState()

        self._text_sequence = self._build_text_sequence()
        self._text_sequence_buffer = deque(maxlen=len(self._text_sequence)) if self._text_sequence is not None else None

    @classmethod
    def text(cls, text: str) -> str:
        return text_to_logical_expr(text)

    @classmethod
    def abbreviation(cls, text: str) -> str:
        return text_to_logical_expr(text)


    def _build_text_sequence(self) -> Optional[Tuple[str, ...]]:
        if not self.is_sequence:
            return None
        chars = []
        for step in self.steps:
            if len(step.groups) != 1:
                return None
            g = step.groups[0]
            if not isinstance(g, _LogicalCharGroup):
                return None
            chars.append(g.char)
        return tuple(chars)

    def _resolved_backspace_policy(self) -> TextBackspacePolicy:
        legacy = self.logical_config.text_backspace_edits_buffer
        if legacy is True:
            return TextBackspacePolicy.EDIT_BUFFER
        if legacy is False:
            return TextBackspacePolicy.IGNORE
        return self.logical_config.text_backspace_policy

    def _reset_text_sequence_buffer(self) -> None:
        if self._text_sequence_buffer is not None:
            self._text_sequence_buffer.clear()

    @staticmethod
    def _mods_with_win_from_pressed(pressed: Set[int]) -> Tuple[bool, bool, bool, bool, bool]:
        shift = any(vk in pressed for vk in (VK_SHIFT, VK_LSHIFT, VK_RSHIFT))
        ctrl = any(vk in pressed for vk in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL))
        ralt = VK_RMENU in pressed
        lalt = any(vk in pressed for vk in (VK_MENU, VK_LMENU))
        altgr = ralt and ctrl
        alt = lalt or (ralt and not altgr)
        win = any(vk in pressed for vk in (VK_LWIN, VK_RWIN))
        return shift, ctrl, alt, altgr, win

    # Char-only logical sequences (for example ``a,b,c``) are handled
    # separately from the general chord/sequence engine below. This path tracks
    # the produced characters directly and avoids the stricter chord-state rules
    # that are needed for mixed logical chords.
    def _handle_text_sequence(self, event: winput.KeyboardEvent, state: InputState, trace, now_ms: int, inj: bool) -> Optional[int]:
        if self._text_sequence is None or self._text_sequence_buffer is None:
            return None

        vk_evt = int(event.vkCode)
        is_down = event.action in (WM_KEYDOWN, WM_SYSKEYDOWN)
        is_up = event.action in (WM_KEYUP, WM_SYSKEYUP)
        if is_up:
            return winput.WP_CONTINUE
        if not is_down:
            return winput.WP_CONTINUE

        is_repeat = bool(getattr(event, "_sb_is_repeat", False))
        repeat_policy = self._resolved_repeat_policy()
        if is_repeat and repeat_policy == OsKeyRepeatPolicy.RESET:
            self._reset_text_sequence_buffer()
            trace.skip("repeat_reset_text_sequence")
            return winput.WP_CONTINUE
        fresh_down = (repeat_policy == OsKeyRepeatPolicy.MATCH) or not is_repeat
        if not fresh_down:
            trace.skip("repeat_ignored_text_sequence")
            return winput.WP_CONTINUE

        if vk_evt == VK_CAPITAL:
            self._caps_on = not self._caps_on
            if self.logical_config.ignore_toggle_keys:
                return winput.WP_CONTINUE
        elif vk_evt in _LOGICAL_TOGGLE_KEYS:
            if self.logical_config.ignore_toggle_keys:
                return winput.WP_CONTINUE
            if self.logical_config.text_clear_buffer_on_non_text:
                self._reset_text_sequence_buffer()
            return winput.WP_CONTINUE

        pressed_for_translation = self._get_pressed_for_policy(state, inj=inj)
        shift, ctrl, alt, altgr, win = self._mods_with_win_from_pressed(pressed_for_translation)

        if vk_evt == VK_BACK and not ctrl and not alt and not win:
            backspace_policy = self._resolved_backspace_policy()
            if backspace_policy == TextBackspacePolicy.EDIT_BUFFER:
                if self._text_sequence_buffer:
                    self._text_sequence_buffer.pop()
            elif backspace_policy == TextBackspacePolicy.CLEAR_BUFFER:
                self._reset_text_sequence_buffer()
            elif backspace_policy == TextBackspacePolicy.CLEAR_WORD:
                # The char-only logical sequence path keeps only a small matcher buffer,
                # not a full text stream, so it cannot reliably remove just the current
                # word fragment. Treat CLEAR_WORD the same as CLEAR_BUFFER here.
                self._reset_text_sequence_buffer()
            return winput.WP_CONTINUE

        ignore_combo = (win and self.logical_config.text_ignore_win_combos) or (ctrl and self.logical_config.text_ignore_ctrl_combos) or (alt and self.logical_config.text_ignore_alt_combos)
        if ignore_combo:
            trace.skip("text_sequence_modifier_combo_ignored", ctrl=ctrl, alt=alt, win=win, altgr=altgr)
            return winput.WP_CONTINUE

        layout = self._translator.current_layout()
        ch = self._translator.to_char(
            vk=vk_evt,
            scan_code=int(getattr(event, "scanCode", 0) or 0),
            flags=int(getattr(event, "flags", 0) or 0),
            shift=shift,
            ctrl=ctrl,
            alt=alt,
            altgr=altgr,
            caps=self._effective_caps(),
            layout=layout,
        )
        if not ch:
            if self.logical_config.text_clear_buffer_on_non_text:
                self._reset_text_sequence_buffer()
            trace.skip("text_sequence_no_char")
            return winput.WP_CONTINUE

        self._text_sequence_buffer.append(ch)
        current = tuple(self._normalize_char(c) for c in self._text_sequence_buffer)
        target = tuple(self._normalize_char(c) for c in self._text_sequence)
        trace.note("decision", "text_sequence_buffer", current=list(self._text_sequence_buffer), target=list(self._text_sequence), repeat_policy=repeat_policy.name)
        if len(current) < len(target) or current[-len(target):] != target:
            return winput.WP_CONTINUE

        flags = winput.WP_CONTINUE
        trig = self.config.trigger
        if trig in (Trigger.ON_SEQUENCE, Trigger.ON_PRESS, Trigger.ON_CHORD_COMPLETE):
            if self.can_fire_now(now_ms, trace=trace):
                self._fires += 1
                self._last_fire_ms = now_ms
                dispatch_trace = trace.fire(trigger="logical_text_sequence", seq_text="".join(self._text_sequence))
                self._fire(dispatch_trace)
                if self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_when_matched", trigger=trig.name.lower())
            self._reset_text_sequence_buffer()
        return flags

    def _normalize_char(self, ch: Optional[str]) -> Optional[str]:
        if ch is None:
            return None
        return ch if self.logical_config.case_sensitive else ch.casefold()

    def _effective_caps(self) -> bool:
        return self._caps_on if self.logical_config.respect_caps_lock else False

    def _resolved_repeat_policy(self) -> OsKeyRepeatPolicy:
        if self.logical_config.os_key_repeat_policy == OsKeyRepeatPolicy.IGNORE and self.config.constraints.allow_os_key_repeat:
            return OsKeyRepeatPolicy.MATCH
        return self.logical_config.os_key_repeat_policy

    def reset(self, *, keep_press_suppress_vk: bool = False) -> None:
        self._seq_index = 0
        self._seq_last_ms = 0
        self._click_down_ms = None
        self._tap_count = 0
        self._tap_last_ms = 0
        self._hold_token += 1
        self._armed = False
        self._was_full = False
        self._had_full = False
        self._release_armed = False
        self._invalidated = False
        self._strict_order.reset()
        self._reset_text_sequence_buffer()
        if not keep_press_suppress_vk:
            self._press_suppress_vk = None

    def _debounce_ok(self, now_ms: int) -> bool:
        db = self.config.timing.debounce_ms
        return db <= 0 or (now_ms - self._last_event_ms) >= db

    def _step_timeout_ok(self, now_ms: int) -> bool:
        to = self.config.timing.chord_timeout_ms
        if not self.is_sequence or self._seq_index == 0:
            return True
        return (now_ms - self._seq_last_ms) <= to

    @staticmethod
    def _mods_from_pressed(pressed: Set[int]) -> Tuple[bool, bool, bool, bool]:
        shift = any(vk in pressed for vk in (VK_SHIFT, VK_LSHIFT, VK_RSHIFT))
        ctrl = any(vk in pressed for vk in (getattr(winput, "VK_CONTROL", 0x11), getattr(winput, "VK_LCONTROL", 0xA2), getattr(winput, "VK_RCONTROL", 0xA3)))
        ralt = getattr(winput, "VK_RMENU", 0xA5) in pressed
        lalt = any(vk in pressed for vk in (getattr(winput, "VK_MENU", 0x12), getattr(winput, "VK_LMENU", 0xA4)))
        altgr = ralt and ctrl
        alt = lalt or (ralt and not altgr)
        return shift, ctrl, alt, altgr

    def _get_pressed_for_policy(self, state: InputState, *, inj: bool) -> Set[int]:
        pol = self.config.injected
        if pol == InjectedPolicy.IGNORE:
            return set(state.pressed_keys)
        if pol == InjectedPolicy.ONLY:
            return set(state.pressed_keys_injected or ())
        if inj:
            inj_keys = set(state.pressed_keys_injected or ())
            phys_mods = {vk for vk in state.pressed_keys if is_modifier_vk(vk)}
            return inj_keys | phys_mods
        return set(state.pressed_keys)

    # Rebuild logical characters for the *current* pressed-key snapshot.
    #
    # This is the core of layout-aware matching for logical chords. We do not
    # cache VK -> char globally because the result depends on the active layout,
    # Shift/AltGr/CapsLock and, for the current event, real scanCode/flags.
    def _compute_pressed_chars_snapshot(
        self,
        pressed_vks: Set[int],
        *,
        layout: int,
        shift: bool,
        ctrl: bool,
        alt: bool,
        altgr: bool,
        event_vk: Optional[int] = None,
        event_scan_code: int = 0,
        event_flags: int = 0,
    ) -> Dict[int, str]:
        chars: Dict[int, str] = {}
        caps = self._effective_caps()
        for vk in pressed_vks:
            if is_modifier_vk(vk) or vk in _LOGICAL_TOGGLE_KEYS:
                continue
            scan_code = event_scan_code if (event_vk is not None and vk == event_vk and event_scan_code) else 0
            flags = event_flags if (event_vk is not None and vk == event_vk) else 0
            ch = self._translator.to_char(
                vk=vk,
                scan_code=scan_code,
                flags=flags,
                shift=shift,
                ctrl=ctrl,
                alt=alt,
                altgr=altgr,
                caps=caps,
                layout=layout,
            )
            if ch is not None:
                chars[vk] = ch
        return chars

    def _group_present(self, group, pressed_vks: Set[int], pressed_chars: Dict[int, str]) -> bool:
        if isinstance(group, _LogicalVkGroup):
            return bool(pressed_vks & set(group.vks))
        expected = self._normalize_char(group.char)
        return expected in {self._normalize_char(ch) for ch in pressed_chars.values()}

    # Match one parsed logical chord against the current VK snapshot plus the
    # reconstructed logical characters. ``ChordPolicy`` is applied here.
    def _match_chord(self, chord: _LogicalChordSpec, pressed_vks: Set[int], pressed_chars: Dict[int, str]) -> bool:
        cpol = self.config.constraints.chord_policy

        for g in chord.groups:
            if not self._group_present(g, pressed_vks, pressed_chars):
                return False

        if cpol == ChordPolicy.RELAXED:
            return True

        allowed_chars = {self._normalize_char(ch) for ch in chord.allowed_chars}
        required_vks = set(chord.allowed_vk_union)
        ignored = self.config.constraints.ignore_keys

        for vk in pressed_vks:
            if vk in required_vks:
                continue
            char = pressed_chars.get(vk)
            if char is not None and self._normalize_char(char) in allowed_chars:
                continue
            if cpol == ChordPolicy.IGNORE_EXTRA_MODIFIERS and is_modifier_vk(vk):
                continue
            if cpol == ChordPolicy.STRICT and vk in ignored:
                continue
            return False
        return True

    def _any_chord_key_pressed(self, chord: _LogicalChordSpec, pressed_vks: Set[int], pressed_chars: Dict[int, str]) -> bool:
        for g in chord.groups:
            if self._group_present(g, pressed_vks, pressed_chars):
                return True
        return False

    # Main runtime pipeline for LogicalBind. The order here is important:
    #
    # 1. pre-checks and debounce / timeout handling
    # 2. injected-input filtering
    # 3. optional char-only sequence fast path
    # 4. rebuild current logical event context (layout, event_char, pressed_chars)
    # 5. match the current logical chord / advance sequence / fire trigger

    def _get_pressed_now(self, state: InputState) -> Set[int]:
        injected_now = bool(state.pressed_keys_injected)
        return self._get_pressed_for_policy(state, inj=injected_now)

    def is_pressed(self) -> bool:
        from .._backend import _GlobalBackend

        with self._lock:
            if self._text_sequence is not None and self._text_sequence_buffer is not None:
                current = tuple(self._normalize_char(ch) for ch in self._text_sequence_buffer)
                target = tuple(self._normalize_char(ch) for ch in self._text_sequence)
                return current == target

            if not self._window_ok(force=True):
                return False

            state = _GlobalBackend.instance().current_state_snapshot()
            pressed_vks = self._get_pressed_now(state)
            shift, ctrl, alt, altgr = self._mods_from_pressed(pressed_vks)
            layout = self._translator.current_layout()
            pressed_chars = self._compute_pressed_chars_snapshot(
                pressed_vks,
                layout=layout,
                shift=shift,
                ctrl=ctrl,
                alt=alt,
                altgr=altgr,
            )
            chord = self.steps[self._seq_index]
            full = self._match_chord(chord, pressed_vks, pressed_chars)
            if not full:
                return False

            opol = self.config.constraints.order_policy
            if opol.name.startswith("STRICT"):
                recoverable = (opol == OrderPolicy.STRICT_RECOVERABLE)
                return self._strict_order.allows_full(chord, pressed_vks, pressed_chars, recoverable=recoverable)
            return True

    def handle(self, event: winput.KeyboardEvent, state: InputState) -> int:
        with self._lock:
            trace = self._trace(event)
            now_ms = int(event.time)

            if not self._window_ok(trace=trace):
                return winput.WP_CONTINUE
            if self.config.checks.predicates and not self._checks_ok(event, state, trace=trace):
                return winput.WP_CONTINUE
            if not self._debounce_ok(now_ms):
                trace.skip("debounce_filtered", debounce_ms=self.config.timing.debounce_ms)
                return winput.WP_CONTINUE
            if not self._step_timeout_ok(now_ms):
                trace.skip("sequence_timeout", seq_index=self._seq_index)
                self.reset()

            self._last_event_ms = now_ms

            inj = bool(getattr(event, "injected", False))
            pol = self.config.injected
            if pol == InjectedPolicy.IGNORE and inj:
                trace.skip("injected_ignored")
                return winput.WP_CONTINUE
            if pol == InjectedPolicy.ONLY and not inj:
                trace.skip("injected_only_but_physical")
                return winput.WP_CONTINUE

            if self._text_sequence is not None:
                handled = self._handle_text_sequence(event, state, trace, now_ms, inj)
                if handled is not None:
                    return handled

            # Build the event-local logical context from the current hook event
            # and the current pressed-state snapshot. Everything below uses this
            # data instead of hard-coding VK assumptions.
            vk_evt = int(event.vkCode)
            is_down = event.action in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up = event.action in (WM_KEYUP, WM_SYSKEYUP)
            is_repeat = bool(getattr(event, "_sb_is_repeat", False))
            repeat_policy = self._resolved_repeat_policy()
            if is_repeat and repeat_policy == OsKeyRepeatPolicy.RESET:
                trace.skip("repeat_reset")
                self.reset()
                return winput.WP_CONTINUE
            fresh_down = is_down and ((repeat_policy == OsKeyRepeatPolicy.MATCH) or not is_repeat)

            if vk_evt == getattr(winput, "VK_CAPITAL", 0x14) and fresh_down:
                self._caps_on = not self._caps_on

            pressed_vks = self._get_pressed_for_policy(state, inj=inj)
            shift, ctrl, alt, altgr = self._mods_from_pressed(pressed_vks)
            layout = self._translator.current_layout()
            event_scan_code = int(getattr(event, "scanCode", 0) or 0)
            event_flags = int(getattr(event, "flags", 0) or 0)

            event_char: Optional[str] = None
            if is_down and fresh_down:
                event_char = self._translator.to_char(
                    vk=vk_evt,
                    scan_code=event_scan_code,
                    flags=event_flags,
                    shift=shift,
                    ctrl=ctrl,
                    alt=alt,
                    altgr=altgr,
                    caps=self._effective_caps(),
                    layout=layout,
                )
            elif is_up:
                event_char = self._translator.to_char(
                    vk=vk_evt,
                    scan_code=event_scan_code,
                    flags=event_flags,
                    shift=shift,
                    ctrl=ctrl,
                    alt=alt,
                    altgr=altgr,
                    caps=self._effective_caps(),
                    layout=layout,
                )

            # Reconstruct current logical characters for the whole pressed-key
            # snapshot. The current event gets its real scanCode/flags; the rest
            # of the pressed keys use translator fallbacks.
            chord = self.steps[self._seq_index]
            pressed_chars = self._compute_pressed_chars_snapshot(
                pressed_vks,
                layout=layout,
                shift=shift,
                ctrl=ctrl,
                alt=alt,
                altgr=altgr,
                event_vk=vk_evt if (is_down and fresh_down) else None,
                event_scan_code=event_scan_code,
                event_flags=event_flags,
            )

            opol = self.config.constraints.order_policy
            is_strict = opol in (OrderPolicy.STRICT, OrderPolicy.STRICT_RECOVERABLE)
            is_recoverable = (opol == OrderPolicy.STRICT_RECOVERABLE)
            if is_strict:
                self._strict_order.on_event(
                    chord,
                    pressed_vks,
                    set(pressed_chars.values()),
                    vk_evt=vk_evt,
                    event_char=event_char,
                    fresh_down=fresh_down,
                    normalize=self._normalize_char,
                    recoverable=is_recoverable,
                )

            prev_full = self._was_full
            full = self._match_chord(chord, pressed_vks, pressed_chars)
            if is_strict and full:
                if not self._strict_order.allows_full(chord, pressed_vks, set(pressed_chars.values()), self._normalize_char, recoverable=is_recoverable):
                    if self._strict_order.invalid:
                        trace.skip("strict_order_invalid")
                    elif self._strict_order.attempt_invalid:
                        trace.skip("strict_order_attempt_invalid")
                    full = False

            if is_strict and full and not prev_full:
                self._strict_order.on_full_rising_edge(chord)

            self._armed = full
            if full:
                self._had_full = True
            if full and not prev_full:
                self._release_armed = True
                trace.match("logical_chord_became_full", seq_index=self._seq_index)

            any_chord_key_pressed = self._any_chord_key_pressed(chord, pressed_vks, pressed_chars)
            event_targets_this_bind = (vk_evt in chord.allowed_vk_union) or (self._normalize_char(event_char) in {self._normalize_char(ch) for ch in chord.allowed_chars} if event_char is not None else False)
            diagnostic_relevant = (
                full or prev_full or self._had_full or self._release_armed or any_chord_key_pressed or (self._seq_index > 0)
                or event_targets_this_bind or (_is_logical_ignorable_vk(vk_evt, self.logical_config) and (any_chord_key_pressed or prev_full or self._seq_index > 0))
                or (self._click_down_ms is not None) or (self._tap_count > 0) or (self._press_suppress_vk is not None)
            )
            if diagnostic_relevant:
                trace.note(
                    "decision",
                    "candidate_state",
                    vk=vk_evt,
                    event_char=event_char,
                    is_down=is_down,
                    is_up=is_up,
                    is_repeat=is_repeat,
                    full=full,
                    seq_index=self._seq_index,
                    pressed_count=len(pressed_vks),
                    pressed_chars=list(pressed_chars.values()),
                    any_chord_key_pressed=any_chord_key_pressed,
                    repeat_policy=repeat_policy.name,
                )

            flags = winput.WP_CONTINUE
            sup = self.config.suppress
            relevant = event_targets_this_bind or is_modifier_vk(vk_evt)

            if sup == SuppressPolicy.ALWAYS:
                flags |= winput.WP_DONT_PASS_INPUT_ON
                trace.suppress("suppressed_always")
            elif sup == SuppressPolicy.WHILE_ACTIVE:
                if self._armed and relevant:
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_while_active", relevant=relevant)
            elif sup == SuppressPolicy.WHILE_EVALUATING:
                in_progress = full or prev_full or any_chord_key_pressed
                if in_progress and relevant:
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_while_evaluating", relevant=relevant)
            elif self.config.suppress == SuppressPolicy.WHEN_MATCHED and self._press_suppress_vk is not None:
                if vk_evt == self._press_suppress_vk:
                    if is_repeat:
                        flags |= winput.WP_DONT_PASS_INPUT_ON
                        trace.suppress("suppressed_when_matched_repeat", paired_vk=vk_evt)
                    elif is_up:
                        flags |= winput.WP_DONT_PASS_INPUT_ON
                        trace.suppress("suppressed_when_matched", paired_vk=vk_evt)
                        self._press_suppress_vk = None

            if self._press_suppress_vk is not None and (not any_chord_key_pressed):
                self._press_suppress_vk = None

            trig = self.config.trigger
            trig_name = trig.name.lower()
            suppress_when_matched = (
                self.config.suppress == SuppressPolicy.WHEN_MATCHED
                and full and not prev_full and fresh_down and event_targets_this_bind
                and trig in (Trigger.ON_RELEASE, Trigger.ON_CHORD_RELEASED)
            )

            def fire_if_allowed(ts_ms: int):
                if not self.can_fire_now(ts_ms, trace=trace):
                    return None
                self._fires += 1
                self._last_fire_ms = ts_ms
                dispatch_trace = trace.fire(trigger=trig_name, seq_index=self._seq_index)
                self._fire(dispatch_trace)
                return dispatch_trace

            # Sequence handling stays in the normal chord engine for mixed
            # expressions such as ``ctrl+A,shift+B``. Only pure char sequences
            # are routed through ``_handle_text_sequence()`` earlier.
            if self.is_sequence:
                if is_repeat and not fresh_down:
                    if diagnostic_relevant:
                        trace.skip("trigger_not_satisfied", detail="sequence_ignores_repeat")
                    return flags

                if self._seq_index > 0 and fresh_down and not event_targets_this_bind:
                    cpol = self.config.constraints.chord_policy
                    foreign_ok = False
                    if cpol == ChordPolicy.RELAXED:
                        foreign_ok = True
                    elif cpol == ChordPolicy.IGNORE_EXTRA_MODIFIERS:
                        foreign_ok = _is_logical_ignorable_vk(vk_evt, self.logical_config)
                    else:
                        foreign_ok = (vk_evt in self.config.constraints.ignore_keys)
                    if not foreign_ok:
                        trace.skip("sequence_reset_foreign_key", vk=vk_evt, seq_index=self._seq_index)
                        self.reset()
                        return flags

                if full and fresh_down:
                    self._seq_last_ms = now_ms
                    if self._seq_index == len(self.steps) - 1:
                        keep_press_suppress_vk = False
                        if trig in (Trigger.ON_SEQUENCE, Trigger.ON_PRESS, Trigger.ON_CHORD_COMPLETE):
                            fired = fire_if_allowed(now_ms)
                            if fired is not None and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                                flags |= winput.WP_DONT_PASS_INPUT_ON
                                trace.suppress("suppressed_when_matched", trigger=trig_name)
                                self._press_suppress_vk = vk_evt
                                keep_press_suppress_vk = True
                        self.reset(keep_press_suppress_vk=keep_press_suppress_vk)
                    else:
                        trace.match("sequence_advanced", seq_index=self._seq_index, next_index=self._seq_index + 1)
                        self._seq_index += 1
                        self._strict_order.reset()

                self._was_full = full
                if not any_chord_key_pressed:
                    self._had_full = False
                    self._release_armed = False
                    self._strict_order.reset()
                return flags

            if trig == Trigger.ON_PRESS and full and fresh_down and event_targets_this_bind:
                fired = fire_if_allowed(now_ms)
                if fired is not None and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_when_matched", trigger=trig_name)
                    self._press_suppress_vk = vk_evt

            elif trig == Trigger.ON_CHORD_COMPLETE and full and fresh_down and not prev_full and event_targets_this_bind:
                fired = fire_if_allowed(now_ms)
                if fired is not None and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_when_matched", trigger=trig_name)
                    self._press_suppress_vk = vk_evt

            elif trig == Trigger.ON_RELEASE:
                if suppress_when_matched and self.can_fire_now(now_ms):
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_when_matched", trigger=trig_name)
                    self._press_suppress_vk = vk_evt
                if self._had_full and self._release_armed and event_targets_this_bind and is_up:
                    fire_if_allowed(now_ms)
                    self._release_armed = False

            elif trig == Trigger.ON_CHORD_RELEASED:
                if suppress_when_matched and self.can_fire_now(now_ms):
                    flags |= winput.WP_DONT_PASS_INPUT_ON
                    trace.suppress("suppressed_when_matched", trigger=trig_name)
                    self._press_suppress_vk = vk_evt
                if self._had_full and is_up and event_targets_this_bind and (not any_chord_key_pressed):
                    fire_if_allowed(now_ms)
                    self._had_full = False
                    self._release_armed = False
                    self._strict_order.reset()

            elif trig == Trigger.ON_CLICK:
                if is_repeat:
                    if diagnostic_relevant or (self._click_down_ms is not None):
                        trace.skip("trigger_not_satisfied", detail="click_ignores_repeat")
                elif full and fresh_down:
                    self._click_down_ms = now_ms
                    trace.note("decision", "click_started")
                elif is_up and self._click_down_ms is not None:
                    dur = now_ms - self._click_down_ms
                    self._click_down_ms = None
                    if dur <= self.config.timing.hold_ms:
                        fire_if_allowed(now_ms)
                    else:
                        trace.skip("hold_not_long_enough", duration_ms=dur, hold_ms=self.config.timing.hold_ms)

            elif trig == Trigger.ON_HOLD:
                if full and fresh_down and not is_repeat:
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
                            if not self._window_ok(force=True, trace=trace):
                                trace.skip("hold_timer_cancelled", reason_detail="window_mismatch")
                                return
                            if self._armed:
                                trace.note("decision", "hold_timer_fired")
                                fire_if_allowed(int(time.monotonic() * 1000))
                            else:
                                trace.skip("hold_timer_cancelled", reason_detail="chord_not_held")

                    threading.Thread(target=_hold, daemon=True).start()

            elif trig == Trigger.ON_REPEAT:
                if full and fresh_down and not is_repeat:
                    delay_s = max(self.config.timing.hold_ms, self.config.timing.repeat_delay_ms) / 1000.0
                    interval_s = max(1, self.config.timing.repeat_interval_ms) / 1000.0
                    self._hold_token += 1
                    token = self._hold_token
                    trace.note("decision", "repeat_started", repeat_delay_ms=int(delay_s * 1000), repeat_interval_ms=int(interval_s * 1000))

                    def _repeat() -> None:
                        time.sleep(max(0.0, delay_s))
                        while True:
                            with self._lock:
                                if token != self._hold_token:
                                    trace.skip("repeat_cancelled", reason_detail="token_changed")
                                    break
                                if not self._window_ok(force=True, trace=trace):
                                    trace.skip("repeat_cancelled", reason_detail="window_mismatch")
                                    break
                                if not self._armed:
                                    trace.skip("repeat_cancelled", reason_detail="chord_not_held")
                                    break
                                trace.note("decision", "repeat_tick")
                                fire_if_allowed(int(time.monotonic() * 1000))
                            time.sleep(interval_s)

                    threading.Thread(target=_repeat, daemon=True).start()

            elif trig == Trigger.ON_DOUBLE_TAP and full and fresh_down and not is_repeat:
                win = self.config.timing.double_tap_window_ms
                if (now_ms - self._tap_last_ms) <= win:
                    self._tap_count += 1
                else:
                    self._tap_count = 1
                self._tap_last_ms = now_ms
                trace.note("decision", "double_tap_progress", tap_count=self._tap_count, window_ms=win)
                if self._tap_count >= 2:
                    self._tap_count = 0
                    fired = fire_if_allowed(now_ms)
                    if fired is not None and self.config.suppress == SuppressPolicy.WHEN_MATCHED:
                        flags |= winput.WP_DONT_PASS_INPUT_ON
                        trace.suppress("suppressed_when_matched", trigger=trig_name)
                        self._press_suppress_vk = vk_evt

            if trig in (Trigger.ON_HOLD, Trigger.ON_REPEAT) and prev_full and not full:
                self._hold_token += 1

            if not any_chord_key_pressed:
                self._had_full = False
                self._release_armed = False
                self._strict_order.reset()

            self._was_full = full
            return flags


__all__ = ["LogicalBind"]
