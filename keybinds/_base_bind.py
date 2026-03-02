import threading
import time

from typing import Union, Optional, Callable

from . import winput

from ._state import InputState
from ._window import get_window
from .types import Callback, FocusPolicy, BindConfig, MouseBindConfig


class BaseBind:
    def __init__(
        self,
        callback: Callback,
        *,
        config: Optional[Union[BindConfig, MouseBindConfig]] = None,
        hwnd: Optional[int] = None,
        dispatch: Optional[Callable[[Callback], None]] = None,
    ) -> None:
        self.callback = callback
        self.config = config or BindConfig()
        self.window = get_window(hwnd)
        self._dispatch = dispatch or (lambda fn: fn())

        self._hold_token: int = 0

        self._focus_cache: bool = True
        self._focus_last_check_ms: int = 0
        self._focus_last_value: Optional[bool] = None  

        self._last_fire_ms: int = 0
        self._fires: int = 0

        self._lock = threading.RLock()

    def _on_blur(self) -> None:
        pol = self.config.focus
        if pol == FocusPolicy.CANCEL_ON_BLUR:
            self.reset()
        elif pol == FocusPolicy.PAUSE_ON_BLUR:
            self._hold_token += 1

    def _on_focus(self) -> None:
        pass

    def reset(self) -> None:
        pass

    def _window_ok(self, *, force: bool = False) -> bool:
        if self.window is None:
            return True

        now_ms = int(time.monotonic() * 1000)
        cache_ms = self.config.timing.window_focus_cache_ms

        if (not force) and (now_ms - self._focus_last_check_ms) < cache_ms:
            return self._focus_cache

        self._focus_last_check_ms = now_ms
        try:
            focused = bool(self.window.is_focused())
        except Exception:
            focused = False

        if self._focus_last_value is None:
            self._focus_last_value = focused
        elif focused != self._focus_last_value:
            self._focus_last_value = focused
            if focused:
                self._on_focus()
            else:
                self._on_blur()

        self._focus_cache = focused
        return focused

    def _checks_ok(self, event: Union[winput.KeyboardEvent, winput.MouseEvent], state: InputState) -> bool:
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

    def _max_fires_ok(self) -> bool:
        mx = self.config.constraints.max_fires
        return mx is None or self._fires < mx

    def _fire(self) -> None:
        self._dispatch(self.callback)
