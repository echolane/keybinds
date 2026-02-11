from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional


class Window:
    """Small HWND wrapper used for focus/validity checks."""

    __slots__ = ("_hwnd",)

    _user32: Optional[ctypes.WinDLL] = None  # singleton storage

    @classmethod
    def _get_user32(cls) -> ctypes.WinDLL:
        """Lazy singleton loader for user32.dll."""
        if cls._user32 is None:
            u = ctypes.WinDLL("user32", use_last_error=True)

            # BOOL IsWindow(HWND hWnd);
            u.IsWindow.argtypes = (wintypes.HWND,)
            u.IsWindow.restype = wintypes.BOOL

            # HWND GetForegroundWindow(void);
            u.GetForegroundWindow.argtypes = ()
            u.GetForegroundWindow.restype = wintypes.HWND

            cls._user32 = u

        return cls._user32

    def __init__(self, hwnd: int) -> None:
        self._hwnd = int(hwnd)

    @property
    def hwnd(self) -> int:
        return self._hwnd

    def is_valid(self) -> bool:
        if self._hwnd <= 0:
            return False
        return bool(self._get_user32().IsWindow(wintypes.HWND(self._hwnd)))

    def is_focused(self) -> bool:
        """True if this window is the current foreground window."""
        if not self.is_valid():
            return False
        fg = self._get_user32().GetForegroundWindow()
        return int(fg) == self._hwnd

    def __repr__(self) -> str:
        return f"Window(hwnd=0x{self._hwnd:08X})"


def get_window(hwnd: Optional[int]) -> Optional[Window]:
    return Window(hwnd) if hwnd is not None else None
