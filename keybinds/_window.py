from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional, Tuple, Union


class Window:
    """Small HWND wrapper used for focus/validity checks.

    A string target is matched against a top-level window's exact title
    (case-insensitive). It is resolved on every check, so a replacement window
    with the same title is picked up automatically.
    """

    _user32 = None

    @classmethod
    def _get_user32(cls):
        if cls._user32 is None:
            u = ctypes.WinDLL("user32", use_last_error=True)
            u.IsWindow.argtypes = (wintypes.HWND,)
            u.IsWindow.restype = wintypes.BOOL
            u.GetForegroundWindow.argtypes = ()
            u.GetForegroundWindow.restype = wintypes.HWND
            u.EnumWindows.argtypes = (ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM)
            u.EnumWindows.restype = wintypes.BOOL
            u.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
            u.GetWindowTextLengthW.restype = ctypes.c_int
            u.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
            u.GetWindowTextW.restype = ctypes.c_int
            cls._user32 = u
        return cls._user32

    def __init__(self, hwnd: Union[int, str]) -> None:
        self._title = hwnd.strip() if isinstance(hwnd, str) else None
        self._hwnd = 0 if isinstance(hwnd, str) else int(hwnd)
        self._resolved_title_hwnd = 0

    def _resolve_title(self) -> int:
        if not self._title:
            return 0
        u = self._get_user32()
        cached = self._resolved_title_hwnd
        if cached > 0:
            length = u.GetWindowTextLengthW(wintypes.HWND(cached))
            if length > 0:
                title = ctypes.create_unicode_buffer(length + 1)
                u.GetWindowTextW(wintypes.HWND(cached), title, length + 1)
                if title.value.casefold() == self._title.casefold():
                    return cached
        found = [0]
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def visit(hwnd, _):
            length = u.GetWindowTextLengthW(hwnd)
            if length > 0:
                title = ctypes.create_unicode_buffer(length + 1)
                u.GetWindowTextW(hwnd, title, length + 1)
                if title.value.casefold() == self._title.casefold():
                    found[0] = int(hwnd)
                    return False
            return True

        u.EnumWindows(callback_type(visit), 0)
        self._resolved_title_hwnd = found[0]
        return found[0]

    @property
    def hwnd(self) -> int:
        return self._resolve_title() if self._title is not None else self._hwnd

    @property
    def title(self) -> Optional[str]:
        return self._title

    def is_valid(self) -> bool:
        hwnd = self.hwnd
        return hwnd > 0 and bool(self._get_user32().IsWindow(wintypes.HWND(hwnd)))

    def focus_status(self) -> Tuple[bool, bool]:
        """Return (valid, focused), resolving and validating the HWND once."""
        hwnd = self.hwnd
        if hwnd <= 0:
            return False, False
        u = self._get_user32()
        if not u.IsWindow(wintypes.HWND(hwnd)):
            return False, False
        return True, int(u.GetForegroundWindow()) == hwnd

    def is_focused(self) -> bool:
        return self.focus_status()[1]

    def __repr__(self) -> str:
        if self._title is not None:
            return f"Window(title={self._title!r})"
        return f"Window(hwnd=0x{self._hwnd:08X})"


def get_window(hwnd: Optional[Union[int, str]]) -> Optional[Window]:
    return Window(hwnd) if hwnd is not None else None
