from __future__ import annotations

from typing import Any, Callable, Iterable, List, Dict, Optional

Callback = Callable[..., Any]

_BIND_OWNER_FUNC: Dict[int, Callback] = {}
_BIND_OWNER_HOOK: Dict[int, Any] = {}
_BIND_KIND: Dict[int, str] = {}


def register_bind(bind: Any, hook: Any, kind: str) -> None:
    existing = getattr(bind, "hook", None)
    if existing is not None and existing is not hook:
        raise ValueError("bind is already registered to a different hook")
    key = id(bind)
    bind.hook = hook
    _BIND_OWNER_HOOK[key] = hook
    _BIND_KIND[key] = kind


def register_decorated_bind(bind: Any, func: Callback) -> None:
    _BIND_OWNER_FUNC[id(bind)] = func


def owner_func_for_bind(bind: Any) -> Optional[Callback]:
    return _BIND_OWNER_FUNC.get(id(bind))


def hook_for_bind(bind: Any) -> Any:
    owner = getattr(bind, "hook", None)
    if owner is not None:
        return owner
    return _BIND_OWNER_HOOK.get(id(bind))


def kind_for_bind(bind: Any) -> Optional[str]:
    return _BIND_KIND.get(id(bind))


def unregister_bind(bind: Any) -> None:
    key = id(bind)
    _BIND_OWNER_FUNC.pop(key, None)
    _BIND_OWNER_HOOK.pop(key, None)
    _BIND_KIND.pop(key, None)
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
