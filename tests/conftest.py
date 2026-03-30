from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / 'keybinds'


def _ensure_package(name: str, path: Path) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__path__ = [str(path)]
    sys.modules[name] = mod
    return mod


def _fake_winput() -> types.ModuleType:
    mod = types.ModuleType('keybinds.winput')
    attrs: Dict[str, Any] = {
        'VK_SHIFT': 0x10,
        'VK_CONTROL': 0x11,
        'VK_MENU': 0x12,
        'VK_LSHIFT': 0xA0,
        'VK_RSHIFT': 0xA1,
        'VK_LCONTROL': 0xA2,
        'VK_RCONTROL': 0xA3,
        'VK_LMENU': 0xA4,
        'VK_RMENU': 0xA5,
        'VK_LWIN': 0x5B,
        'VK_RWIN': 0x5C,
        'VK_CAPITAL': 0x14,
        'VK_NUMLOCK': 0x90,
        'VK_SCROLL': 0x91,
        'VK_BACK': 0x08,
        'VK_ESCAPE': 0x1B,
        'VK_RETURN': 0x0D,
        'VK_TAB': 0x09,
        'VK_SPACE': 0x20,
        'VK_DELETE': 0x2E,
        'VK_INSERT': 0x2D,
        'VK_HOME': 0x24,
        'VK_END': 0x23,
        'VK_PRIOR': 0x21,
        'VK_NEXT': 0x22,
        'VK_UP': 0x26,
        'VK_DOWN': 0x28,
        'VK_LEFT': 0x25,
        'VK_RIGHT': 0x27,
        'VK_PAUSE': 0x13,
        'VK_SNAPSHOT': 0x2C,
        'VK_APPS': 0x5D,
        'VK_CLEAR': 0x0C,
        'VK_HELP': 0x2F,
        'VK_SELECT': 0x29,
        'VK_EXECUTE': 0x2B,
        'VK_PRINT': 0x2A,
        'VK_SLEEP': 0x5F,
        'VK_VOLUME_UP': 0xAF,
        'VK_VOLUME_DOWN': 0xAE,
        'VK_VOLUME_MUTE': 0xAD,
        'VK_MEDIA_NEXT_TRACK': 0xB0,
        'VK_MEDIA_PREV_TRACK': 0xB1,
        'VK_MEDIA_STOP': 0xB2,
        'VK_MEDIA_PLAY_PAUSE': 0xB3,
        'VK_OEM_3': 0xC0,
        'VK_OEM_MINUS': 0xBD,
        'VK_OEM_PLUS': 0xBB,
        'VK_OEM_4': 0xDB,
        'VK_OEM_6': 0xDD,
        'VK_OEM_5': 0xDC,
        'VK_OEM_1': 0xBA,
        'VK_OEM_7': 0xDE,
        'VK_OEM_COMMA': 0xBC,
        'VK_OEM_PERIOD': 0xBE,
        'VK_OEM_2': 0xBF,
        'VK_MULTIPLY': 0x6A,
        'VK_ADD': 0x6B,
        'VK_SUBTRACT': 0x6D,
        'VK_DECIMAL': 0x6E,
        'VK_DIVIDE': 0x6F,
        'WM_LBUTTONDOWN': 0x0201,
        'WM_LBUTTONUP': 0x0202,
        'WM_RBUTTONDOWN': 0x0204,
        'WM_RBUTTONUP': 0x0205,
        'WM_MBUTTONDOWN': 0x0207,
        'WM_MBUTTONUP': 0x0208,
        'WM_XBUTTONDOWN': 0x020B,
        'WM_XBUTTONUP': 0x020C,
        'WM_KEYDOWN': 0x0100,
        'WM_KEYUP': 0x0101,
        'WM_SYSKEYDOWN': 0x0104,
        'WM_SYSKEYUP': 0x0105,
        'WM_MOUSEMOVE': 0x0200,
        'WM_MOUSEWHEEL': 0x020A,
        'WM_MOUSEHWHEEL': 0x020E,
        'KEYEVENTF_KEYUP': 0x0002,
        'KEYEVENTF_UNICODE': 0x0004,
        'MAPVK_VK_TO_VSC': 0,
    }
    for i in range(1, 25):
        attrs[f'VK_F{i}'] = 0x70 + (i - 1)
    for i in range(10):
        attrs[f'VK_NUMPAD{i}'] = 0x60 + i
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


