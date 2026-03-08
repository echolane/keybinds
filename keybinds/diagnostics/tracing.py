
from __future__ import annotations

import time
from itertools import count
from typing import Any, Dict, List, Optional, cast

try:
    from typing import Protocol  # type: ignore
except ImportError:
    from typing_extensions import Protocol

from .core import BindMetadata, DiagnosticRecord, DiagnosticsConfig, MemorySink, _LEVELS


class _DispatchTrace(Protocol):
    @property
    def dispatch_id(self) -> Optional[int]: ...

    def note(self, kind: str, reason: str, **details: Any) -> None: ...
    def queued(self) -> None: ...
    def started(self) -> None: ...
    def finished(self) -> None: ...
    def returned_awaitable(self) -> None: ...
    def async_scheduled(self) -> None: ...
    def async_finished(self) -> None: ...
    def error(self, exc: BaseException) -> None: ...
    def async_error(self, exc: BaseException) -> None: ...


class _EventTrace(Protocol):
    @property
    def event_id(self) -> Optional[int]: ...

    def note(self, kind: str, reason: str, **details: Any) -> None: ...
    def skip(self, reason: str, **details: Any) -> None: ...
    def suppress(self, reason: str, **details: Any) -> None: ...
    def match(self, reason: str, **details: Any) -> None: ...
    def fire(self, trigger: Optional[str] = None, **details: Any) -> _DispatchTrace: ...


class _BoundDiagnostics(Protocol):
    def start(self, event: Any) -> _EventTrace: ...


class _NullDispatchTrace:
    __slots__ = ()

    @property
    def dispatch_id(self) -> Optional[int]:
        return None

    def note(self, kind: str, reason: str, **details: Any) -> None:
        return None

    def queued(self) -> None:
        return None

    def started(self) -> None:
        return None

    def finished(self) -> None:
        return None

    def returned_awaitable(self) -> None:
        return None

    def async_scheduled(self) -> None:
        return None

    def async_finished(self) -> None:
        return None

    def error(self, exc: BaseException) -> None:
        return None

    def async_error(self, exc: BaseException) -> None:
        return None


class _NullEventTrace:
    __slots__ = ()

    @property
    def event_id(self) -> Optional[int]:
        return None

    def note(self, kind: str, reason: str, **details: Any) -> None:
        return None

    def skip(self, reason: str, **details: Any) -> None:
        return None

    def suppress(self, reason: str, **details: Any) -> None:
        return None

    def match(self, reason: str, **details: Any) -> None:
        return None

    def fire(self, trigger: Optional[str] = None, **details: Any) -> _DispatchTrace:
        return _NULL_DISPATCH_TRACE


class _NullBoundDiagnostics:
    __slots__ = ()

    def start(self, event: Any) -> _EventTrace:
        return _NULL_EVENT_TRACE


_NULL_DISPATCH_TRACE: _DispatchTrace = _NullDispatchTrace()
_NULL_EVENT_TRACE: _EventTrace = _NullEventTrace()
_NULL_BOUND_DIAGNOSTICS: _BoundDiagnostics = _NullBoundDiagnostics()


