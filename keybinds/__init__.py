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
    Timing,
    Constraints,
    Checks,
    BindConfig,
    MouseButton,
    MouseBindConfig,
    Callback,
    Predicate,
)

from .bind import Bind, MouseBind, Hook, get_default_hook, set_default_hook, join
from .decorators import bind_key, bind_mouse
from . import presets

from ._constants import register_key_token

__version__ = "1.1.0"

__all__ = [
    "Trigger","SuppressPolicy","ChordPolicy","OrderPolicy","FocusPolicy","InjectedPolicy",
    "Timing","Constraints","Checks","BindConfig",
    "MouseButton","MouseBindConfig","Callback","Predicate",
    "Bind","MouseBind","Hook","get_default_hook","set_default_hook","join",
    "bind_key","bind_mouse","presets","register_key_token","winput"
]
