from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Callable, Optional, Union, Generator, List, Tuple, Dict, TYPE_CHECKING

from ._backend import _GlobalBackend
from ._dispatcher import _CallbackDispatcher
from ._keyboard import Bind
from .logical.keyboard import LogicalBind
from .logical.abbreviation import TextAbbreviationBind
from ._mouse import MouseBind, _normalize_mouse_button
from .types import BindConfig, MouseBindConfig, MouseButton, Callback, InjectedPolicy, LogicalConfig, ReplacementPolicy
from .diagnostics import DiagnosticRecord, DiagnosticsConfig, create_diagnostics_manager
from ._bind_registry import (
    register_bind, unregister_bind, owner_func_for_bind, remove_binds_from_func,
    get_func_binds, hook_for_bind, kind_for_bind,
)

if TYPE_CHECKING:
    import asyncio
    from .diagnostics.core import ExplainSelect
    from .diagnostics.reporting import InputAttempt, ExplainReport

KeyboardBind = Union[Bind, LogicalBind, TextAbbreviationBind]

_default_hook: Optional[Hook] = None


def get_default_hook() -> Hook:
    global _default_hook
    if _default_hook is None:
        _default_hook = Hook()
    return _default_hook


def set_default_hook(hook: Hook) -> None:
    global _default_hook
    _default_hook = hook


def _compute_text_replacement_edit(source: str, target: str, policy: ReplacementPolicy) -> Tuple[int, str]:
    if policy == ReplacementPolicy.REPLACE_ALL:
        return len(source), target
    if policy == ReplacementPolicy.APPEND_SUFFIX:
        if target.startswith(source):
            return 0, target[len(source):]
        return len(source), target

    # MINIMAL_DIFF: with a caret at the end we can preserve the longest common
    # prefix, backspace the differing suffix of the typed source, then type the
    # remaining suffix of the target.
    prefix_len = 0
    max_prefix = min(len(source), len(target))
    while prefix_len < max_prefix and source[prefix_len] == target[prefix_len]:
        prefix_len += 1
    return len(source) - prefix_len, target[prefix_len:]


def join(hook: Optional[Hook] = None) -> None:
    """Block until the hook is stopped.

    If hook is None, the default hook will be used.
    """

    if hook is None:
        hook = get_default_hook()

    try:
        hook.wait()
    finally:
        hook.close()


def _is_bind_instance(obj: Any) -> bool:
    return isinstance(obj, (Bind, LogicalBind, TextAbbreviationBind, MouseBind))


def _iter_bind_targets(target: Any):
    if target is None:
        return
    if _is_bind_instance(target):
        yield target
        return
    if callable(target) and (hasattr(target, "binds") or hasattr(target, "bind")):
        for bind in get_func_binds(target):
            yield bind
        return
    if isinstance(target, (list, tuple, set, frozenset)):
        for item in target:
            for bind in _iter_bind_targets(item):
                yield bind


def _bind_belongs_to_hook(bind: Any, hook: "Hook") -> bool:
    owner = getattr(bind, "hook", None)
    if owner is None:
        owner = hook_for_bind(bind)
    return owner is None or owner is hook


def unbind(target: Any, *, hook: Optional["Hook"] = None) -> None:
    binds = list(_iter_bind_targets(target))
    if hook is not None:
        hook.unbind(target)
        return
    if not binds:
        get_default_hook().unbind(target)
        return

    grouped: Dict[Hook, List[Any]] = {}
    for bind in binds:
        owner = hook_for_bind(bind)
        if owner is None:
            owner = get_default_hook()
        grouped.setdefault(owner, []).append(bind)

    for owner_hook, owner_binds in grouped.items():
        owner_hook.unbind(owner_binds)


