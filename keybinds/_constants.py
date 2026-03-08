from __future__ import annotations

from typing import Dict, Set

from . import winput

# Common VK codes (fallbacks); winput also exposes VK_* constants.
VK_SHIFT = getattr(winput, "VK_SHIFT", 0x10)
VK_CONTROL = getattr(winput, "VK_CONTROL", 0x11)
VK_MENU = getattr(winput, "VK_MENU", 0x12)  # ALT
VK_LSHIFT = getattr(winput, "VK_LSHIFT", 0xA0)
VK_RSHIFT = getattr(winput, "VK_RSHIFT", 0xA1)
VK_LCONTROL = getattr(winput, "VK_LCONTROL", 0xA2)
VK_RCONTROL = getattr(winput, "VK_RCONTROL", 0xA3)
VK_LMENU = getattr(winput, "VK_LMENU", 0xA4)
VK_RMENU = getattr(winput, "VK_RMENU", 0xA5)
VK_LWIN = getattr(winput, "VK_LWIN", 0x5B)
VK_RWIN = getattr(winput, "VK_RWIN", 0x5C)

# Mouse wParams
WM_LBUTTONDOWN = winput.WM_LBUTTONDOWN
WM_LBUTTONUP = winput.WM_LBUTTONUP
WM_RBUTTONDOWN = winput.WM_RBUTTONDOWN
WM_RBUTTONUP = winput.WM_RBUTTONUP
WM_MBUTTONDOWN = winput.WM_MBUTTONDOWN
WM_MBUTTONUP = winput.WM_MBUTTONUP
WM_XBUTTONDOWN = winput.WM_XBUTTONDOWN
WM_XBUTTONUP = winput.WM_XBUTTONUP

WM_KEYDOWN = winput.WM_KEYDOWN
WM_KEYUP = winput.WM_KEYUP
WM_SYSKEYDOWN = winput.WM_SYSKEYDOWN
WM_SYSKEYUP = winput.WM_SYSKEYUP

# mouse move/wheel constants may exist; values are stable win32.
WM_MOUSEMOVE = getattr(winput, "WM_MOUSEMOVE", 0x0200)
WM_MOUSEWHEEL = getattr(winput, "WM_MOUSEWHEEL", 0x020A)
WM_MOUSEHWHEEL = getattr(winput, "WM_MOUSEHWHEEL", 0x020E)


_MOD_GROUPS: Dict[str, Set[int]] = {
    "shift": {VK_SHIFT, VK_LSHIFT, VK_RSHIFT},
    "lshift": {VK_LSHIFT},
    "rshift": {VK_RSHIFT},

    "ctrl": {VK_CONTROL, VK_LCONTROL, VK_RCONTROL},
    "control": {VK_CONTROL, VK_LCONTROL, VK_RCONTROL},
    "lctrl": {VK_LCONTROL},
    "rctrl": {VK_RCONTROL},
    "lcontrol": {VK_LCONTROL},
    "rcontrol": {VK_RCONTROL},

    "alt": {VK_MENU, VK_LMENU, VK_RMENU},
    "menu": {VK_MENU, VK_LMENU, VK_RMENU},
    "lalt": {VK_LMENU},
    "ralt": {VK_RMENU},
    "altgr": {VK_RMENU},

    "win": {VK_LWIN, VK_RWIN},
    "lwin": {VK_LWIN},
    "rwin": {VK_RWIN},
}