class FakeHook:
    def __init__(self) -> None:
        self.calls = []

    def bind(self, *args, **kwargs):
        bind = types.SimpleNamespace(kind='key', args=args, kwargs=kwargs, hook=self)
        self.calls.append(('bind', args, kwargs, bind))
        return bind

    def bind_logical(self, *args, **kwargs):
        bind = types.SimpleNamespace(kind='logical', args=args, kwargs=kwargs, hook=self)
        self.calls.append(('bind_logical', args, kwargs, bind))
        return bind

    def bind_text(self, *args, **kwargs):
        bind = types.SimpleNamespace(kind='text', args=args, kwargs=kwargs, hook=self)
        self.calls.append(('bind_text', args, kwargs, bind))
        return bind

    def add_abbreviation(self, *args, **kwargs):
        bind = types.SimpleNamespace(kind='abbreviation', args=args, kwargs=kwargs, hook=self)
        self.calls.append(('add_abbreviation', args, kwargs, bind))
        return bind

    def bind_mouse(self, *args, **kwargs):
        bind = types.SimpleNamespace(kind='mouse', args=args, kwargs=kwargs, hook=self)
        self.calls.append(('bind_mouse', args, kwargs, bind))
        return bind

    def wait(self, timeout=None):
        self.calls.append(('wait', (timeout,), {}, None))
        return True

    def close(self):
        self.calls.append(('close', (), {}, None))


class Loader:
    def __init__(self) -> None:
        self.default_hook = FakeHook()
        self.package = self._bootstrap()

    def _bootstrap(self) -> types.ModuleType:
        for name in list(sys.modules):
            if name == 'keybinds' or name.startswith('keybinds.'):
                del sys.modules[name]

        package = _ensure_package('keybinds', PACKAGE_ROOT)
        winput = _fake_winput()
        sys.modules['keybinds.winput'] = winput
        package.winput = winput
        return package

    def load(self, fullname: str, relpath: str):
        spec = importlib.util.spec_from_file_location(fullname, ROOT / relpath)
        if spec is None or spec.loader is None:
            raise RuntimeError(f'Could not load module {fullname!r}')
        module = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = module
        spec.loader.exec_module(module)
        return module

    def package_module(self, name: str, relative_dir: str) -> types.ModuleType:
        return _ensure_package(name, ROOT / relative_dir)

    def install_fake_bind_module(self):
        bind_module = types.ModuleType('keybinds.bind')
        bind_module.Hook = FakeHook
        bind_module.Bind = object
        bind_module.LogicalBind = object
        bind_module.TextAbbreviationBind = object
        bind_module.MouseBind = object
        bind_module.get_default_hook = lambda: self.default_hook
        sys.modules['keybinds.bind'] = bind_module
        self.package.get_default_hook = bind_module.get_default_hook
        self.package.join = lambda hook=None: ('joined', hook)
        return bind_module


@pytest.fixture

def kb_env():
    loader = Loader()
    constants = loader.load('keybinds._constants', 'keybinds/_constants.py')
    parsing = loader.load('keybinds._parsing', 'keybinds/_parsing.py')
    types_mod = loader.load('keybinds.types', 'keybinds/types.py')
    registry = loader.load('keybinds._bind_registry', 'keybinds/_bind_registry.py')

    loader.package_module('keybinds.logical', 'keybinds/logical')
    logical_parsing = loader.load('keybinds.logical.parsing', 'keybinds/logical/parsing.py')

    loader.package_module('keybinds.diagnostics', 'keybinds/diagnostics')
    diagnostics_core = loader.load('keybinds.diagnostics.core', 'keybinds/diagnostics/core.py')
    diagnostics_reporting = loader.load('keybinds.diagnostics.reporting', 'keybinds/diagnostics/reporting.py')
    diagnostics_analysis = loader.load('keybinds.diagnostics.analysis', 'keybinds/diagnostics/analysis.py')

    loader.install_fake_bind_module()
    decorators = loader.load('keybinds.decorators', 'keybinds/decorators.py')
    simple = loader.load('keybinds.simple', 'keybinds/simple.py')

    return types.SimpleNamespace(
        loader=loader,
        package=loader.package,
        winput=loader.package.winput,
        default_hook=loader.default_hook,
        constants=constants,
        parsing=parsing,
        logical_parsing=logical_parsing,
        types=types_mod,
        registry=registry,
        decorators=decorators,
        simple=simple,
        diagnostics_core=diagnostics_core,
        diagnostics_reporting=diagnostics_reporting,
        diagnostics_analysis=diagnostics_analysis,
        FakeHook=FakeHook,
    )