class Hook:
    def __init__(
        self,
        *,
        callback_workers: int = 1,
        default_config: Optional[BindConfig] = None,
        default_mouse_config: Optional[MouseBindConfig] = None,
        default_logical_config: Optional[LogicalConfig] = None,
        asyncio_loop: "Optional[asyncio.AbstractEventLoop]" = None,
        on_async_error: Optional[Callable[[BaseException], None]] = None,
        auto_start: bool = True,
        diagnostics: Optional[DiagnosticsConfig] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._started = False

        self._pause_count = 0
        self._paused = False

        self.default_config = default_config
        self.default_mouse_config = default_mouse_config
        self.default_logical_config = default_logical_config

        self._diagnostics = create_diagnostics_manager(diagnostics)
        self._dispatcher = _CallbackDispatcher(
            workers=callback_workers,
            asyncio_loop=asyncio_loop,
            on_async_error=on_async_error,
        )

        # binds live in this frontend
        self._keyboard_binds: List[KeyboardBind] = []
        self._mouse_binds: List[MouseBind] = []

        # snapshots used by backend hot path
        self._keyboard_snapshot: Tuple[KeyboardBind, ...] = ()
        self._mouse_snapshot: Tuple[MouseBind, ...] = ()

        if auto_start:
            self.start()

    # -------------------------
    # public API
    # -------------------------

    def __enter__(self) -> Hook:
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @property
    def asyncio_loop(self) -> "Optional[asyncio.AbstractEventLoop]":
        return self._dispatcher.asyncio_loop

    @property
    def started(self) -> bool:
        return self._started

    def bind(self, expr: str, callback: Callback, *, config: Optional[BindConfig] = None, hwnd=None) -> Bind:
        cfg = config or self.default_config or BindConfig()
        b = Bind(
            expr,
            callback,
            config=cfg,
            hwnd=hwnd,
            dispatch=self._dispatcher.submit,
            diagnostics=self._diagnostics,
        )
        register_bind(b, self, "keyboard")
        with self._lock:
            self._keyboard_binds.append(b)
            self._keyboard_snapshot = tuple(self._keyboard_binds)
        return b

    def bind_logical(self, expr: str, callback: Callback, *, config: Optional[BindConfig] = None, logical_config: Optional[LogicalConfig] = None, hwnd=None) -> LogicalBind:
        cfg = config or self.default_config or BindConfig()
        lcfg = logical_config or self.default_logical_config or LogicalConfig()
        b = LogicalBind(
            expr,
            callback,
            config=cfg,
            hwnd=hwnd,
            dispatch=self._dispatcher.submit,
            diagnostics=self._diagnostics,
            logical_config=lcfg,
        )
        register_bind(b, self, "logical")
        with self._lock:
            self._keyboard_binds.append(b)
            self._keyboard_snapshot = tuple(self._keyboard_binds)
        return b

    def bind_text(self, text: str, callback: Callback, *, config: Optional[BindConfig] = None, logical_config: Optional[LogicalConfig] = None, hwnd=None) -> TextAbbreviationBind:
        cfg = config or self.default_config or BindConfig()
        lcfg = logical_config or self.default_logical_config or LogicalConfig()
        b = TextAbbreviationBind(
            text,
            callback,
            config=cfg,
            hwnd=hwnd,
            dispatch=self._dispatcher.submit,
            diagnostics=self._diagnostics,
            logical_config=lcfg,
        )
        register_bind(b, self, "text")
        with self._lock:
            self._keyboard_binds.append(b)
            self._keyboard_snapshot = tuple(self._keyboard_binds)
        return b

    def add_abbreviation(self, typed: str, replacement: str, callback: Optional[Callback] = None, *, config: Optional[BindConfig] = None, logical_config: Optional[LogicalConfig] = None, hwnd=None) -> TextAbbreviationBind:
        from .logical.translate import send_backspaces, send_unicode_text
        base_cfg = (self.default_config or BindConfig()).soft_merge(BindConfig(injected=InjectedPolicy.IGNORE))
        cfg = base_cfg.hard_merge(config) if config is not None else base_cfg
        lcfg = logical_config or self.default_logical_config or LogicalConfig()

        def _noop() -> None:
            return None

        b = TextAbbreviationBind(
            typed,
            _noop,
            config=cfg,
            hwnd=hwnd,
            dispatch=self._dispatcher.submit,
            diagnostics=self._diagnostics,
            logical_config=lcfg,
        )

        def _expand(bound_bind: TextAbbreviationBind = b) -> None:
            match = bound_bind.consume_match()
            trailing_text = getattr(match, "trailing_text", "") if match is not None else ""
            matched_text = getattr(match, "matched_text", "") if match is not None else ""
            if not matched_text:
                matched_text = typed
            source_text = matched_text + trailing_text
            target_text = replacement + trailing_text
            delete_count, insert_text = _compute_text_replacement_edit(
                source_text,
                target_text,
                lcfg.replacement_policy,
            )
            with self.paused():
                send_backspaces(delete_count)
                if insert_text:
                    send_unicode_text(insert_text)
            if callback is not None:
                self._dispatcher.submit(callback)

        b.callback = _expand
        register_bind(b, self, "abbreviation")
        with self._lock:
            self._keyboard_binds.append(b)
            self._keyboard_snapshot = tuple(self._keyboard_binds)
        return b

    def bind_mouse(self, button: Union[MouseButton, str], callback: Callback, *, config: Optional[MouseBindConfig] = None, hwnd=None) -> MouseBind:
        cfg = config or self.default_mouse_config or MouseBindConfig()
        b = MouseBind(
            button,
            callback,
            config=cfg,
            hwnd=hwnd,
            dispatch=self._dispatcher.submit,
            diagnostics=self._diagnostics,
        )
        register_bind(b, self, "mouse")
        with self._lock:
            self._mouse_binds.append(b)
            self._mouse_snapshot = tuple(self._mouse_binds)
        return b

    def _unbind_single(self, bind: Any) -> bool:
        removed = False
        owner_func = owner_func_for_bind(bind)

        if isinstance(bind, MouseBind):
            with self._lock:
                try:
                    self._mouse_binds.remove(bind)
                except ValueError:
                    return False
                self._mouse_snapshot = tuple(self._mouse_binds)
                removed = True
        elif isinstance(bind, (Bind, LogicalBind, TextAbbreviationBind)):
            with self._lock:
                try:
                    self._keyboard_binds.remove(bind)
                except ValueError:
                    return False
                self._keyboard_snapshot = tuple(self._keyboard_binds)
                removed = True
        else:
            return False

        if removed:
            if owner_func is not None:
                remove_binds_from_func(owner_func, [bind])
            unregister_bind(bind)
        return removed

    def unbind(self, target: Any) -> None:
        binds = list(_iter_bind_targets(target))
        if not binds:
            if _is_bind_instance(target) and _bind_belongs_to_hook(target, self):
                self._unbind_single(target)
            return
        for bind in binds:
            if _bind_belongs_to_hook(bind, self):
                self._unbind_single(bind)

    def unbind_mouse(self, target: Any) -> None:
        binds = [b for b in _iter_bind_targets(target) if isinstance(b, MouseBind)]
        if not binds:
            if isinstance(target, MouseBind) and _bind_belongs_to_hook(target, self):
                self._unbind_single(target)
            return
        for bind in binds:
            if _bind_belongs_to_hook(bind, self):
                self._unbind_single(bind)

    def binds_for(self, func: Callback) -> List[Any]:
        return list(get_func_binds(func))

    def clear_keyboard_binds(self) -> None:
        self.unbind(list(self._keyboard_snapshot))

    def clear_mouse_binds(self) -> None:
        self.unbind_mouse(list(self._mouse_snapshot))

    def clear_logical_binds(self) -> None:
        self.unbind([b for b in self._keyboard_snapshot if kind_for_bind(b) == "logical"])

    def clear_text_binds(self) -> None:
        self.unbind([b for b in self._keyboard_snapshot if kind_for_bind(b) == "text"])

    def clear_abbreviations(self) -> None:
        self.unbind([b for b in self._keyboard_snapshot if kind_for_bind(b) == "abbreviation"])

    def _reset_runtime_states(self) -> None:
        for b in self._keyboard_snapshot:
            try:
                b.reset()
            except Exception:
                pass
        for b in self._mouse_snapshot:
            try:
                b.reset()
            except Exception:
                pass

    def pause(self) -> None:
        """Pause the hook (no callbacks will be called until resume() is called).

        Useful for temporarily disabling the hook while it's running.
        """
        with self._lock:
            self._pause_count += 1
            if self._pause_count == 1:
                self._paused = True
                self._reset_runtime_states()

    def resume(self) -> None:
        """Resume the hook (callbacks will be called again after calling pause()).

        Useful for re-enabling the hook after temporarily disabling it with pause().
        """
        with self._lock:
            if self._pause_count == 0:
                return
            self._pause_count -= 1
            if self._pause_count == 0:
                self._paused = False
                self._reset_runtime_states()

    def is_paused(self) -> bool:
        """Get whether the hook is currently paused.

        Returns True if the hook is paused, False otherwise.
        """
        with self._lock:
            return self._paused

    @contextmanager
    def paused(self) -> Generator[None, None, None]:
        """Pause and resume the hook using the with statement.

        Example:
            >>> with hook.paused():
                # do something that requires the hook to be paused
        """
        self.pause()
        try:
            yield
        finally:
            self.resume()

    def stop(self) -> None:
        """Signal to stop waiting in wait().

        After calling stop(), wait() will return True as soon as possible.
        """
        self._stop_event.set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for stop() to be called.

        If timeout is not None, wait for stop() to be called.
        Returns True if stop() was called, False otherwise.
        """
        if timeout is not None:
            return self._stop_event.wait(timeout)

        try:
            while not self._stop_event.wait(0.2):
                pass
            return True
        except KeyboardInterrupt:
            return True

    def set_default(self) -> None:
        """Alias for set_default_hook(hook)."""
        set_default_hook(self)

    def join(self) -> None:
        """Block until the hook is stopped."""
        join(self)

    def start(self) -> None:
        """Start the hook (register to the backend, start callback dispatcher)."""
        if not self.started:
            self._started = True
            _GlobalBackend.instance().register(self)
            if self._dispatcher.stopped:
                self._dispatcher.start()

    def close(self) -> None:
        if self.started:
            self._started = False
            _GlobalBackend.instance().unregister(self)
            self._dispatcher.stop()

    def get_recent_diagnostics(self, limit: Optional[int] = None) -> List[DiagnosticRecord]:
        return self._diagnostics.get_recent(limit=limit)

    def clear_diagnostics(self) -> None:
        self._diagnostics.clear()

    def get_recent_attempts(self, *, last_ms: int = 1500) -> List["InputAttempt"]:
        from .diagnostics.analysis import collect_attempts
        return collect_attempts(self.get_recent_diagnostics(), last_ms=last_ms, bind_meta=self._diagnostics.get_bind_metadata())

    def explain(self, bind_or_expr, *, last_ms: int = 1500, select: "ExplainSelect" = "best") -> "ExplainReport":
        from .diagnostics.analysis import explain_records
        bind_name = getattr(bind_or_expr, "expr", None)
        if bind_name is None:
            btn = getattr(bind_or_expr, "button", None)
            if btn is not None:
                bind_name = getattr(btn, "name", str(btn)).lower()
        if bind_name is None:
            bind_name = str(bind_or_expr)
        return explain_records(bind_name, self.get_recent_diagnostics(), last_ms=last_ms, bind_meta=self._diagnostics.get_bind_metadata(), select=select)

    def explain_mouse(self, button: Union[MouseButton, str], *, last_ms: int = 1500, select: "ExplainSelect" = "best") -> "ExplainReport":
        from .diagnostics.analysis import explain_records
        normalized = _normalize_mouse_button(button)
        bind_name = normalized.name.lower()
        return explain_records(bind_name, self.get_recent_diagnostics(), last_ms=last_ms, bind_meta=self._diagnostics.get_bind_metadata(), select=select, device="mouse")

    # -------------------------
    # called by backend
    # -------------------------

    def _handle_keyboard_event(self, event, state) -> int:
        event_id = self._diagnostics.prepare_event(event, "keyboard")
        with self._lock:
            if self._paused:
                self._diagnostics.emit(kind="decision", reason="hook_paused", device="keyboard", event_id=event_id)
                return 0

        snap = self._keyboard_snapshot
        if not snap:
            return 0  # winput.WP_CONTINUE (backend ORs anyway)
        flags = 0
        for b in snap:
            flags |= b.handle(event, state)
        return flags

    def _handle_mouse_event(self, event, state) -> int:
        event_id = self._diagnostics.prepare_event(event, "mouse")
        with self._lock:
            if self._paused:
                self._diagnostics.emit(kind="decision", reason="hook_paused", device="mouse", event_id=event_id)
                return 0

        snap = self._mouse_snapshot
        if not snap:
            return 0
        flags = 0
        for b in snap:
            flags |= b.handle(event, state)
        return flags
