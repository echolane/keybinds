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
    "ctrl": {VK_CONTROL, VK_LCONTROL, VK_RCONTROL},
    "control": {VK_CONTROL, VK_LCONTROL, VK_RCONTROL},
    "alt": {VK_MENU, VK_LMENU, VK_RMENU},
    "menu": {VK_MENU, VK_LMENU, VK_RMENU},
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
    "volumeup": getattr(winput, "VK_VOLUMEUP", 0xAF),
    "volumedown": getattr(winput, "VK_VOLUMEDOWN", 0xAE),
    "mute": getattr(winput, "VK_VOLUMEMUTE", 0xAD),
}

SPECIAL_KEYS.update({
    "`": getattr(winput, "VK_OEM_3", 0xC0),        # `~
    "backtick": getattr(winput, "VK_OEM_3", 0xC0),
    "grave": getattr(winput, "VK_OEM_3", 0xC0),
    "tilde": getattr(winput, "VK_OEM_3", 0xC0),

    "-": getattr(winput, "VK_OEM_MINUS", 0xBD),   # -_
    "=": getattr(winput, "VK_OEM_PLUS", 0xBB),    # =+
    "[": getattr(winput, "VK_OEM_4", 0xDB),       # [{
    "]": getattr(winput, "VK_OEM_6", 0xDD),       # ]}
    "\\": getattr(winput, "VK_OEM_5", 0xDC),      # \|
    ";": getattr(winput, "VK_OEM_1", 0xBA),       # ;:
    "'": getattr(winput, "VK_OEM_7", 0xDE),       # '"
    ",": getattr(winput, "VK_OEM_COMMA", 0xBC),   # ,<
    ".": getattr(winput, "VK_OEM_PERIOD", 0xBE),  # .>
    "/": getattr(winput, "VK_OEM_2", 0xBF),       # /?
})

for i in range(1, 25):
    SPECIAL_KEYS[f"f{i}"] = getattr(winput, f"VK_F{i}", 0x70 + (i - 1))


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
