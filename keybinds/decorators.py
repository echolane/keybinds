from __future__ import annotations

from typing import Callable, Optional, Union, List

from .types import (
    Callback,
    MouseButton,
    MouseBindConfig,
    BindConfig,
    SuppressPolicy,
    Trigger,
)
from .bind import get_default_hook

_active_binds: List[object] = []  # prevent garbage collection


def bind_key(
    key: str,
    *,
    hwnd: Optional[int] = None,
    trigger_on_release: bool = False,
    suppress: bool = False,
    config: Optional[BindConfig] = None,
) -> Callable[[Callback], Callback]:
    def decorator(func: Callback) -> Callback:
        cfg = config
        if cfg is None:
            cfg = BindConfig(
                trigger=Trigger.ON_RELEASE if trigger_on_release else Trigger.ON_PRESS,
                suppress=SuppressPolicy.WHEN_MATCHED if suppress else SuppressPolicy.NEVER,
            )
        b = get_default_hook().bind(key, func, config=cfg, hwnd=hwnd)
        setattr(func, "bind", b)
        _active_binds.append(b)
        return func
    return decorator


def bind_mouse(
    buttons: Union[str, MouseButton, List[Union[str, MouseButton]]] = MouseButton.LEFT,
    *,
    hwnd: Optional[int] = None,
    config: Optional[MouseBindConfig] = None,
) -> Callable[[Callback], Callback]:
    def decorator(func: Callback) -> Callback:
        btns = buttons if isinstance(buttons, list) else [buttons]
        cfg = config or MouseBindConfig()
        # create one bind per button
        binds = []
        for btn in btns:
            b = get_default_hook().bind_mouse(btn, func, config=cfg, hwnd=hwnd)
            binds.append(b)
            _active_binds.append(b)
        setattr(func, "bind", binds[0] if len(binds) == 1 else binds)
        return func
    return decorator
