import sys

if sys.platform != "win32":
    raise RuntimeError("keybinds works on Windows only")

from . import winput

from .types import (
    Trigger,
    SuppressPolicy,
    ChordPolicy,
    OrderPolicy,
    FocusPolicy,
    InjectedPolicy,
    TextBoundaryPolicy,
    TextBackspacePolicy,
    OsKeyRepeatPolicy,
    ReplacementPolicy,
    Timing,
    Constraints,
    Checks,
    BindConfig,
    MouseButton,
    WHEEL_BUTTONS,
    is_wheel_button,
    MouseBindConfig,
    LogicalConfig,
    Callback,
    Predicate,
)


from .bind import Bind, LogicalBind, TextAbbreviationBind, KeyboardBind, MouseBind, Hook, get_default_hook, set_default_hook, join, unbind
from .decorators import bind_key, bind_logical, bind_text, add_abbreviation, bind_abbreviation, bind_mouse
from . import presets

from ._backend import reinstall_hooks, rehook

from ._constants import register_key_token
from .capture import CapturedKey, CapturedChord, CapturedMouse, CaptureConfig, InterceptConfig, ChordEndPolicy, InterceptAction, SuppressFilter, vk_to_token, token_to_vk, vk_to_char, TextAccumulator, TextStream, KeyStream, MouseStream, InterceptStream, InterceptedKey, InterceptedMouse

def capture_key(*args, **kwargs): return get_default_hook().capture_key(*args, **kwargs)
async def capture_key_async(*args, **kwargs): return await get_default_hook().capture_key_async(*args, **kwargs)
def capture_chord(*args, **kwargs): return get_default_hook().capture_chord(*args, **kwargs)
async def capture_chord_async(*args, **kwargs): return await get_default_hook().capture_chord_async(*args, **kwargs)
def capture_mouse(*args, **kwargs): return get_default_hook().capture_mouse(*args, **kwargs)
async def capture_mouse_async(*args, **kwargs): return await get_default_hook().capture_mouse_async(*args, **kwargs)
def stream_keys(*args, **kwargs): return get_default_hook().stream_keys(*args, **kwargs)
def stream_mouse(*args, **kwargs): return get_default_hook().stream_mouse(*args, **kwargs)
def intercept(*args, **kwargs): return get_default_hook().intercept(*args, **kwargs)
def read_text(*args, **kwargs): return get_default_hook().read_text(*args, **kwargs)
def stream_text(*args, **kwargs): return get_default_hook().stream_text(*args, **kwargs)

__version__ = "1.4.0"

__all__ = [
    "Trigger","SuppressPolicy","ChordPolicy","OrderPolicy","FocusPolicy","InjectedPolicy","TextBoundaryPolicy","TextBackspacePolicy","OsKeyRepeatPolicy","ReplacementPolicy",
    "Timing","Constraints","Checks","BindConfig",
    "MouseButton","WHEEL_BUTTONS","is_wheel_button","MouseBindConfig","Callback","Predicate","LogicalConfig",
    "Bind","LogicalBind","TextAbbreviationBind","KeyboardBind","MouseBind","Hook","get_default_hook","set_default_hook","join","unbind",
    "bind_key","bind_logical","bind_text","add_abbreviation","bind_abbreviation","bind_mouse","presets","register_key_token","winput",
    "reinstall_hooks","rehook","CapturedKey","CapturedChord","CapturedMouse","CaptureConfig","InterceptConfig","ChordEndPolicy","InterceptAction","SuppressFilter","vk_to_token","token_to_vk","vk_to_char","TextAccumulator","TextStream","KeyStream","MouseStream","InterceptStream","InterceptedKey","InterceptedMouse","capture_key","capture_key_async","capture_chord","capture_chord_async","capture_mouse","capture_mouse_async","stream_keys","stream_mouse","intercept","read_text","stream_text"
]