SPECIAL_KEYS: Dict[str, int] = {
    "esc": getattr(winput, "VK_ESCAPE", 0x1B),
    "escape": getattr(winput, "VK_ESCAPE", 0x1B),
    "enter": getattr(winput, "VK_RETURN", 0x0D),
    "return": getattr(winput, "VK_RETURN", 0x0D),
    "tab": getattr(winput, "VK_TAB", 0x09),
    "space": getattr(winput, "VK_SPACE", 0x20),
    "backspace": getattr(winput, "VK_BACK", 0x08),
    "delete": getattr(winput, "VK_DELETE", 0x2E),
    "del": getattr(winput, "VK_DELETE", 0x2E),
    "insert": getattr(winput, "VK_INSERT", 0x2D),
    "home": getattr(winput, "VK_HOME", 0x24),
    "end": getattr(winput, "VK_END", 0x23),
    "pgup": getattr(winput, "VK_PRIOR", 0x21),
    "pageup": getattr(winput, "VK_PRIOR", 0x21),
    "pgdn": getattr(winput, "VK_NEXT", 0x22),
    "pagedown": getattr(winput, "VK_NEXT", 0x22),
    "up": getattr(winput, "VK_UP", 0x26),
    "down": getattr(winput, "VK_DOWN", 0x28),
    "left": getattr(winput, "VK_LEFT", 0x25),
    "right": getattr(winput, "VK_RIGHT", 0x27),

    "capslock": getattr(winput, "VK_CAPITAL", 0x14),
    "caps": getattr(winput, "VK_CAPITAL", 0x14),

    "pause": getattr(winput, "VK_PAUSE", 0x13),
    "break": getattr(winput, "VK_PAUSE", 0x13),

    "printscreen": getattr(winput, "VK_SNAPSHOT", 0x2C),
    "prtsc": getattr(winput, "VK_SNAPSHOT", 0x2C),
    "snapshot": getattr(winput, "VK_SNAPSHOT", 0x2C),

    "scrolllock": getattr(winput, "VK_SCROLL", 0x91),
    "scroll": getattr(winput, "VK_SCROLL", 0x91),

    "apps": getattr(winput, "VK_APPS", 0x5D),
    "menukey": getattr(winput, "VK_APPS", 0x5D),
    "contextmenu": getattr(winput, "VK_APPS", 0x5D),

    "clear": getattr(winput, "VK_CLEAR", 0x0C),
    "help": getattr(winput, "VK_HELP", 0x2F),
    "select": getattr(winput, "VK_SELECT", 0x29),
    "execute": getattr(winput, "VK_EXECUTE", 0x2B),
    "print": getattr(winput, "VK_PRINT", 0x2A),
    "sleep": getattr(winput, "VK_SLEEP", 0x5F),

    "volumeup": getattr(winput, "VK_VOLUME_UP", 0xAF),
    "volup": getattr(winput, "VK_VOLUME_UP", 0xAF),
    "volumedown": getattr(winput, "VK_VOLUME_DOWN", 0xAE),
    "voldown": getattr(winput, "VK_VOLUME_DOWN", 0xAE),
    "volumemute": getattr(winput, "VK_VOLUME_MUTE", 0xAD),
    "mute": getattr(winput, "VK_VOLUME_MUTE", 0xAD),

    "medianext": getattr(winput, "VK_MEDIA_NEXT_TRACK", 0xB0),
    "medianexttrack": getattr(winput, "VK_MEDIA_NEXT_TRACK", 0xB0),
    "mediaprev": getattr(winput, "VK_MEDIA_PREV_TRACK", 0xB1),
    "mediaprevtrack": getattr(winput, "VK_MEDIA_PREV_TRACK", 0xB1),
    "mediastop": getattr(winput, "VK_MEDIA_STOP", 0xB2),
    "mediaplaypause": getattr(winput, "VK_MEDIA_PLAY_PAUSE", 0xB3),
}

for i in range(1, 25):
    SPECIAL_KEYS[f"f{i}"] = getattr(winput, f"VK_F{i}", 0x70 + (i - 1))

