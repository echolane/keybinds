"""
winput

Capture and send keyboard and mouse input on Windows

---------------------
LICENSE (zlib/libpng)
---------------------
zlib/libpng license

Copyright (c) 2017 Zuzu_Typ

This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
"""

import ctypes
from sys import getwindowsversion
from ctypes import wintypes

from typing import Callable, Optional, Tuple

try:
    from .vk_codes import *
    from . import vk_codes
except ImportError:
    from vk_codes import *
    import vk_codes

class MouseEvent:
    type = "MouseEvent"
    def __init__(
        self,
        position : Tuple[int, int],
        action : int,
        time : int,
        additional_data = None,
        *,
        flags: int = 0,
        injected: bool = False,
        lower_il_injected: bool = False,
        extra_info: int = 0,
    ):
        self.position = self.pos = position
        self.x, self.y = self.pos
        self.action = action
        self.time = time
        self.additional_data = additional_data

        # Low-level hook metadata
        self.flags = flags
        self.injected = injected
        self.lower_il_injected = lower_il_injected
        self.extra_info = extra_info

class KeyboardEvent:
    type = "KeyboardEvent"
    def __init__(
        self,
        action : int,
        vkCode : int,
        time : int,
        *,
        scanCode: int = 0,
        flags: int = 0,
        injected: bool = False,
        lower_il_injected: bool = False,
        extra_info: int = 0,
    ):
        self.action = action
        self.key = self.vk_code = self.vkCode = vkCode
        self.time = time

        # Low-level hook metadata
        self.scanCode = scanCode
        self.flags = flags
        self.injected = injected
        self.lower_il_injected = lower_il_injected
        self.extra_info = extra_info

WP_CONTINUE             = 0x00
WP_UNHOOK               = 0x01
WP_STOP                 = 0x02
WP_DONT_PASS_INPUT_ON   = 0x04

user32 = ctypes.windll.user32

# Pointer-sized Win32 types.
# NOTE: ctypes.c_long is 32-bit on Windows even on x64, so avoid it for LONG_PTR/ULONG_PTR.
LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t

# Matching pointer-sized WPARAM/LPARAM for callbacks (esp. important on x64).
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t

INPUT_MOUSE    = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_UNICODE     = 0x0004
KEYEVENTF_SCANCODE    = 0x0008

MAPVK_VK_TO_VSC = 0

WH_MOUSE_LL = (14)

WH_KEYBOARD_LL = (13)

WM_MOUSEMOVE                    =0x0200

WM_LBUTTONDOWN                  =0x0201
WM_LBUTTONUP                    =0x0202

WM_RBUTTONDOWN                  =0x0204
WM_RBUTTONUP                    =0x0205

WM_MBUTTONDOWN                  =0x0207
WM_MBUTTONUP                    =0x0208

WM_MOUSEWHEEL                   =0x020A
WM_MOUSEHWHEEL                  =0x020E

WM_XBUTTONDOWN                  =0x020B
WM_XBUTTONUP                    =0x020C

XBUTTON1      =0x0001
XBUTTON2      =0x0002

MB_LEFT = 0x0001
MB_RIGHT = 0x0002
MB_MIDDLE = 0x0004
MB_X1 = 0x0008
MB_X2 = 0x0016

WM_KEYDOWN                      =0x0100
WM_KEYUP                        =0x0101

WM_SYSKEYDOWN                   =0x0104
WM_SYSKEYUP                     =0x0105

WHEEL_DELTA                  =120
GET_HWORD          =lambda x: ctypes.c_short((x >> 16)).value

vk_code_dict = {}

for item in dir(vk_codes):
    if item.startswith("__"):
        continue
    vk_code_dict[getattr(vk_codes, item)] = item

all_vk_codes = vk_code_dict

QS_KEY            =0x0001
QS_MOUSEMOVE      =0x0002
QS_MOUSEBUTTON    =0x0004
QS_RAWINPUT       =0x0400
QS_TOUCH          =0x0800
QS_POINTER        =0x1000

QS_MOUSE = QS_MOUSEMOVE | QS_MOUSEBUTTON

_WINVER = getwindowsversion()
_WIN32_WINNT = (_WINVER.major << 8) | _WINVER.minor

if (_WIN32_WINNT >= 0x602):
    QS_INPUT = QS_MOUSE | QS_KEY | QS_RAWINPUT | QS_TOUCH | QS_POINTER
elif (_WIN32_WINNT >= 0x0501):
    QS_INPUT = QS_MOUSE | QS_KEY | QS_RAWINPUT
