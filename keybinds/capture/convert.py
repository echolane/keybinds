from typing import FrozenSet, Optional, Union

from .._constants import SPECIAL_KEYS, _MOD_GROUPS


_MODIFIERS = {
    0x10: "shift",
    0x11: "ctrl",
    0x12: "alt",
    0x5B: "win",
    0x5C: "win",
    0xA0: "lshift",
    0xA1: "rshift",
    0xA2: "lctrl",
    0xA3: "rctrl",
    0xA4: "lalt",
    0xA5: "ralt",
}
_VK_NAMES = {value: key for key, value in SPECIAL_KEYS.items()}
_VK_NAMES.update(
    {
        0x08: "backspace",
        0x09: "tab",
        0x0D: "enter",
        0x1B: "esc",
        0x20: "space",
        0x14: "capslock",
        0x21: "pgup",
        0x22: "pgdn",
        0x2C: "printscreen",
        0x2E: "delete",
        0x5D: "apps",
        0x90: "numlock",
        0x91: "scrolllock",
        0x6A: "num*",
        0x6B: "num+",
        0x6D: "num-",
        0x6E: "num.",
        0x6F: "num/",
        0xAD: "volumemute",
        0xAE: "volumedown",
        0xAF: "volumeup",
    }
)
for _index in range(10):
    _VK_NAMES[0x60 + _index] = "numpad{}".format(_index)


def vk_to_token(vk: int, side_specific: bool = False) -> str:
    vk = int(vk)
    if vk in _MODIFIERS:
        token = _MODIFIERS[vk]
        if not side_specific and token.startswith(("l", "r")):
            token = token[1:]
        return token
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x70 <= vk <= 0x87:
        return "f{}".format(vk - 0x6F)
    return _VK_NAMES.get(vk, "vk_{:02x}".format(vk))


def token_to_vk(token: str) -> int:
    normalized = token.lower()
    for vk in range(8, 256):
        if vk_to_token(vk, True) == normalized or vk_to_token(vk) == normalized:
            return vk
    if normalized in SPECIAL_KEYS:
        return int(SPECIAL_KEYS[normalized])
    if len(normalized) == 1:
        return ord(normalized.upper())
    if normalized.startswith("f") and normalized[1:].isdigit():
        function_number = int(normalized[1:])
        if 1 <= function_number <= 24:
            return 0x6F + function_number
    raise ValueError("Unknown key token: {!r}".format(token))


def token_to_vks(token: str) -> FrozenSet[int]:
    normalized = token.lower()
    group = _MOD_GROUPS.get(normalized)
    return frozenset(group) if group else frozenset((token_to_vk(normalized),))


def vk_to_char(
    vk: int,
    shift: bool = False,
    caps_lock: bool = False,
    alt_gr: bool = False,
    hwnd: Optional[Union[int, str]] = None,
) -> Optional[str]:
    try:
        from ..logical.translate import LogicalTranslator

        translator = LogicalTranslator()
        layout = translator.current_layout()
        if hwnd is not None:
            from .._window import get_window
            from ..logical import translate

            target = get_window(hwnd).hwnd
            process_id = __import__("ctypes").c_ulong(0)
            thread_id = int(
                translate._GetWindowThreadProcessId(
                    target, __import__("ctypes").byref(process_id)
                )
            )
            if thread_id:
                layout = translate._hkl_to_int(
                    translate._GetKeyboardLayout(thread_id)
                ) or layout
        char = translator.to_char(
            vk=vk,
            scan_code=0,
            flags=0,
            shift=shift,
            ctrl=False,
            alt=False,
            altgr=alt_gr,
            caps=caps_lock,
            layout=layout,
        )
        if char and all(ord(value) >= 32 and ord(value) != 127 for value in char):
            return char
    except Exception:
        pass
    return None
