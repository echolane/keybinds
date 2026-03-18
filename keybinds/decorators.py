from __future__ import annotations

from typing import Callable, Optional, Union, List

from .types import (
    Callback,
    MouseButton,
    MouseBindConfig,
    BindConfig,
    SuppressPolicy,
    Trigger,
    LogicalConfig,
)
from .bind import get_default_hook, Hook, Bind, LogicalBind, TextAbbreviationBind, MouseBind
from ._bind_registry import add_binds_to_func as _registry_add_binds_to_func


def _add_binds_to_func(binds: List[Union[Bind, LogicalBind, TextAbbreviationBind, MouseBind]], func: Callback) -> None:
    _registry_add_binds_to_func(func, binds)


def bind_key(
    keys: Union[str, List[str]],
    *,
    hwnd: Optional[int] = None,
    trigger_on_release: bool = False,
    suppress: bool = False,
    config: Optional[BindConfig] = None,
    hook: Optional[Hook] = None,
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

        _add_binds_to_func(binds, func)
        return func

    return decorator


def bind_logical(
    exprs: Union[str, List[str]],
    *,
    hwnd: Optional[int] = None,
    config: Optional[BindConfig] = None,
    logical_config: Optional[LogicalConfig] = None,
    hook: Optional[Hook] = None,
) -> Callable[[Callback], Callback]:
    def decorator(func: Callback) -> Callback:
        nonlocal exprs, hook
        items = exprs if isinstance(exprs, list) else [exprs]

        if hook is None:
            hook = get_default_hook()

        binds = []
        for expr in items:
            b = hook.bind_logical(
                expr,
                func,
                config=config,
                logical_config=logical_config,
                hwnd=hwnd,
            )
            binds.append(b)

        _add_binds_to_func(binds, func)
        return func

    return decorator


def bind_text(
    texts: Union[str, List[str]],
    *,
    hwnd: Optional[int] = None,
    config: Optional[BindConfig] = None,
    logical_config: Optional[LogicalConfig] = None,
    hook: Optional[Hook] = None,
) -> Callable[[Callback], Callback]:
    def decorator(func: Callback) -> Callback:
        nonlocal texts, hook
        items = texts if isinstance(texts, list) else [texts]

        if hook is None:
            hook = get_default_hook()

        binds = []
        for text in items:
            b = hook.bind_text(
                text,
                func,
                config=config,
                logical_config=logical_config,
                hwnd=hwnd,
            )
            binds.append(b)

        _add_binds_to_func(binds, func)
        return func

    return decorator


def add_abbreviation(
    typed: str,
    replacement: str,
    callback: Optional[Callback] = None,
    *,
    hwnd: Optional[int] = None,
    config: Optional[BindConfig] = None,
    logical_config: Optional[LogicalConfig] = None,
    hook: Optional[Hook] = None,
) -> TextAbbreviationBind:
    if hook is None:
        hook = get_default_hook()

    return hook.add_abbreviation(
        typed,
        replacement,
        callback,
        config=config,
        logical_config=logical_config,
        hwnd=hwnd,
    )


def bind_abbreviation(
    typed: Union[str, List[str]],
    replacement: str,
    *,
    hwnd: Optional[int] = None,
    config: Optional[BindConfig] = None,
    logical_config: Optional[LogicalConfig] = None,
    hook: Optional[Hook] = None,
) -> Callable[[Callback], Callback]:
    def decorator(func: Callback) -> Callback:
        nonlocal typed, hook
        items = typed if isinstance(typed, list) else [typed]

        if hook is None:
            hook = get_default_hook()

        binds = []
        for item in items:
            b = hook.add_abbreviation(
                item,
                replacement,
                func,
                config=config,
                logical_config=logical_config,
                hwnd=hwnd,
            )
            binds.append(b)

        _add_binds_to_func(binds, func)
        return func

    return decorator


def bind_mouse(
    buttons: Union[str, MouseButton, List[Union[str, MouseButton]]] = MouseButton.LEFT,
    *,
    hwnd: Optional[int] = None,
    config: Optional[MouseBindConfig] = None,
    hook: Optional[Hook] = None,
) -> Callable[[Callback], Callback]:
    def decorator(func: Callback) -> Callback:
        btns = buttons if isinstance(buttons, list) else [buttons]
        cfg = config or MouseBindConfig()

        nonlocal hook
        if hook is None:
            hook = get_default_hook()

        binds = []
        for btn in btns:
            b = hook.bind_mouse(btn, func, config=cfg, hwnd=hwnd)
            binds.append(b)

        _add_binds_to_func(binds, func)
        return func

    return decorator


__all__ = [
    "bind_key",
    "bind_logical",
    "bind_text",
    "add_abbreviation",
    "bind_abbreviation",
    "bind_mouse",
]