else:
    QS_INPUT = QS_MOUSE | QS_KEY

PM_NOREMOVE = 0x0000
PM_REMOVE = 0x0001
PM_QS_INPUT = (QS_INPUT << 16)

PROCESS_DPI_UNAWARE           = 0
PROCESS_SYSTEM_DPI_AWARE      = 1
PROCESS_PER_MONITOR_DPI_AWARE = 2

MDT_EFFECTIVE_DPI   = 0
MDT_ANGULAR_DPI     = 1
MDT_RAW_DPI         = 2

LOGPIXELSX = 88
LOGPIXELSY = 90

MONITOR_DEFAULTTONULL       = 0x00000000
MONITOR_DEFAULTTOPRIMARY    = 0x00000001
MONITOR_DEFAULTTONEAREST    = 0x00000002

class MOUSEINPUT(ctypes.Structure):
    _fields_ = (("dx",          wintypes.LONG),
                ("dy",          wintypes.LONG),
                ("mouseData",   wintypes.DWORD),
                ("dwFlags",     wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR))

class KEYBDINPUT(ctypes.Structure):
    _fields_ = (("wVk",         wintypes.WORD),
                ("wScan",       wintypes.WORD),
                ("dwFlags",     wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR))

    def __init__(self, *args, **kwds):
        super(KEYBDINPUT, self).__init__(*args, **kwds)
        # some programs use the scan code even if KEYEVENTF_SCANCODE
        # isn't set in dwFflags, so attempt to map the correct code.
        if not self.dwFlags & KEYEVENTF_UNICODE:
            self.wScan = user32.MapVirtualKeyExW(self.wVk,
                                                 MAPVK_VK_TO_VSC, 0)

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (("uMsg",    wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD))

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = (("ki", KEYBDINPUT),
                    ("mi", MOUSEINPUT),
                    ("hi", HARDWAREINPUT))
    _anonymous_ = ("_input",)
    _fields_ = (("type",   wintypes.DWORD),
                ("_input", _INPUT))

LPINPUT = ctypes.POINTER(INPUT)

def _check_count(result, func, args):
    if result == 0:
        raise ctypes.WinError(ctypes.get_last_error())
    return args

user32.SendInput.errcheck = _check_count
user32.SendInput.argtypes = (wintypes.UINT, # nInputs
                             LPINPUT,       # pInputs
                             ctypes.c_int)  # cbSize

# ---- WinAPI prototypes (critical for x64 correctness) ----
HHOOK = ctypes.c_void_p
HINSTANCE = ctypes.c_void_p

# HOOKPROC signature for WH_KEYBOARD_LL / WH_MOUSE_LL
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)

# SetWindowsHookEx
user32.SetWindowsHookExW.restype = HHOOK
user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, HINSTANCE, wintypes.DWORD)

# CallNextHookEx
user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = (HHOOK, ctypes.c_int, WPARAM, LPARAM)

# UnhookWindowsHookEx
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.UnhookWindowsHookEx.argtypes = (HHOOK,)

# GetMessage / PostQuitMessage
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)

user32.PostQuitMessage.restype = None
user32.PostQuitMessage.argtypes = (ctypes.c_int,)


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long),
                ("y", ctypes.c_long)]

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


# Low-level hook flags that indicate synthesized ("injected") input.
# Mouse: MSLLHOOKSTRUCT.flags
LLMHF_INJECTED = 0x00000001
LLMHF_LOWER_IL_INJECTED = 0x00000002

# Keyboard: KBDLLHOOKSTRUCT.flags
LLKHF_LOWER_IL_INJECTED = 0x00000002
LLKHF_INJECTED = 0x00000010


def _ptr_value(v) -> int:
    """Best-effort conversion of an ULONG_PTR-like field to int."""
    try:
        return int(v)
    except Exception:
        try:
            return ctypes.cast(v, ctypes.c_void_p).value or 0
        except Exception:
            return 0

