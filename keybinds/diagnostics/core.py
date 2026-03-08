from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional

try:
    from typing import Literal
except ImportError:  # pragma: no cover - Python 3.7 fallback
    class _LiteralShim(object):
        def __getitem__(self, item):
            return object

    Literal = _LiteralShim()

ExplainSelect = Literal["best", "last", "last_fired", "last_failed"]
ExplainVerbosity = Literal["short", "normal", "detailed"]

_LEVELS = {
    "off": 0,
    "errors": 1,
    "decisions": 2,
    "trace": 3,
}


@dataclass(frozen=True)
class DiagnosticRecord:
    """Structured diagnostic record emitted by the matching/dispatch pipeline."""

    ts_ns: int
    seq: int
    kind: str
    reason: str
    bind: Optional[str] = None
    device: Optional[str] = None
    trigger: Optional[str] = None
    event_id: Optional[int] = None
    dispatch_id: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiagnosticsConfig:
    """Configuration for diagnostics.

    level:
        - "off": disable diagnostics completely
        - "errors": callback/async/internal errors only
        - "decisions": matching and dispatch decisions
        - "trace": includes raw input events too
    """

    enabled: bool = False
    level: str = "off"
    ring_size: int = 1000
    sink: Optional[Any] = None

    def normalized_level(self) -> str:
        lvl = str(self.level).strip().lower()
        if lvl not in _LEVELS:
            raise ValueError("diagnostics level must be one of: off, errors, decisions, trace")
        if not self.enabled:
            return "off"
        return lvl


class MemorySink:
    """Thread-safe in-memory diagnostic sink backed by a ring buffer."""

    def __init__(self, maxlen: int = 1000) -> None:
        maxlen = max(1, int(maxlen))
        self._buf: Deque[DiagnosticRecord] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def emit(self, record: DiagnosticRecord) -> None:
        with self._lock:
            self._buf.append(record)

    def get_recent(self, limit: Optional[int] = None) -> List[DiagnosticRecord]:
        with self._lock:
            items = list(self._buf)
        if limit is None:
            return items
        return items[-max(0, int(limit)):]

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()


@dataclass(frozen=True)
class NamedCheck:
    name: str
    predicate: Callable[[Any, Any], bool]

    def __call__(self, event: Any, state: Any) -> bool:
        return self.predicate(event, state)


@dataclass(frozen=True)
class BindMetadata:
    bind: str
    device: str
    trigger: Optional[str] = None
    suppress: Optional[str] = None
    injected: Optional[str] = None
    chord_policy: Optional[str] = None
    order_policy: Optional[str] = None
    hold_ms: Optional[int] = None
    repeat_delay_ms: Optional[int] = None
    repeat_interval_ms: Optional[int] = None
    double_tap_window_ms: Optional[int] = None
    is_sequence: bool = False


def named_check(name: str, predicate: Callable[[Any, Any], bool]) -> NamedCheck:
    if not name or not isinstance(name, str):
        raise TypeError("name must be a non-empty string")
    if not callable(predicate):
        raise TypeError("predicate must be callable")
    return NamedCheck(name=name.strip(), predicate=predicate)
