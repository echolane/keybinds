# keybinds/_backend.py
from __future__ import annotations

import threading
import weakref
from traceback import print_exc
from typing import Optional, List

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


class _GlobalBackend:
    """
    One per-process backend:
      - installs winput hooks once
      - runs wait_messages() once
      - dispatches events to all active Hook instances
    """

    _instance: Optional["_GlobalBackend"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._hooks: List[weakref.ReferenceType] = []
        self._hooks_lock = threading.Lock()

        self._thread: Optional[threading.Thread] = None
        self._thread_started = False

        # physical only
        self._pressed_keys: set[int] = set()
        self._pressed_mouse: set[MouseButton] = set()

        # physical + injected
        self._pressed_keys_all: set[int] = set()
        self._pressed_mouse_all: set[MouseButton] = set()

        # injected only
        self._pressed_keys_injected: set[int] = set()
        self._pressed_mouse_injected: set[MouseButton] = set()

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
        with self._hooks_lock:
            self._hooks.append(weakref.ref(hook_obj))

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

    def _ensure_thread(self) -> None:
        with self._hooks_lock:
            if self._thread_started:
                return
            self._thread_started = True

        t = threading.Thread(target=self._thread_main, name="keybinds-backend", daemon=True)
        self._thread = t
        t.start()

    def _thread_main(self) -> None:
        # Install hooks and pump messages on the SAME thread.
        try:
            winput.hook_keyboard(self._on_keyboard)
            winput.hook_mouse(self._on_mouse)
            winput.wait_messages()
        except Exception:
            # If something goes wrong, try to unhook to restore input.
            try:
                winput.unhook_keyboard()
            except Exception:
                pass
            try:
                winput.unhook_mouse()
            except Exception:
                pass

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
        if is_down:
            base = self._pressed_keys_injected if injected else self._pressed_keys
            was_down = vk in base
        else:
            was_down = False

        if is_down:
            self._pressed_keys_all.add(vk)
        elif is_up:
            self._pressed_keys_all.discard(vk)

        if is_down:
            if injected:
                self._pressed_keys_injected.add(vk)
            else:
                self._pressed_keys.add(vk)

        elif is_up:
            self._pressed_keys.discard(vk)
            self._pressed_keys_injected.discard(vk)

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

        def _apply(target: set[MouseButton]) -> None:
            if act == WM_LBUTTONDOWN:
                target.add(MouseButton.LEFT)
            elif act == WM_LBUTTONUP:
                target.discard(MouseButton.LEFT)
            elif act == WM_RBUTTONDOWN:
                target.add(MouseButton.RIGHT)
            elif act == WM_RBUTTONUP:
                target.discard(MouseButton.RIGHT)
            elif act == WM_MBUTTONDOWN:
                target.add(MouseButton.MIDDLE)
            elif act == WM_MBUTTONUP:
                target.discard(MouseButton.MIDDLE)
            elif act == WM_XBUTTONDOWN:
                which = int(getattr(event, "additional_data", 0) or 0)
                if which == 1:
                    target.add(MouseButton.X1)
                elif which == 2:
                    target.add(MouseButton.X2)
            elif act == WM_XBUTTONUP:
                which = int(getattr(event, "additional_data", 0) or 0)
                if which == 1:
                    target.discard(MouseButton.X1)
                elif which == 2:
                    target.discard(MouseButton.X2)

        # Update ALL-state always
        _apply(self._pressed_mouse_all)

        # Update injected-only state only for injected events
        if injected:
            _apply(self._pressed_mouse_injected)
        else:
            # Update PHYSICAL-state only for non-injected events
            _apply(self._pressed_mouse)

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
                pass
        return flags