def _LowLevelMouseProc(nCode : int, wParam : int, lParam : int, cbfunc : Callable[[MouseEvent], Optional[int]]):
    if nCode < 0: # error passthrough
        return user32.CallNextHookEx(0, nCode, wParam, lParam)

    lParam_addr = lParam
    # lParam is an address (LPARAM) to an MSLLHOOKSTRUCT.
    ms = ctypes.cast(lParam_addr, ctypes.POINTER(MSLLHOOKSTRUCT)).contents

    extra_data = None

    if wParam in (WM_XBUTTONDOWN, WM_XBUTTONUP): # X button changed state
        extra_data = GET_HWORD(ms.mouseData)
        
    elif wParam == WM_MOUSEWHEEL or wParam == WM_MOUSEHWHEEL: # used scrollwheel
        extra_data = GET_HWORD(ms.mouseData) // WHEEL_DELTA

    result = cbfunc(MouseEvent(
        (ms.pt.x, ms.pt.y),
        wParam,
        ms.time,
        extra_data,
        flags=ms.flags,
        injected=bool(ms.flags & LLMHF_INJECTED),
        lower_il_injected=bool(ms.flags & LLMHF_LOWER_IL_INJECTED),
        extra_info=_ptr_value(ms.dwExtraInfo),
    ))

    if result is None:
        result = WP_CONTINUE

    assert type(result) == int

    if result & WP_UNHOOK:
        global mouse_hook
        user32.UnhookWindowsHookEx(mouse_hook)

    if result & WP_STOP:
        user32.PostQuitMessage(0)

    if result & WP_DONT_PASS_INPUT_ON:
        return -1

    return user32.CallNextHookEx(mouse_hook, nCode, wParam, lParam_addr)

def _LowLevelKeyboardProc(nCode : int, wParam : int, lParam : int, cbfunc : Callable[[KeyboardEvent], Optional[int]]):
    if nCode < 0: # error passthrough
        return user32.CallNextHookEx(0, nCode, wParam, lParam)

    lParam_addr = lParam
    # lParam is an address (LPARAM) to a KBDLLHOOKSTRUCT.
    kb = ctypes.cast(lParam_addr, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents

    result = cbfunc(KeyboardEvent(
        wParam,
        kb.vkCode,
        kb.time,
        scanCode=kb.scanCode,
        flags=kb.flags,
        injected=bool(kb.flags & LLKHF_INJECTED),
        lower_il_injected=bool(kb.flags & LLKHF_LOWER_IL_INJECTED),
        extra_info=_ptr_value(kb.dwExtraInfo),
    ))

    if result is None:
        result = WP_CONTINUE

    assert type(result) == int

    if result & WP_UNHOOK:
        global keyboard_hook
        user32.UnhookWindowsHookEx(keyboard_hook)

    if result & WP_STOP:
        user32.PostQuitMessage(0)

    if result & WP_DONT_PASS_INPUT_ON:
        return -1

    return user32.CallNextHookEx(keyboard_hook, nCode, wParam, lParam_addr)

mouse_hook_func = None
keyboard_hook_func = None

mouse_hook = None
keyboard_hook = None


LLMouseProc = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)
LLKeyboardProc = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)

def _issue_mouse_event(dwFlags = 0x0001, dx = 0, dy = 0, mouseData = 0x000):
    me = INPUT(type=INPUT_MOUSE,
               mi=MOUSEINPUT(dx = dx, dy = dy, dwFlags = dwFlags, mouseData = mouseData))
    user32.SendInput(1, ctypes.byref(me), ctypes.sizeof(me))

LEFT_MOUSE_BUTTON   = LMB   = 1
MIDDLE_MOUSE_BUTTON = MMB   = 2
RIGHT_MOUSE_BUTTON  = RMB   = 4
EXTRA_MOUSE_BUTTON1 = XMB1  = 8
EXTRA_MOUSE_BUTTON2 = XMB2  = 16



def set_mouse_pos(x : int, y : int) -> bool:
    """set_mouse_pos(x, y) -> success
Moves the cursor to the given coordinates."""
    return bool(user32.SetCursorPos(x, y))

def get_mouse_pos() -> Tuple[int, int]:
    """get_mouse_pos() -> (x, y)
Gets the current cursor position"""
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)

def press_mouse_button(mouse_button : int = LMB) -> None: # presses the given mouse button
    if(not (LMB <= mouse_button <= XMB2)):
        raise AssertionError("invalid mouse button")
    
    dwFlags = 0x0002 if mouse_button == LMB else \
              0x0008 if mouse_button == RMB else \
              0x0020 if mouse_button == MMB else \
              0x0080

    if dwFlags == 0x0080:
        mouseData = 0x1 if mouse_button == XMB1 else 0x2
    else:
        mouseData = 0
        
    _issue_mouse_event(dwFlags, 0, 0, mouseData)

