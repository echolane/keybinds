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
from .bind import get_default_hook, Hook


def bind_key(
    keys: Union[str, List[str]],
    *,
    hwnd: Optional[int] = None,
    trigger_on_release: bool = False,
    suppress: bool = False,
    config: Optional[BindConfig] = None,
    hook: Optional[Hook] = None
) -> Callable[[Callback], Callback]:
    def decorator(func: Callback) -> Callback:
        nonlocal keys, config, hook
        keys = keys if isinstance(keys, list) else [keys]
        if config is None:
            config = BindConfig(
                trigger=Trigger.ON_RELEASE if trigger_on_release else Trigger.ON_PRESS,
                suppress=SuppressPolicy.WHEN_MATCHED if suppress else SuppressPolicy.NEVER,
            )

        if hook is None:
            hook = get_default_hook()

        binds = []
        for key in keys:
            b = hook.bind(key, func, config=config, hwnd=hwnd)
            binds.append(b)
        setattr(func, "bind", binds[0] if len(binds) == 1 else binds)
        return func
    return decorator


def bind_mouse(
    buttons: Union[str, MouseButton, List[Union[str, MouseButton]]] = MouseButton.LEFT,
    *,
    hwnd: Optional[int] = None,
    config: Optional[MouseBindConfig] = None,
    hook: Optional[Hook] = None
) -> Callable[[Callback], Callback]:
    def decorator(func: Callback) -> Callback:
        btns = buttons if isinstance(buttons, list) else [buttons]
        cfg = config or MouseBindConfig()

        nonlocal hook
        if hook is None:
            hook = get_default_hook()

        # create one bind per button
        binds = []
        for btn in btns:
            b = hook.bind_mouse(btn, func, config=cfg, hwnd=hwnd)
            binds.append(b)
        setattr(func, "bind", binds[0] if len(binds) == 1 else binds)
        return func
    return decorator
