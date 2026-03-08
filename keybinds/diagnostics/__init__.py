from importlib import import_module
from typing import TYPE_CHECKING

from .core import (
    DiagnosticRecord,
    DiagnosticsConfig,
    MemorySink,
    NamedCheck,
    BindMetadata,
    named_check,
    ExplainSelect,
    ExplainVerbosity,
)
from .tracing import (
    _BoundDiagnostics,
    _DispatchTrace,
    _DiagnosticsManager,
    _EventTrace,
    _NULL_BOUND_DIAGNOSTICS,
    _NULL_DISPATCH_TRACE,
    _NULL_EVENT_TRACE,
    build_bind_metadata,
    create_diagnostics_manager,
)

if TYPE_CHECKING:
    from .reporting import (
        CheckDecision,
        DispatchOutcome,
        BindDecision,
        InputAttempt,
        ExplainReport,
    )
    from .analysis import (
        collect_attempts,
        explain_records,
        render_explain_report,
    )

__all__ = [
    'DiagnosticRecord', 'DiagnosticsConfig', 'MemorySink', 'NamedCheck', 'BindMetadata', 'named_check',
    'ExplainSelect', 'ExplainVerbosity',
    '_BoundDiagnostics', '_DispatchTrace', '_DiagnosticsManager', '_EventTrace',
    '_NULL_BOUND_DIAGNOSTICS', '_NULL_DISPATCH_TRACE', '_NULL_EVENT_TRACE',
    'build_bind_metadata', 'create_diagnostics_manager',
    'CheckDecision', 'DispatchOutcome', 'BindDecision', 'InputAttempt', 'ExplainReport',
    'collect_attempts', 'explain_records', 'render_explain_report',
]

_LAZY_REPORTING = {'CheckDecision', 'DispatchOutcome', 'BindDecision', 'InputAttempt', 'ExplainReport'}
_LAZY_ANALYSIS = {'collect_attempts', 'explain_records', 'render_explain_report'}


def __getattr__(name):
    if name in _LAZY_REPORTING:
        mod = import_module('.reporting', __name__)
        return getattr(mod, name)
    if name in _LAZY_ANALYSIS:
        mod = import_module('.analysis', __name__)
        return getattr(mod, name)
    raise AttributeError(name)


def __dir__():
    return sorted(__all__)