class _FakeBackendSingleton:
    def __init__(self) -> None:
        self.registered = []
        self.reinstall_count = 0

    def register(self, hook_obj) -> None:
        if hook_obj not in self.registered:
            self.registered.append(hook_obj)

    def unregister(self, hook_obj) -> None:
        self.registered = [item for item in self.registered if item is not hook_obj]

    def reinstall_hooks(self) -> None:
        self.reinstall_count += 1


class HookDriver:
    def __init__(self, env, hook) -> None:
        self.env = env
        self.hook = hook
        self.now = 0
        self.pressed_keys = set()
        self.pressed_mouse = set()
        self.pressed_keys_all = set()
        self.pressed_mouse_all = set()
        self.pressed_keys_injected = set()
        self.pressed_mouse_injected = set()

    def _state(self):
        return self.env.state_mod.InputState(
            self.pressed_keys,
            self.pressed_mouse,
            self.pressed_keys_all,
            self.pressed_mouse_all,
            self.pressed_keys_injected,
            self.pressed_mouse_injected,
        )

    def _tick(self, dt: int | None) -> int:
        self.now += 1 if dt is None else int(dt)
        return self.now

    def key(self, vk: int, action: str = 'down', *, dt: int | None = None, injected: bool = False, scan_code: int = 0, flags: int = 0):
        timestamp = self._tick(dt)
        action_map = {
            'down': self.env.winput.WM_KEYDOWN,
            'up': self.env.winput.WM_KEYUP,
            'sysdown': self.env.winput.WM_SYSKEYDOWN,
            'sysup': self.env.winput.WM_SYSKEYUP,
        }
        msg = action_map[action]
        is_down = msg in (self.env.winput.WM_KEYDOWN, self.env.winput.WM_SYSKEYDOWN)
        is_up = msg in (self.env.winput.WM_KEYUP, self.env.winput.WM_SYSKEYUP)
        base = self.pressed_keys_injected if injected else self.pressed_keys
        was_down = (vk in base) if is_down else False

        if is_down:
            self.pressed_keys_all.add(vk)
            base.add(vk)
        elif is_up:
            base.discard(vk)
            if (vk in self.pressed_keys) or (vk in self.pressed_keys_injected):
                self.pressed_keys_all.add(vk)
            else:
                self.pressed_keys_all.discard(vk)

        event = self.env.winput.KeyboardEvent(
            vkCode=vk,
            action=msg,
            time=timestamp,
            injected=injected,
            scanCode=scan_code,
            flags=flags,
        )
        setattr(event, '_sb_is_repeat', bool(is_down and was_down))
        return self.hook._handle_keyboard_event(event, self._state())

    def mouse(self, button, action: str = 'down', *, dt: int | None = None, injected: bool = False):
        timestamp = self._tick(dt)
        btn = button if isinstance(button, self.env.types.MouseButton) else self.env._mouse._normalize_mouse_button(button)
        action_lookup = {
            self.env.types.MouseButton.LEFT: (self.env.winput.WM_LBUTTONDOWN, self.env.winput.WM_LBUTTONUP, 0),
            self.env.types.MouseButton.RIGHT: (self.env.winput.WM_RBUTTONDOWN, self.env.winput.WM_RBUTTONUP, 0),
            self.env.types.MouseButton.MIDDLE: (self.env.winput.WM_MBUTTONDOWN, self.env.winput.WM_MBUTTONUP, 0),
            self.env.types.MouseButton.X1: (self.env.winput.WM_XBUTTONDOWN, self.env.winput.WM_XBUTTONUP, 1),
            self.env.types.MouseButton.X2: (self.env.winput.WM_XBUTTONDOWN, self.env.winput.WM_XBUTTONUP, 2),
        }
        down_act, up_act, additional_data = action_lookup[btn]
        msg = down_act if action == 'down' else up_act
        is_down = action == 'down'
        base = self.pressed_mouse_injected if injected else self.pressed_mouse
        if is_down:
            self.pressed_mouse_all.add(btn)
            base.add(btn)
        else:
            base.discard(btn)
            if (btn in self.pressed_mouse) or (btn in self.pressed_mouse_injected):
                self.pressed_mouse_all.add(btn)
            else:
                self.pressed_mouse_all.discard(btn)

        event = self.env.winput.MouseEvent(
            action=msg,
            time=timestamp,
            injected=injected,
            additional_data=additional_data,
        )
        return self.hook._handle_mouse_event(event, self._state())


