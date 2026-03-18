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

__version__ = "1.3.0"

__all__ = [
    "Trigger","SuppressPolicy","ChordPolicy","OrderPolicy","FocusPolicy","InjectedPolicy","TextBoundaryPolicy","TextBackspacePolicy","OsKeyRepeatPolicy","ReplacementPolicy",
    "Timing","Constraints","Checks","BindConfig",
    "MouseButton","MouseBindConfig","Callback","Predicate","LogicalConfig",
    "Bind","LogicalBind","TextAbbreviationBind","KeyboardBind","MouseBind","Hook","get_default_hook","set_default_hook","join","unbind",
    "bind_key","bind_logical","bind_text","add_abbreviation","bind_abbreviation","bind_mouse","presets","register_key_token","winput",
    "reinstall_hooks","rehook"
]