class _DiagnosticsManager:
    def __init__(self, config: Optional[DiagnosticsConfig] = None) -> None:
        cfg = config or DiagnosticsConfig()
        level_name = cfg.normalized_level()
        self._level_name = level_name
        self._level = _LEVELS[level_name]
        self._enabled = self._level > 0
        self._sink = cfg.sink or MemorySink(cfg.ring_size)
        self._event_seq = count(1)
        self._dispatch_seq = count(1)
        self._record_seq = count(1)
        self._manager_key = f"mgr_{id(self)}"
        self._bind_meta: Dict[str, BindMetadata] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def sink(self) -> Any:
        return self._sink

    def bind(self, bind_name: str, device: str, metadata: Optional[BindMetadata] = None) -> _BoundDiagnostics:
        if metadata is not None:
            self._bind_meta[bind_name] = metadata
        if not self._enabled:
            return _NULL_BOUND_DIAGNOSTICS
        return _BoundDiagnosticsImpl(self, bind_name=bind_name, device=device)

    def get_bind_metadata(self) -> Dict[str, BindMetadata]:
        return dict(self._bind_meta)

    def get_recent(self, limit: Optional[int] = None) -> List[DiagnosticRecord]:
        getter = getattr(self._sink, 'get_recent', None)
        if callable(getter):
            records = getter(limit=limit)
            if isinstance(records, list):
                return cast(List[DiagnosticRecord], records)
        return []

    def clear(self) -> None:
        clearer = getattr(self._sink, 'clear', None)
        if callable(clearer):
            clearer()

    def prepare_event(self, event: Any, device: str) -> Optional[int]:
        if not self._enabled:
            return None
        ids = getattr(event, '_kb_diag_event_ids', None)
        if not isinstance(ids, dict):
            ids = {}
            try:
                setattr(event, '_kb_diag_event_ids', ids)
            except Exception:
                ids = {}
        event_id = ids.get(self._manager_key)
        if event_id is None:
            event_id = self._next_event_id()
            ids[self._manager_key] = event_id
        emitted = getattr(event, '_kb_diag_raw_emitted', None)
        if not isinstance(emitted, set):
            emitted = set()
            try:
                setattr(event, '_kb_diag_raw_emitted', emitted)
            except Exception:
                emitted = set()
        if self._manager_key not in emitted:
            details: Dict[str, Any] = {
                'action': _safe_int(getattr(event, 'action', None)),
                'injected': bool(getattr(event, 'injected', False)),
                'time': _safe_int(getattr(event, 'time', 0) or 0),
            }
            vk = getattr(event, 'vkCode', None)
            if vk is not None:
                details['vk'] = _safe_int(vk)
            extra = getattr(event, 'additional_data', None)
            if extra is not None:
                details['additional_data'] = extra
            self.emit(kind='raw', reason='input_event', bind=None, device=device, event_id=event_id, details=details)
            emitted.add(self._manager_key)
        return event_id

    def emit(
        self,
        *,
        kind: str,
        reason: str,
        bind: Optional[str] = None,
        device: Optional[str] = None,
        trigger: Optional[str] = None,
        event_id: Optional[int] = None,
        dispatch_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._enabled:
            return
        details = details or {}
        if kind == 'raw' and self._level < 3:
            return
        if kind == 'error':
            if self._level < 1:
                return
        elif self._level < 2:
            return
        record = DiagnosticRecord(
            ts_ns=time.time_ns(),
            seq=next(self._record_seq),
            kind=kind,
            reason=reason,
            bind=bind,
            device=device,
            trigger=trigger,
            event_id=event_id,
            dispatch_id=dispatch_id,
            details=details,
        )
        try:
            self._sink.emit(record)
        except Exception:
            pass

    def _next_event_id(self) -> int:
        return next(self._event_seq)

    def _next_dispatch_id(self) -> int:
        return next(self._dispatch_seq)


class _BoundDiagnosticsImpl:
    __slots__ = ('_mgr', 'bind_name', 'device')

    def __init__(self, mgr: _DiagnosticsManager, *, bind_name: str, device: str) -> None:
        self._mgr = mgr
        self.bind_name = bind_name
        self.device = device

    def start(self, event: Any) -> _EventTrace:
        event_id = self._mgr.prepare_event(event, self.device)
        if event_id is None:
            return _NULL_EVENT_TRACE
        return _EventTraceImpl(self._mgr, bind_name=self.bind_name, device=self.device, event_id=event_id)


class _EventTraceImpl:
    __slots__ = ('_mgr', 'bind_name', 'device', '_event_id')

    def __init__(self, mgr: _DiagnosticsManager, *, bind_name: str, device: str, event_id: int) -> None:
        self._mgr = mgr
        self.bind_name = bind_name
        self.device = device
        self._event_id = event_id

    @property
    def event_id(self) -> Optional[int]:
        return self._event_id

    def note(self, kind: str, reason: str, **details: Any) -> None:
        self._mgr.emit(kind=kind, reason=reason, bind=self.bind_name, device=self.device, event_id=self.event_id, details=details)

    def skip(self, reason: str, **details: Any) -> None:
        self.note('skip', reason, **details)

    def suppress(self, reason: str, **details: Any) -> None:
        self.note('suppress', reason, **details)

    def match(self, reason: str, **details: Any) -> None:
        self.note('match', reason, **details)

    def fire(self, trigger: Optional[str] = None, **details: Any) -> _DispatchTrace:
        dispatch_id = self._mgr._next_dispatch_id()
        self._mgr.emit(
            kind='fire',
            reason='bind_fired',
            bind=self.bind_name,
            device=self.device,
            trigger=trigger,
            event_id=self.event_id,
            dispatch_id=dispatch_id,
            details=details,
        )
        return _DispatchTraceImpl(
            self._mgr,
            bind_name=self.bind_name,
            device=self.device,
            trigger=trigger,
            event_id=self.event_id,
            dispatch_id=dispatch_id,
        )


class _DispatchTraceImpl:
    __slots__ = ('_mgr', 'bind_name', 'device', 'trigger', '_event_id', '_dispatch_id')

    def __init__(self, mgr: _DiagnosticsManager, *, bind_name: str, device: str, trigger: Optional[str], event_id: Optional[int], dispatch_id: int) -> None:
        self._mgr = mgr
        self.bind_name = bind_name
        self.device = device
        self.trigger = trigger
        self._event_id = event_id
        self._dispatch_id = dispatch_id

    @property
    def event_id(self) -> Optional[int]:
        return self._event_id

    @property
    def dispatch_id(self) -> Optional[int]:
        return self._dispatch_id

    def note(self, kind: str, reason: str, **details: Any) -> None:
        self._mgr.emit(
            kind=kind,
            reason=reason,
            bind=self.bind_name,
            device=self.device,
            trigger=self.trigger,
            event_id=self.event_id,
            dispatch_id=self.dispatch_id,
            details=details,
        )

    def queued(self) -> None:
        self.note('dispatch', 'callback_queued')

    def started(self) -> None:
        self.note('dispatch', 'callback_started')

    def finished(self) -> None:
        self.note('dispatch', 'callback_finished')

    def returned_awaitable(self) -> None:
        self.note('dispatch', 'callback_returned_awaitable')

    def async_scheduled(self) -> None:
        self.note('dispatch', 'async_scheduled')

    def async_finished(self) -> None:
        self.note('dispatch', 'async_finished')

    def error(self, exc: BaseException) -> None:
        self.note('error', 'callback_error', error_type=type(exc).__name__, error=str(exc))

    def async_error(self, exc: BaseException) -> None:
        self.note('error', 'async_error', error_type=type(exc).__name__, error=str(exc))


def create_diagnostics_manager(config: Optional[DiagnosticsConfig] = None) -> _DiagnosticsManager:
    return _DiagnosticsManager(config)


def build_bind_metadata(bind_name: str, device: str, config: Any) -> BindMetadata:
    trigger = _enum_name(getattr(config, 'trigger', None))
    suppress = _enum_name(getattr(config, 'suppress', None))
    injected = _enum_name(getattr(config, 'injected', None))
    constraints = getattr(config, 'constraints', None)
    timing = getattr(config, 'timing', None)
    return BindMetadata(
        bind=bind_name,
        device=device,
        trigger=trigger,
        suppress=suppress,
        injected=injected,
        chord_policy=_enum_name(getattr(constraints, 'chord_policy', None)),
        order_policy=_enum_name(getattr(constraints, 'order_policy', None)),
        hold_ms=_safe_int(getattr(timing, 'hold_ms', None)),
        repeat_delay_ms=_safe_int(getattr(timing, 'repeat_delay_ms', None)),
        repeat_interval_ms=_safe_int(getattr(timing, 'repeat_interval_ms', None)),
        double_tap_window_ms=_safe_int(getattr(timing, 'double_tap_window_ms', None)),
        is_sequence=',' in bind_name,
    )


def _enum_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    name = getattr(value, 'name', None)
    if isinstance(name, str) and name:
        return name.lower()
    return str(value).lower()


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None