SPECIAL_KEYS.update({
    "`": getattr(winput, "VK_OEM_3", 0xC0),
    "backtick": getattr(winput, "VK_OEM_3", 0xC0),
    "grave": getattr(winput, "VK_OEM_3", 0xC0),
    "tilde": getattr(winput, "VK_OEM_3", 0xC0),

    "-": getattr(winput, "VK_OEM_MINUS", 0xBD),
    "=": getattr(winput, "VK_OEM_PLUS", 0xBB),
    "[": getattr(winput, "VK_OEM_4", 0xDB),
    "]": getattr(winput, "VK_OEM_6", 0xDD),
    "\\": getattr(winput, "VK_OEM_5", 0xDC),
    ";": getattr(winput, "VK_OEM_1", 0xBA),
    "'": getattr(winput, "VK_OEM_7", 0xDE),
    ",": getattr(winput, "VK_OEM_COMMA", 0xBC),
    ".": getattr(winput, "VK_OEM_PERIOD", 0xBE),
    "/": getattr(winput, "VK_OEM_2", 0xBF),

    "minus": getattr(winput, "VK_OEM_MINUS", 0xBD),
    "equals": getattr(winput, "VK_OEM_PLUS", 0xBB),
    "plus": getattr(winput, "VK_OEM_PLUS", 0xBB),
    "lbracket": getattr(winput, "VK_OEM_4", 0xDB),
    "rbracket": getattr(winput, "VK_OEM_6", 0xDD),
    "backslash": getattr(winput, "VK_OEM_5", 0xDC),
    "semicolon": getattr(winput, "VK_OEM_1", 0xBA),
    "quote": getattr(winput, "VK_OEM_7", 0xDE),
    "apostrophe": getattr(winput, "VK_OEM_7", 0xDE),
    "comma": getattr(winput, "VK_OEM_COMMA", 0xBC),
    "period": getattr(winput, "VK_OEM_PERIOD", 0xBE),
    "dot": getattr(winput, "VK_OEM_PERIOD", 0xBE),
    "slash": getattr(winput, "VK_OEM_2", 0xBF),
})

SPECIAL_KEYS.update({
    "numlock": getattr(winput, "VK_NUMLOCK", 0x90),

    "num*": getattr(winput, "VK_MULTIPLY", 0x6A),
    "nummul": getattr(winput, "VK_MULTIPLY", 0x6A),
    "numpadmultiply": getattr(winput, "VK_MULTIPLY", 0x6A),

    "num+": getattr(winput, "VK_ADD", 0x6B),
    "numadd": getattr(winput, "VK_ADD", 0x6B),
    "numpadadd": getattr(winput, "VK_ADD", 0x6B),

    "num-": getattr(winput, "VK_SUBTRACT", 0x6D),
    "numsub": getattr(winput, "VK_SUBTRACT", 0x6D),
    "numpadsubtract": getattr(winput, "VK_SUBTRACT", 0x6D),

    "num.": getattr(winput, "VK_DECIMAL", 0x6E),
    "numdecimal": getattr(winput, "VK_DECIMAL", 0x6E),
    "numpaddecimal": getattr(winput, "VK_DECIMAL", 0x6E),

    "num/": getattr(winput, "VK_DIVIDE", 0x6F),
    "numdiv": getattr(winput, "VK_DIVIDE", 0x6F),
    "numpaddivide": getattr(winput, "VK_DIVIDE", 0x6F),
})

for i in range(10):
    vk = getattr(winput, f"VK_NUMPAD{i}", 0x60 + i)
    SPECIAL_KEYS[f"numpad{i}"] = vk
    SPECIAL_KEYS[f"num{i}"] = vk


def is_modifier_vk(vk: int) -> bool:
    return vk in (
        VK_SHIFT,
        VK_LSHIFT,
        VK_RSHIFT,
        VK_CONTROL,
        VK_LCONTROL,
        VK_RCONTROL,
        VK_MENU,
        VK_LMENU,
        VK_RMENU,
        VK_LWIN,
        VK_RWIN,
    )


def register_key_token(name: str, vk: int) -> None:
    """
    Register a custom key token at runtime.

    Example:
        register_key_token("`", 0xC0)
    """
    SPECIAL_KEYS[name.lower()] = vk