def release_mouse_button(mouse_button : int = LMB) -> None:# releases the given mouse button
    if(not (LMB <= mouse_button <= XMB2)):
        raise AssertionError("invalid mouse button")
    
    dwFlags = 0x0004 if mouse_button == LMB else \
              0x0010 if mouse_button == RMB else \
              0x0040 if mouse_button == MMB else \
              0x0100

    if dwFlags == 0x0100:
        mouseData = 0x1 if mouse_button == XMB1 else 0x2
    else:
        mouseData = 0
        
    _issue_mouse_event(dwFlags, 0, 0, mouseData)

def click_mouse_button(mouse_button : int = LMB) -> None: # presses and releases the given mouse button
    press_mouse_button(mouse_button)
    release_mouse_button(mouse_button)

def move_mousewheel(amount : int, horizontal : bool = False) -> None: # moves the mousewheel by the specified amount
    assert type(amount) == int, "amount has to be an integer"
    
    _issue_mouse_event(0x0800 if not horizontal else 0x1000, 0, 0, amount * WHEEL_DELTA)

def move_mouse(dx : int, dy : int) -> None: # moves the mouse by the specified amount in pixels
    assert type(dx) == type(dy) == int, "dx and dy have to be integers"
    
    _issue_mouse_event(0x0001, dx, dy, 0)

def press_key(vk_code : int) -> None: # presses the given key
    x = INPUT(type=INPUT_KEYBOARD,
              ki=KEYBDINPUT(wVk=vk_code))
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

def release_key(vk_code : int) -> None: # releases the given key
    x = INPUT(type=INPUT_KEYBOARD,
              ki=KEYBDINPUT(wVk=vk_code,
                            dwFlags=KEYEVENTF_KEYUP))
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

def click_key(vk_code : int) -> None: # presses and releases the given key
    press_key(vk_code)
    release_key(vk_code)

def hook_mouse(func : Callable[[MouseEvent], Optional[int]]) -> None: # hook onto mouse event queue
    global mouse_hook_func, mouse_hook
    mouse_hook_func = LLMouseProc(lambda x, y, z: _LowLevelMouseProc(x, y, z, func))
    mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, mouse_hook_func, None, 0)

def hook_keyboard(func : Callable[[KeyboardEvent], Optional[int]]) -> None: # hook onto keyboard event queue
    global keyboard_hook_func, keyboard_hook
    keyboard_hook_func = LLKeyboardProc(lambda x, y, z: _LowLevelKeyboardProc(x, y, z, func))
    keyboard_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, keyboard_hook_func, None, 0)
    
def wait_messages() -> None: # enter message loop
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.pointer(msg), None, 0, 0):
        pass

def get_message() -> bool: # get pending messages
    msg = wintypes.MSG()
    return bool(user32.PeekMessageA(ctypes.pointer(msg), None, 0, 0, PM_REMOVE))

def stop() -> None: # stop message loop
    user32.PostQuitMessage(0)

def unhook_mouse() -> None: # remove hook from mouse event queue
    global mouse_hook
    user32.UnhookWindowsHookEx(mouse_hook)

def unhook_keyboard() -> None: # remove hook from keyboard event queue
    global keyboard_hook
    user32.UnhookWindowsHookEx(keyboard_hook)

def set_DPI_aware(per_monitor : bool = True) -> None: # make this process DPI aware
    shcore = ctypes.windll.shcore
    
    if hasattr(shcore, "SetProcessDpiAwareness"):
        shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE if per_monitor else PROCESS_SYSTEM_DPI_AWARE)
    elif hasattr(shcore, "SetProcessDPIAware"):
        shcore.SetProcessDPIAware()

def get_window_scaling_factor(hwnd : int) -> float: # gets the DPI scaling factor for the given window (may require DPI awareness)
    if hasattr(user32, "GetDpiForWindow"):
        return user32.GetDpiForWindow(hwnd) / 96.0
    if hasattr(ctypes.windll.shcore, "GetDpiForMonitor"):
        hmonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        dpiX = ctypes.c_uint()
        dpiY = ctypes.c_uint()
        hres = ctypes.windll.shcore.GetDpiForMonitor(hmonitor, MDT_EFFECTIVE_DPI, ctypes.byref(dpiX), ctypes.byref(dpiY))

        assert hres == 0

        return dpiX.value / 96.0
    if hasattr(ctypes.windll.gdi32, "GetDeviceCaps"):
        hdc = user32.GetDC(hwnd)
        try:
            return ctypes.windll.gdi32.GetDeviceCaps(hdc, LOGPIXELSX) / 96.0
        finally:
            user32.ReleaseDC(hwnd, hdc)

    return 1.0
        
        
