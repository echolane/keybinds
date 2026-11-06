from __future__ import annotations

import weakref
from typing import Any, Callable, Iterable, List, Dict, Optional

Callback = Callable[..., Any]

_BIND_OWNER_FUNC: Dict[int, tuple] = {}
_BIND_OWNER_HOOK: Dict[int, tuple] = {}
_BIND_KIND: Dict[int, tuple] = {}


def _weak_or_value(value: Any):
    try:
        return weakref.ref(value)
    except TypeError:
        return value


def _resolve(value: Any) -> Any:
    return value() if isinstance(value, weakref.ReferenceType) else value


def _forget_bind(key: int, bind_ref: weakref.ReferenceType) -> None:
    for registry in (_BIND_OWNER_FUNC, _BIND_OWNER_HOOK, _BIND_KIND):
        entry = registry.get(key)
        if entry is not None and entry[0] is bind_ref:
            registry.pop(key, None)


def register_bind(bind: Any, hook: Any, kind: str) -> None:
    existing = getattr(bind, "hook", None)
    if existing is not None and existing is not hook:
        raise ValueError("bind is already registered to a different hook")
    key = id(bind)
    bind_ref = _weak_or_value(bind)
    bind.hook = hook
    _BIND_OWNER_HOOK[key] = (bind_ref, _weak_or_value(hook))
    _BIND_KIND[key] = (bind_ref, kind)
    if isinstance(bind_ref, weakref.ReferenceType):
        weakref.finalize(bind, _forget_bind, key, bind_ref)


def register_decorated_bind(bind: Any, func: Callback) -> None:
    key = id(bind)
    bind_ref = _weak_or_value(bind)
    _BIND_OWNER_FUNC[key] = (bind_ref, _weak_or_value(func))
    if isinstance(bind_ref, weakref.ReferenceType):
        weakref.finalize(bind, _forget_bind, key, bind_ref)


def owner_func_for_bind(bind: Any) -> Optional[Callback]:
    entry = _BIND_OWNER_FUNC.get(id(bind))
    if entry is None or _resolve(entry[0]) is not bind:
        return None
    return _resolve(entry[1])


def hook_for_bind(bind: Any) -> Any:
    owner = getattr(bind, "hook", None)
    if owner is not None:
        return owner
    entry = _BIND_OWNER_HOOK.get(id(bind))
    if entry is None or _resolve(entry[0]) is not bind:
        return None
    return _resolve(entry[1])


def kind_for_bind(bind: Any) -> Optional[str]:
    entry = _BIND_KIND.get(id(bind))
    if entry is None or _resolve(entry[0]) is not bind:
        return None
    return entry[1]


def unregister_bind(bind: Any) -> None:
    key = id(bind)
    for registry in (_BIND_OWNER_FUNC, _BIND_OWNER_HOOK, _BIND_KIND):
        entry = registry.get(key)
        if entry is not None and _resolve(entry[0]) is bind:
            registry.pop(key, None)
    try:
        bind.hook = None
    except Exception:
        pass


def _as_bind_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def get_func_binds(func: Callback) -> List[Any]:
    if hasattr(func, "binds"):
        binds = getattr(func, "binds")
        if isinstance(binds, list):
            return list(binds)
    if hasattr(func, "bind"):
        return _as_bind_list(getattr(func, "bind"))
    return []


def sync_func_bind_attrs(func: Callback, binds: Iterable[Any]) -> None:
    bind_list = list(binds)
    setattr(func, "binds", bind_list)
    if not bind_list:
        setattr(func, "bind", None)
    elif len(bind_list) == 1:
        setattr(func, "bind", bind_list[0])
    else:
        setattr(func, "bind", list(bind_list))


def add_binds_to_func(func: Callback, binds: Iterable[Any]) -> None:
    bind_list = get_func_binds(func)
    for bind in binds:
        bind_list.append(bind)
        register_decorated_bind(bind, func)
    sync_func_bind_attrs(func, bind_list)


def remove_binds_from_func(func: Callback, binds: Iterable[Any]) -> None:
    removed_ids = set(id(b) for b in binds)
    kept = [b for b in get_func_binds(func) if id(b) not in removed_ids]
    sync_func_bind_attrs(func, kept)
