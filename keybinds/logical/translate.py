from __future__ import annotations

import ctypes
from ctypes import wintypes
from functools import lru_cache
from typing import Iterable, Optional, Any

from .. import winput
from .._constants import (
    VK_SHIFT,
    VK_CONTROL,
    VK_MENU,
    VK_CAPITAL,
    VK_LSHIFT,
    VK_LCONTROL,
    VK_RCONTROL,
    VK_LMENU,
    VK_RMENU,
    VK_BACK,
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    MAPVK_VK_TO_VSC,
)

user32 = ctypes.WinDLL("user32", use_last_error=True)

_ToUnicodeEx = user32.ToUnicodeEx
_ToUnicodeEx.argtypes = (
    wintypes.UINT,
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_ubyte),
    wintypes.LPWSTR,
    ctypes.c_int,
    wintypes.UINT,
    wintypes.HKL,
)
_ToUnicodeEx.restype = ctypes.c_int

_GetKeyboardLayout = user32.GetKeyboardLayout
_GetKeyboardLayout.argtypes = (wintypes.DWORD,)
_GetKeyboardLayout.restype = wintypes.HKL

_MapVirtualKeyExW = user32.MapVirtualKeyExW
_MapVirtualKeyExW.argtypes = (wintypes.UINT, wintypes.UINT, wintypes.HKL)
_MapVirtualKeyExW.restype = wintypes.UINT

_GetForegroundWindow = user32.GetForegroundWindow
_GetForegroundWindow.argtypes = ()
_GetForegroundWindow.restype = wintypes.HWND

_GetWindowThreadProcessId = user32.GetWindowThreadProcessId
_GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_GetWindowThreadProcessId.restype = wintypes.DWORD

_GetKeyState = user32.GetKeyState
_GetKeyState.argtypes = (ctypes.c_int,)
_GetKeyState.restype = ctypes.c_short

_SendInput = user32.SendInput

LLKHF_EXTENDED = 0x01


def _hkl_to_int(hkl: Any) -> int:
    if hkl is None:
        return 0
    if isinstance(hkl, int):
        return int(hkl)
    value = getattr(hkl, "value", None)
    if value is not None:
        return int(value or 0)
    try:
        return int(hkl)
    except (TypeError, ValueError):
        return 0


class LogicalTranslator:
    __slots__ = ("_buf_len", "_buf", "_ks")

    _last_known_layout: int = 0

    def __init__(self, buf_len: int = 8):
        self._buf_len = buf_len
        self._buf = ctypes.create_unicode_buffer(buf_len)
        self._ks = (ctypes.c_ubyte * 256)()

    @staticmethod
    @lru_cache(maxsize=4096)
    def scancode_from_vk(vk: int, layout: int) -> int:
        return int(_MapVirtualKeyExW(vk, MAPVK_VK_TO_VSC, layout))

    @classmethod
    def current_layout(cls) -> int:
        hwnd = _GetForegroundWindow()
        if hwnd:
            pid = wintypes.DWORD(0)
            thread_id = int(_GetWindowThreadProcessId(hwnd, ctypes.byref(pid)))
            if thread_id:
                layout = _hkl_to_int(_GetKeyboardLayout(thread_id))
                if layout:
                    cls._last_known_layout = layout
                    return layout
        layout = _hkl_to_int(_GetKeyboardLayout(0))
        if layout:
            cls._last_known_layout = layout
            return layout
        if cls._last_known_layout:
            return cls._last_known_layout
        return 0

    @staticmethod
    def capslock_on() -> bool:
        return bool(_GetKeyState(VK_CAPITAL) & 1)

    def _fill_state(self, *, shift: bool, ctrl: bool, alt: bool, altgr: bool, caps: bool) -> None:
        ctypes.memset(ctypes.byref(self._ks), 0, 256)

        # For logical character matching, plain Ctrl/Alt should not destroy the
        # base printable character. AltGr must be preserved because layouts use it
        # to produce distinct symbols.
        effective_ctrl = False
        effective_alt = False

        if altgr:
            effective_ctrl = True
            effective_alt = True

        if shift:
            self._ks[VK_SHIFT] = 0x80
            self._ks[VK_LSHIFT] = 0x80
        if effective_ctrl:
            self._ks[VK_CONTROL] = 0x80
            self._ks[VK_LCONTROL] = 0x80
            self._ks[VK_RCONTROL] = 0x80
        if effective_alt:
            self._ks[VK_MENU] = 0x80
            self._ks[VK_LMENU] = 0x80
            self._ks[VK_RMENU] = 0x80
        if caps:
            self._ks[VK_CAPITAL] = 0x01

    def to_char(
        self,
        *,
        vk: int,
        scan_code: int,
        flags: int,
        shift: bool,
        ctrl: bool,
        alt: bool,
        altgr: bool,
        caps: bool,
        layout: int,
    ) -> Optional[str]:
        if not vk:
            return None

        if not scan_code:
            scan_code = self.scancode_from_vk(vk, layout)

        if flags & LLKHF_EXTENDED:
            scan_code |= 0xE000

        self._fill_state(shift=shift, ctrl=ctrl, alt=alt, altgr=altgr, caps=caps)
        self._buf.value = ""

        rc = int(_ToUnicodeEx(
            vk,
            scan_code,
            self._ks,
            self._buf,
            self._buf_len,
            0,
            layout,
        ))

        if rc > 0:
            return self._buf.value[:rc]
        return None


def send_backspaces(count: int) -> None:
    for _ in range(max(0, int(count))):
        winput.press_key(VK_BACK)
        winput.release_key(VK_BACK)


def _utf16_code_units(text: str) -> Iterable[int]:
    data = text.encode("utf-16-le")
    for i in range(0, len(data), 2):
        yield int.from_bytes(data[i:i + 2], "little")


def send_unicode_text(text: str) -> None:
    for code_unit in _utf16_code_units(text):
        down = winput.INPUT(
            type=winput.INPUT_KEYBOARD,
            ki=winput.KEYBDINPUT(wVk=0, wScan=code_unit, dwFlags=KEYEVENTF_UNICODE),
        )
        up = winput.INPUT(
            type=winput.INPUT_KEYBOARD,
            ki=winput.KEYBDINPUT(wVk=0, wScan=code_unit, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
        )
        _SendInput(1, ctypes.byref(down), ctypes.sizeof(down))
        _SendInput(1, ctypes.byref(up), ctypes.sizeof(up))


__all__ = ["LogicalTranslator", "send_backspaces", "send_unicode_text"]
