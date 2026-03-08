from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .core import DiagnosticRecord, BindMetadata, ExplainVerbosity


@dataclass(frozen=True)
class CheckDecision:
    name: str
    passed: bool
    raised: bool = False
    error_type: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class DispatchOutcome:
    queued: bool = False
    started: bool = False
    finished: bool = False
    returned_awaitable: bool = False
    async_scheduled: bool = False
    async_finished: bool = False
    callback_error: Optional[str] = None
    async_error: Optional[str] = None
    callback_error_type: Optional[str] = None
    async_error_type: Optional[str] = None

    @property
    def entered(self) -> bool:
        return self.queued or self.started or self.finished or self.returned_awaitable or self.async_scheduled


@dataclass(frozen=True)
class BindDecision:
    bind: str
    device: Optional[str]
    trigger: Optional[str]
    records: List[DiagnosticRecord]
    checks: List[CheckDecision]
    dispatch: DispatchOutcome
    scope_ok: Optional[bool]
    injected_ok: Optional[bool]
    fired: bool
    suppressed: bool
    suppression_reasons: List[str]
    terminal_stage: str
    terminal_reason: str
    terminal_details: Dict[str, Any] = field(default_factory=dict)
    trigger_details: Dict[str, Any] = field(default_factory=dict)
    metadata: Optional[BindMetadata] = None

    @property
    def callback_reached(self) -> bool:
        return self.fired or self.dispatch.entered


@dataclass(frozen=True)
class InputAttempt:
    event_id: int
    device: Optional[str]
    ts_ns: int
    raw: Optional[DiagnosticRecord]
    candidates: List[BindDecision]

    def render_text(self) -> str:
        lines = [
            f"Attempt #{self.event_id}",
            f"Device: {self.device or 'unknown'}",
        ]
        if self.raw is not None:
            raw = self.raw.details
            action = raw.get('action')
            vk = raw.get('vk')
            injected = raw.get('injected')
            desc = []
            if action is not None:
                desc.append(f"action={action}")
            if vk is not None:
                desc.append(f"vk={vk}")
            if injected is not None:
                desc.append(f"injected={bool(injected)}")
            if desc:
                lines.append(f"Input: {', '.join(desc)}")
        lines.append("Candidates:")
        for cand in self.candidates:
            lines.append(f"- {cand.bind}: {cand.terminal_reason.replace('_', ' ')}")
        return "\n".join(lines)


@dataclass(frozen=True)
class ExplainReport:
    bind: str
    attempt: Optional[InputAttempt]
    decision: Optional[BindDecision]

    def render_text(self, *, verbosity: ExplainVerbosity = "normal") -> str:
        from .analysis import render_explain_report
        return render_explain_report(self, verbosity=verbosity)