@pytest.fixture
def runtime_env():
    loader = Loader()
    winput = loader.package.winput

    setattr(winput, 'WP_CONTINUE', 0)
    setattr(winput, 'WP_DONT_PASS_INPUT_ON', 1)

    class _Event:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    setattr(winput, 'KeyboardEvent', _Event)
    setattr(winput, 'MouseEvent', _Event)

    recorded_presses = []
    recorded_releases = []
    setattr(winput, 'press_key', lambda vk: recorded_presses.append(vk))
    setattr(winput, 'release_key', lambda vk: recorded_releases.append(vk))
    setattr(winput, 'hook_keyboard', lambda cb: None)
    setattr(winput, 'hook_mouse', lambda cb: None)
    setattr(winput, 'unhook_keyboard', lambda: None)
    setattr(winput, 'unhook_mouse', lambda: None)
    setattr(winput, 'wait_messages', lambda cb=None: None)
    setattr(winput, 'ensure_message_queue', lambda: None)
    setattr(winput, 'get_current_thread_id', lambda: 1)
    setattr(winput, 'post_thread_message', lambda thread_id, msg, wparam, lparam: None)

    backend_module = types.ModuleType('keybinds._backend')
    backend_singleton = _FakeBackendSingleton()

    class _GlobalBackend:
        @classmethod
        def instance(cls):
            return backend_singleton

    backend_module._GlobalBackend = _GlobalBackend
    backend_module.reinstall_hooks = backend_singleton.reinstall_hooks
    backend_module.rehook = backend_singleton.reinstall_hooks
    sys.modules['keybinds._backend'] = backend_module

    window_module = types.ModuleType('keybinds._window')
    window_module.get_window = lambda hwnd=None: None
    sys.modules['keybinds._window'] = window_module

    loader.load('keybinds._constants', 'keybinds/_constants.py')
    loader.load('keybinds._parsing', 'keybinds/_parsing.py')
    types_mod = loader.load('keybinds.types', 'keybinds/types.py')
    state_mod = loader.load('keybinds._state', 'keybinds/_state.py')
    loader.load('keybinds._bind_registry', 'keybinds/_bind_registry.py')

    loader.package_module('keybinds.diagnostics', 'keybinds/diagnostics')
    loader.load('keybinds.diagnostics.core', 'keybinds/diagnostics/core.py')
    loader.load('keybinds.diagnostics.reporting', 'keybinds/diagnostics/reporting.py')
    loader.load('keybinds.diagnostics.tracing', 'keybinds/diagnostics/tracing.py')
    loader.load('keybinds.diagnostics.analysis', 'keybinds/diagnostics/analysis.py')
    loader.load('keybinds.diagnostics', 'keybinds/diagnostics/__init__.py')

    loader.load('keybinds._dispatcher', 'keybinds/_dispatcher.py')
    loader.load('keybinds._base_bind', 'keybinds/_base_bind.py')
    keyboard_mod = loader.load('keybinds._keyboard', 'keybinds/_keyboard.py')
    mouse_mod = loader.load('keybinds._mouse', 'keybinds/_mouse.py')

    loader.package_module('keybinds.logical', 'keybinds/logical')
    logical_parsing = loader.load('keybinds.logical.parsing', 'keybinds/logical/parsing.py')

    translate_mod = types.ModuleType('keybinds.logical.translate')
    translate_mod.sent_backspaces = []
    translate_mod.sent_unicode_text = []

    class FakeLogicalTranslator:
        char_map = {}
        _last_known_layout = 0x0409

        def __init__(self, buf_len: int = 8):
            self.buf_len = buf_len

        @staticmethod
        def scancode_from_vk(vk: int, layout: int) -> int:
            return vk

        @classmethod
        def current_layout(cls) -> int:
            return cls._last_known_layout

        @staticmethod
        def capslock_on() -> bool:
            return False

        def to_char(self, *, vk: int, scan_code: int, flags: int, shift: bool, ctrl: bool, alt: bool, altgr: bool, caps: bool, layout: int):
            del scan_code, flags, ctrl, alt, altgr, layout
            entry = self.char_map.get(vk)
            if callable(entry):
                return entry(vk=vk, shift=shift, caps=caps)
            if entry is None:
                if 65 <= vk <= 90:
                    base = chr(vk).lower()
                    return base.upper() if (shift ^ caps) else base
                if 48 <= vk <= 57:
                    return chr(vk)
                if vk == getattr(winput, 'VK_SPACE', 0x20):
                    return ' '
                if vk == getattr(winput, 'VK_OEM_COMMA', 0xBC):
                    return ','
                if vk == getattr(winput, 'VK_OEM_PERIOD', 0xBE):
                    return '>' if shift else '.'
                if vk == getattr(winput, 'VK_OEM_2', 0xBF):
                    return '?' if shift else '/'
                if vk == getattr(winput, 'VK_OEM_MINUS', 0xBD):
                    return '_' if shift else '-'
                if vk == getattr(winput, 'VK_OEM_PLUS', 0xBB):
                    return '+' if shift else '='
                return None
            if isinstance(entry, tuple):
                lower, upper = entry
                return upper if (shift ^ caps) else lower
            return entry

    translate_mod.LogicalTranslator = FakeLogicalTranslator
    translate_mod.send_backspaces = lambda count: translate_mod.sent_backspaces.append(int(count))
    translate_mod.send_unicode_text = lambda text: translate_mod.sent_unicode_text.append(text)
    sys.modules['keybinds.logical.translate'] = translate_mod

    logical_keyboard = loader.load('keybinds.logical.keyboard', 'keybinds/logical/keyboard.py')
    logical_abbreviation = loader.load('keybinds.logical.abbreviation', 'keybinds/logical/abbreviation.py')
    hook_mod = loader.load('keybinds._hook', 'keybinds/_hook.py')
    bind_mod = loader.load('keybinds.bind', 'keybinds/bind.py')

    created_hooks = []

    def make_hook(*, auto_start: bool = False, callback_workers: int = 1, diagnostics=None):
        hook = bind_mod.Hook(auto_start=auto_start, callback_workers=callback_workers, diagnostics=diagnostics)
        hook._dispatcher.submit = lambda fn, trace=None: fn()
        created_hooks.append(hook)
        return hook

    env = types.SimpleNamespace(
        loader=loader,
        package=loader.package,
        winput=winput,
        types=types_mod,
        state_mod=state_mod,
        keyboard=keyboard_mod,
        _mouse=mouse_mod,
        logical_parsing=logical_parsing,
        logical_keyboard=logical_keyboard,
        logical_abbreviation=logical_abbreviation,
        translate=translate_mod,
        hook_mod=hook_mod,
        bind=bind_mod,
        backend_singleton=backend_singleton,
        recorded_presses=recorded_presses,
        recorded_releases=recorded_releases,
        make_hook=make_hook,
        HookDriver=HookDriver,
    )

    try:
        yield env
    finally:
        for hook in created_hooks:
            try:
                hook.close()
            except Exception:
                pass
