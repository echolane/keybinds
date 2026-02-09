from __future__ import annotations

import signal
import threading
from contextlib import contextmanager
from typing import Callable, Optional, Union, Generator

from ._backend import _GlobalBackend
from ._dispatcher import _CallbackDispatcher
from ._keyboard import Bind
from ._mouse import MouseBind
from .types import BindConfig, MouseBindConfig, MouseButton

_default_hook: Optional[Hook] = None


def get_default_hook() -> Hook:
    global _default_hook
    if _default_hook is None:
        _default_hook = Hook()
    return _default_hook


def set_default_hook(hook: Hook) -> None:
    global _default_hook
    _default_hook = hook


def join(hook: Optional[Hook] = None) -> None:
    """Block until the hook is stopped.

    If hook is None, the default hook will be used.
    """

    if hook is None:
        hook = get_default_hook()

    def handler(sig, frame):
        hook.stop()

    signal.signal(signal.SIGINT, handler)

    try:
        hook.wait()
    finally:
        hook.close()


class Hook:
    def __init__(
        self,
        *,
        callback_workers: int = 1,
        default_config: Optional[BindConfig] = None,
        default_mouse_config: Optional[MouseBindConfig] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self._pause_count = 0
        self._paused = False

        self.default_config = default_config
        self.default_mouse_config = default_mouse_config

        self._dispatcher = _CallbackDispatcher(workers=callback_workers)

        # binds live in this frontend
        self._keyboard_binds: list[Bind] = []
        self._mouse_binds: list[MouseBind] = []

        # snapshots used by backend hot path (tuples are cheap to iterate)
        self._keyboard_snapshot: tuple[Bind, ...] = ()
        self._mouse_snapshot: tuple[MouseBind, ...] = ()

        # Attach to global backend (installs hooks once)
        _GlobalBackend.instance().register(self)

    # -------------------------
    # public API
    # -------------------------

    def bind(self, expr: str, callback: Callable[[], None], *, config: Optional[BindConfig] = None, hwnd=None) -> Bind:
        cfg = config or self.default_config or BindConfig()
        b = Bind(expr, callback, config=cfg, hwnd=hwnd, dispatch=self._dispatcher.submit)
        with self._lock:
            self._keyboard_binds.append(b)
            self._keyboard_snapshot = tuple(self._keyboard_binds)
        return b

    def bind_mouse(self, button: Union[MouseButton, str], callback: Callable[[], None], *, config: Optional[MouseBindConfig] = None, hwnd=None) -> MouseBind:
        cfg = config or self.default_mouse_config or MouseBindConfig()
        b = MouseBind(button, callback, config=cfg, hwnd=hwnd, dispatch=self._dispatcher.submit)
        with self._lock:
            self._mouse_binds.append(b)
            self._mouse_snapshot = tuple(self._mouse_binds)
        return b

    def unbind(self, b: Bind) -> None:
        with self._lock:
            try:
                self._keyboard_binds.remove(b)
            except ValueError:
                return
            self._keyboard_snapshot = tuple(self._keyboard_binds)

    def unbind_mouse(self, b: MouseBind) -> None:
        with self._lock:
            try:
                self._mouse_binds.remove(b)
            except ValueError:
                return
            self._mouse_snapshot = tuple(self._mouse_binds)

    def pause(self) -> None:
        """Pause the hook (no callbacks will be called until resume() is called).

        Useful for temporarily disabling the hook while it's running.
        """
        with self._lock:
            self._pause_count += 1
            self._paused = True

    def resume(self) -> None:
        """Resume the hook (callbacks will be called again after calling pause()).

        Useful for re-enabling the hook after temporarily disabling it with pause().
        """
        with self._lock:
            if self._pause_count == 0:
                return
            self._pause_count -= 1
            if self._pause_count == 0:
                self._paused = False

    def is_paused(self) -> bool:
        """Get whether the hook is currently paused.

        Returns True if the hook is paused, False otherwise.
        """
        return self._paused

    @contextmanager
    def paused(self) -> Generator[None, None, None]:
        """Pause and resume the hook using the with statement.

        Example:
            >>> with hook.paused():
                # do something that requires the hook to be paused
        """
        self.pause()
        try:
            yield
        finally:
            self.resume()

    def stop(self) -> None:
        """Signal to stop waiting in wait().

        After calling stop(), wait() will return True as soon as possible.
        """
        self._stop_event.set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for stop() to be called.

        If timeout is not None, wait for stop() to be called.
        Returns True if stop() was called, False otherwise.
        """
        if timeout is not None:
            return self._stop_event.wait(timeout)

        try:
            while not self._stop_event.wait(0.2):
                pass
            return True
        except KeyboardInterrupt:
            return True

    def join(self) -> None:
        """Block until the hook is stopped."""
        join(self)

    def close(self) -> None:
        # just detach this frontend; backend keeps running if others exist
        _GlobalBackend.instance().unregister(self)
        self._dispatcher.stop()

    # -------------------------
    # called by backend
    # -------------------------

    def _handle_keyboard_event(self, event, state) -> int:
        if self._paused:
            return 0

        snap = self._keyboard_snapshot
        if not snap:
            return 0  # winput.WP_CONTINUE (backend ORs anyway)
        flags = 0
        for b in snap:
            flags |= b.handle(event, state)
        return flags

    def _handle_mouse_event(self, event, state) -> int:
        if self._paused:
            return 0

        snap = self._mouse_snapshot
        if not snap:
            return 0
        flags = 0
        for b in snap:
            flags |= b.handle(event, state)
        return flags
