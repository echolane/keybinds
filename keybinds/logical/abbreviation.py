from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional, Deque, Set, Tuple

from .. import winput
from .._base_bind import BaseBind
from .._constants import (
    WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP,
    VK_SHIFT, VK_LSHIFT, VK_RSHIFT,
    VK_CONTROL, VK_LCONTROL, VK_RCONTROL,
    VK_MENU, VK_LMENU, VK_RMENU,
    VK_LWIN, VK_RWIN,
    VK_CAPITAL, VK_NUMLOCK, VK_SCROLL, VK_BACK,
)
from .translate import LogicalTranslator
from ..diagnostics import _DiagnosticsManager
from ..types import Callback, BindConfig, InjectedPolicy, LogicalConfig, TextBoundaryPolicy, TextBackspacePolicy, OsKeyRepeatPolicy
from .._state import InputState

_TOGGLE_KEYS = {VK_CAPITAL, VK_NUMLOCK, VK_SCROLL}

@dataclass(frozen=True)
class _TextMatchResult:
    delete_count: int
    trailing_text: str = ""
    matched_text: str = ""


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"



class TextAbbreviationBind(BaseBind[winput.KeyboardEvent]):
    """Match a suffix in the stream of produced printable characters.

    Unlike sequence binds, this ignores helper keystrokes such as Shift,
    CapsLock toggles, and layout switching combinations. Matching is based on
    the final character produced by the current layout.
    """

    def __init__(
        self,
        typed: str,
        callback: Callback,
        *,
        config: Optional[BindConfig] = None,
        hwnd: Optional[int] = None,
        dispatch: Optional[Callable[..., None]] = None,
        diagnostics: Optional[_DiagnosticsManager] = None,
        logical_config: Optional[LogicalConfig] = None,
    ) -> None:
        if not typed:
            raise ValueError("typed abbreviation text must not be empty")
        super().__init__(callback, config=config or BindConfig(), hwnd=hwnd, dispatch=dispatch, diagnostics=diagnostics)
        self.typed = typed
        self.logical_config = logical_config or LogicalConfig()
        self._set_diagnostics_identity(f"abbr:{typed}", "keyboard")
        self._translator = LogicalTranslator()
        self._caps_on = self._translator.capslock_on()
        self._buffer: Deque[str] = deque(maxlen=max(1, len(typed)))
        self._typed_norm = self._normalize_text(typed)
        self._last_event_ms = 0
        self.last_match: Optional[_TextMatchResult] = None
        self._pending_matches: Deque[_TextMatchResult] = deque(maxlen=16)
        self._pending_fire_vk: Optional[int] = None
        self._pending_fire_ms: int = 0
        self._resize_buffer()

    def reset(self) -> None:
        self._buffer.clear()
        self.last_match = None
        self._pending_matches.clear()
        self._pending_fire_vk = None
        self._pending_fire_ms = 0
        self._hold_token += 1
        self._last_event_ms = 0
        # Re-sync toggle state on resets caused by pause/resume.
        self._caps_on = self._translator.capslock_on()

    def _debounce_ok(self, now_ms: int) -> bool:
        db = self.config.timing.debounce_ms
        return db <= 0 or (now_ms - self._last_event_ms) >= db

    def _normalize_text(self, value: str) -> str:
        return value if self.logical_config.case_sensitive else value.casefold()

    def _effective_caps(self) -> bool:
        return self._caps_on if self.logical_config.respect_caps_lock else False

    def _resolved_backspace_policy(self) -> TextBackspacePolicy:
        legacy = self.logical_config.text_backspace_edits_buffer
        if legacy is True:
            return TextBackspacePolicy.EDIT_BUFFER
        if legacy is False:
            return TextBackspacePolicy.IGNORE
        return self.logical_config.text_backspace_policy

    def _resolved_repeat_policy(self) -> OsKeyRepeatPolicy:
        if self.logical_config.os_key_repeat_policy == OsKeyRepeatPolicy.IGNORE and self.config.constraints.allow_os_key_repeat:
            return OsKeyRepeatPolicy.MATCH
        return self.logical_config.os_key_repeat_policy

    def _backspace_clear_word(self) -> None:
        while self._buffer and _is_word_char(self._buffer[-1]):
            self._buffer.pop()

    def _resize_buffer(self) -> None:
        extra = 2 if self.logical_config.text_boundary_policy in (TextBoundaryPolicy.WORD_END, TextBoundaryPolicy.WHOLE_WORD) else 1
        limit = max(1, len(self.typed) + extra)
        if getattr(self._buffer, "maxlen", None) == limit:
            return
        self._buffer = deque(self._buffer, maxlen=limit)

    def _enqueue_match(self, match: _TextMatchResult) -> None:
        self._pending_matches.append(match)
        self.last_match = match

    def consume_match(self) -> Optional[_TextMatchResult]:
        if self._pending_matches:
            match = self._pending_matches.popleft()
            self.last_match = self._pending_matches[0] if self._pending_matches else None
            return match
        match = self.last_match
        self.last_match = None
        return match

    def _match_current_buffer(self) -> Optional[_TextMatchResult]:
        current = "".join(self._buffer)
        if not current:
            return None

        current_norm = self._normalize_text(current)
        target_norm = self._typed_norm
        policy = self.logical_config.text_boundary_policy
        target_len = len(self.typed)

        if policy == TextBoundaryPolicy.ANYWHERE:
            if current_norm.endswith(target_norm):
                return _TextMatchResult(delete_count=target_len, matched_text=current[-target_len:])
            return None

        if policy == TextBoundaryPolicy.WORD_START:
            if not current_norm.endswith(target_norm):
                return None
            start = len(current) - target_len
            if start <= 0 or not _is_word_char(current[start - 1]):
                return _TextMatchResult(delete_count=target_len, matched_text=current[-target_len:])
            return None

        if len(current) < target_len + 1:
            return None

        trailing = current[-1]
        if _is_word_char(trailing):
            return None

        core = current[:-1]
        core_norm = current_norm[:-1]
        if not core_norm.endswith(target_norm):
            return None

        start = len(core) - target_len
        if policy == TextBoundaryPolicy.WHOLE_WORD:
            if start > 0 and _is_word_char(core[start - 1]):
                return None

        return _TextMatchResult(delete_count=target_len + 1, trailing_text=trailing, matched_text=core[-target_len:])

    @staticmethod
    def _mods_from_pressed(pressed: Set[int]) -> Tuple[bool, bool, bool, bool, bool]:
        shift = any(vk in pressed for vk in (VK_SHIFT, VK_LSHIFT, VK_RSHIFT))
        ctrl = any(vk in pressed for vk in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL))
        ralt = VK_RMENU in pressed
        lalt = any(vk in pressed for vk in (VK_MENU, VK_LMENU))
        altgr = ralt and ctrl
        alt = lalt or (ralt and not altgr)
        win = any(vk in pressed for vk in (VK_LWIN, VK_RWIN))
        return shift, ctrl, alt, altgr, win

    def _get_pressed_for_policy(self, state: InputState, *, inj: bool) -> Set[int]:
        pol = self.config.injected
        if pol == InjectedPolicy.IGNORE:
            return set(state.pressed_keys)
        if pol == InjectedPolicy.ONLY:
            return set(state.pressed_keys_injected or ())
        if inj:
            inj_keys = set(state.pressed_keys_injected or ())
            phys_mods = {vk for vk in state.pressed_keys if vk in {VK_SHIFT, VK_LSHIFT, VK_RSHIFT, VK_CONTROL, VK_LCONTROL, VK_RCONTROL, VK_MENU, VK_LMENU, VK_RMENU, VK_LWIN, VK_RWIN}}
            return inj_keys | phys_mods
        return set(state.pressed_keys)

    def handle(self, event: winput.KeyboardEvent, state: InputState) -> int:
        with self._lock:
            trace = self._trace(event)
            now_ms = int(getattr(event, "time", 0) or 0)

            if not self._window_ok(trace=trace):
                return winput.WP_CONTINUE
            if self.config.checks.predicates and not self._checks_ok(event, state, trace=trace):
                return winput.WP_CONTINUE

            inj = bool(getattr(event, "injected", False))
            pol = self.config.injected
            if pol == InjectedPolicy.IGNORE and inj:
                trace.skip("injected_ignored")
                return winput.WP_CONTINUE
            if pol == InjectedPolicy.ONLY and not inj:
                trace.skip("injected_only_but_physical")
                return winput.WP_CONTINUE

            is_down = event.action in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up = event.action in (WM_KEYUP, WM_SYSKEYUP)
            vk_evt = int(event.vkCode)

            if is_up:
                if self._pending_fire_vk is not None and vk_evt == self._pending_fire_vk and self._pending_matches:
                    fire_ms = self._pending_fire_ms or now_ms
                    if not self.can_fire_now(fire_ms, trace=trace):
                        return winput.WP_CONTINUE
                    self._fires += 1
                    self._last_fire_ms = fire_ms
                    match = self._pending_matches[0]
                    dispatch_trace = trace.fire(
                        trigger="on_text_suffix",
                        text=self.typed,
                        boundary_policy=self.logical_config.text_boundary_policy.name,
                        delete_count=match.delete_count,
                        trailing_text=match.trailing_text,
                    )
                    self._fire(dispatch_trace)
                    self._pending_fire_vk = None
                    self._pending_fire_ms = 0
                return winput.WP_CONTINUE

            if not is_down:
                return winput.WP_CONTINUE

            if not self._debounce_ok(now_ms):
                trace.skip("debounce_filtered", debounce_ms=self.config.timing.debounce_ms)
                return winput.WP_CONTINUE
            self._last_event_ms = now_ms
            is_repeat = bool(getattr(event, "_sb_is_repeat", False))
            repeat_policy = self._resolved_repeat_policy()
            if is_repeat and repeat_policy == OsKeyRepeatPolicy.RESET:
                self._buffer.clear()
                trace.skip("repeat_reset_buffer")
                return winput.WP_CONTINUE
            fresh_down = (repeat_policy == OsKeyRepeatPolicy.MATCH) or not is_repeat
            if not fresh_down:
                trace.skip("repeat_ignored")
                return winput.WP_CONTINUE

            if vk_evt == VK_CAPITAL:
                self._caps_on = not self._caps_on
                if self.logical_config.ignore_toggle_keys:
                    return winput.WP_CONTINUE
            elif vk_evt in _TOGGLE_KEYS:
                if self.logical_config.ignore_toggle_keys:
                    return winput.WP_CONTINUE
                if self.logical_config.text_clear_buffer_on_non_text:
                    self._buffer.clear()
                return winput.WP_CONTINUE

            pressed_for_translation = self._get_pressed_for_policy(state, inj=inj)
            shift, ctrl, alt, altgr, win = self._mods_from_pressed(pressed_for_translation)

            # Editing should affect the rolling typed-text buffer.
            if vk_evt == VK_BACK and not ctrl and not alt and not win:
                backspace_policy = self._resolved_backspace_policy()
                if backspace_policy == TextBackspacePolicy.EDIT_BUFFER:
                    if self._buffer:
                        self._buffer.pop()
                        trace.note("state", "abbr_backspace_edit", size=len(self._buffer))
                elif backspace_policy == TextBackspacePolicy.CLEAR_BUFFER:
                    self._buffer.clear()
                    trace.note("state", "abbr_backspace_clear_buffer")
                elif backspace_policy == TextBackspacePolicy.CLEAR_WORD:
                    before = len(self._buffer)
                    self._backspace_clear_word()
                    trace.note("state", "abbr_backspace_clear_word", removed=max(0, before - len(self._buffer)))
                else:
                    trace.note("state", "abbr_backspace_ignored")
                return winput.WP_CONTINUE

            # Ignore shortcut and layout-switch helper combinations. We only care
            # about text-producing keydowns.
            ignore_combo = (win and self.logical_config.text_ignore_win_combos) or (ctrl and self.logical_config.text_ignore_ctrl_combos) or (alt and self.logical_config.text_ignore_alt_combos)
            if ignore_combo:
                trace.skip("abbr_modifier_combo_ignored", ctrl=ctrl, alt=alt, win=win, altgr=altgr)
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
                    self._buffer.clear()
                    trace.note("state", "abbr_buffer_cleared_non_text")
                trace.skip("abbr_no_char")
                return winput.WP_CONTINUE

            self._buffer.append(ch)
            current = "".join(self._buffer)
            current_norm = self._normalize_text(current)
            trace.note("decision", "abbr_buffer", current=current, target=self.typed, normalized=current_norm, boundary_policy=self.logical_config.text_boundary_policy.name, backspace_policy=self._resolved_backspace_policy().name, repeat_policy=self._resolved_repeat_policy().name)
            match = self._match_current_buffer()
            if not match:
                return winput.WP_CONTINUE

            self._enqueue_match(match)
            self._pending_fire_vk = vk_evt
            self._pending_fire_ms = now_ms
            trace.note("decision", "abbr_match_pending_keyup", vk=vk_evt, delete_count=match.delete_count)
            self._buffer.clear()
            return winput.WP_CONTINUE


__all__ = ["TextAbbreviationBind"]
