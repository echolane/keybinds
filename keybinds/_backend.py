# keybinds/_backend.py
from __future__ import annotations

import threading
import weakref
from traceback import print_exc
from typing import Optional, List, Set

from . import winput

from ._constants import (
    WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP,
    WM_LBUTTONDOWN, WM_LBUTTONUP,
    WM_RBUTTONDOWN, WM_RBUTTONUP,
    WM_MBUTTONDOWN, WM_MBUTTONUP,
    WM_XBUTTONDOWN, WM_XBUTTONUP,
)
from .types import MouseButton
from ._state import InputState

WM_KEYBINDS_REINSTALL = winput.WM_APP + 1


class _GlobalBackend:
    """
    One per-process backend:
      - installs winput hooks once
      - runs wait_messages() once
      - dispatches events to all active Hook instances
    """

    _instance: Optional[_GlobalBackend] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._hooks: List[weakref.ReferenceType] = []
        self._hooks_lock = threading.Lock()

        self._thread: Optional[threading.Thread] = None
        self._thread_started = False

        # physical only
        self._pressed_keys: Set[int] = set()
        self._pressed_mouse: Set[MouseButton] = set()

        # physical + injected
        self._pressed_keys_all: Set[int] = set()
        self._pressed_mouse_all: Set[MouseButton] = set()

        # injected only
        self._pressed_keys_injected: Set[int] = set()
        self._pressed_mouse_injected: Set[MouseButton] = set()

        self._thread_id: Optional[int] = None
        self._thread_ready = threading.Event()

    @classmethod
    def instance(cls) -> _GlobalBackend:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = _GlobalBackend()
            return cls._instance

    # -------------------------
    # lifecycle
    # -------------------------

    def register(self, hook_obj) -> None:
        """Register a Hook frontend and ensure backend thread is running."""
        stop_dispatcher = hook_obj._dispatcher.stop

        def _on_hook_gc(_wr):
            try:
                stop_dispatcher()
            except Exception:
                pass

        with self._hooks_lock:
            self._hooks.append(weakref.ref(hook_obj, _on_hook_gc))

        self._ensure_thread()

    def unregister(self, hook_obj) -> None:
        """Unregister a Hook frontend."""
        with self._hooks_lock:
            new_list = []
            for r in self._hooks:
                o = r()
                if o is None:
                    continue
                if o is hook_obj:
                    continue
                new_list.append(r)
            self._hooks = new_list

    def reinstall_hooks(self) -> None:
        if not self._thread_started:
            self._ensure_thread()

        if not self._thread_ready.wait(timeout=1.0):
            raise TimeoutError("keybinds backend thread did not become ready in time")

        thread_id = self._thread_id
        if thread_id is None:
            raise RuntimeError("keybinds backend thread is ready but has no thread id")

        winput.post_thread_message(thread_id, WM_KEYBINDS_REINSTALL, 0, 0)

    def _reset_all_hook_runtime_states(self) -> None:
        for hook in self._alive_hooks():
            try:
                hook._reset_runtime_states()
            except Exception:
                pass

    def _clear_pressed_state(self) -> None:
        self._pressed_keys.clear()
        self._pressed_mouse.clear()
        self._pressed_keys_all.clear()
        self._pressed_mouse_all.clear()
        self._pressed_keys_injected.clear()
        self._pressed_mouse_injected.clear()

    def _ensure_thread(self) -> None:
        with self._hooks_lock:
            if self._thread_started:
                return
            self._thread_started = True

        self._thread_ready.clear()
        t = threading.Thread(target=self._thread_main, name="keybinds-backend", daemon=True)
        self._thread = t
        t.start()

    def _on_backend_message(self, msg) -> bool:
        if int(msg.message) == WM_KEYBINDS_REINSTALL:
            try:
                winput.unhook_keyboard()
            except Exception:
                pass
            try:
                winput.unhook_mouse()
            except Exception:
                pass

            self._clear_pressed_state()
            self._reset_all_hook_runtime_states()

            winput.hook_keyboard(self._on_keyboard)
            winput.hook_mouse(self._on_mouse)
            return True

        return False

    def _thread_main(self) -> None:
        self._thread_id = winput.get_current_thread_id()

        # Force-create the thread message queue before anyone posts thread messages.
        winput.ensure_message_queue()
        self._thread_ready.set()

        try:
            winput.hook_keyboard(self._on_keyboard)
            winput.hook_mouse(self._on_mouse)
            winput.wait_messages(self._on_backend_message)
        except Exception:
            print_exc()
        finally:
            try:
                winput.unhook_keyboard()
            except Exception:
                pass
            try:
                winput.unhook_mouse()
            except Exception:
                pass

            self._clear_pressed_state()
            with self._hooks_lock:
                self._thread_started = False
                self._thread = None
                self._thread_id = None
                self._thread_ready.clear()

    # -------------------------
    # dispatch
    # -------------------------

    def _alive_hooks(self) -> list:
        """Return strong refs to currently alive Hook objects."""
        out = []
        with self._hooks_lock:
            new_refs = []
            for r in self._hooks:
                o = r()
                if o is None:
                    continue
                out.append(o)
                new_refs.append(r)
            self._hooks = new_refs
        return out

    def _on_keyboard(self, event: winput.KeyboardEvent) -> int:
        vk = int(event.vkCode)
        is_down = event.action in (WM_KEYDOWN, WM_SYSKEYDOWN)
        is_up = event.action in (WM_KEYUP, WM_SYSKEYUP)

        injected = bool(getattr(event, "injected", False))

        # Choose domain for repeat detection on KEYDOWN only
        base = self._pressed_keys_injected if injected else self._pressed_keys
        was_down = (vk in base) if is_down else False

        if is_down:
            self._pressed_keys_all.add(vk)
            base.add(vk)
        elif is_up:
            base.discard(vk)
            # Only clear from the union set when the key is no longer pressed in either domain.
            # (If it's pressed in both, a KEYUP from one side must not clear it.)
            if (vk in self._pressed_keys) or (vk in self._pressed_keys_injected):
                self._pressed_keys_all.add(vk)
            else:
                self._pressed_keys_all.discard(vk)

        # Mark OS auto-repeat (keydown while already pressed in that domain)
        try:
            setattr(event, "_sb_is_repeat", bool(is_down and was_down))
        except Exception:
            pass

        state = InputState(
            self._pressed_keys,
            self._pressed_mouse,
            self._pressed_keys_all,
            self._pressed_mouse_all,
            self._pressed_keys_injected,
            self._pressed_mouse_injected,
        )

        flags = winput.WP_CONTINUE
        for h in self._alive_hooks():
            try:
                flags |= h._handle_keyboard_event(event, state)
            except Exception:
                print_exc()
        return flags

    def _on_mouse(self, event: winput.MouseEvent) -> int:
        # Hard filter: only handle button up/down (everything else is noise).
        act = event.action
        if act not in (
            WM_LBUTTONDOWN, WM_LBUTTONUP,
            WM_RBUTTONDOWN, WM_RBUTTONUP,
            WM_MBUTTONDOWN, WM_MBUTTONUP,
            WM_XBUTTONDOWN, WM_XBUTTONUP,
        ):
            return winput.WP_CONTINUE

        injected = bool(getattr(event, "injected", False))

        def _button_from_event() -> Optional[MouseButton]:
            if act in (WM_LBUTTONDOWN, WM_LBUTTONUP):
                return MouseButton.LEFT
            if act in (WM_RBUTTONDOWN, WM_RBUTTONUP):
                return MouseButton.RIGHT
            if act in (WM_MBUTTONDOWN, WM_MBUTTONUP):
                return MouseButton.MIDDLE
            if act in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                which = int(getattr(event, "additional_data", 0) or 0)
                if which == 1:
                    return MouseButton.X1
                if which == 2:
                    return MouseButton.X2
            return None

        btn = _button_from_event()
        if btn is None:
            return winput.WP_CONTINUE

        is_down = act in (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN, WM_XBUTTONDOWN)
        is_up = act in (WM_LBUTTONUP, WM_RBUTTONUP, WM_MBUTTONUP, WM_XBUTTONUP)

        base = self._pressed_mouse_injected if injected else self._pressed_mouse

        if is_down:
            self._pressed_mouse_all.add(btn)
            base.add(btn)
        elif is_up:
            base.discard(btn)
            # Only clear from union when it's no longer pressed in either domain.
            if (btn in self._pressed_mouse) or (btn in self._pressed_mouse_injected):
                self._pressed_mouse_all.add(btn)
            else:
                self._pressed_mouse_all.discard(btn)

        state = InputState(
            self._pressed_keys,
            self._pressed_mouse,
            self._pressed_keys_all,
            self._pressed_mouse_all,
            self._pressed_keys_injected,
            self._pressed_mouse_injected,
        )

        flags = winput.WP_CONTINUE
        for h in self._alive_hooks():
            try:
                flags |= h._handle_mouse_event(event, state)
            except Exception:
                print_exc()
        return flags


def reinstall_hooks() -> None:
    """
    Reinstall global keyboard/mouse hooks so keybinds is placed later
    in the Windows low-level hook chain.
    """
    _GlobalBackend.instance().reinstall_hooks()


rehook = reinstall_hooks
