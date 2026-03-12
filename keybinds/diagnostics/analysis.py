
from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .core import BindMetadata, DiagnosticRecord, ExplainSelect, ExplainVerbosity
from .reporting import BindDecision, CheckDecision, DispatchOutcome, ExplainReport, InputAttempt


def collect_attempts(
    records: Iterable[DiagnosticRecord],
    *,
    last_ms: int = 1500,
    bind_meta: Optional[Dict[str, BindMetadata]] = None,
) -> List[InputAttempt]:
    now_ns = time.time_ns()
    cutoff_ns = now_ns - max(0, int(last_ms)) * 1_000_000
    filtered = [r for r in records if r.event_id is not None and r.ts_ns >= cutoff_ns]
    by_event: Dict[int, List[DiagnosticRecord]] = {}
    for rec in filtered:
        event_id = rec.event_id
        if event_id is None:
            continue
        by_event.setdefault(event_id, []).append(rec)

    attempts: List[InputAttempt] = []
    for event_id, group in sorted(by_event.items()):
        group.sort(key=lambda r: r.seq)
        raw = next((r for r in group if r.kind == 'raw'), None)
        by_bind: Dict[str, List[DiagnosticRecord]] = {}
        for rec in group:
            if rec.bind:
                by_bind.setdefault(rec.bind, []).append(rec)
        candidates: List[BindDecision] = []
        for bind, recs in sorted(by_bind.items(), key=lambda item: item[1][0].seq):
            decision = _build_bind_decision(bind, recs, metadata=(bind_meta or {}).get(bind))
            if _is_relevant_candidate(decision, raw):
                candidates.append(decision)
        if not candidates:
            continue
        attempts.append(
            InputAttempt(
                event_id=event_id,
                device=(raw.device if raw is not None else (group[0].device if group else None)),
                ts_ns=group[-1].ts_ns,
                raw=raw,
                candidates=candidates,
            )
        )
    attempts.sort(key=lambda a: (a.ts_ns, a.event_id))
    return attempts


def explain_records(
    bind_name: str,
    records: Iterable[DiagnosticRecord],
    *,
    last_ms: int = 1500,
    bind_meta: Optional[Dict[str, BindMetadata]] = None,
    select: ExplainSelect = "best",
    device: Optional[str] = None,
) -> ExplainReport:
    attempts = collect_attempts(records, last_ms=last_ms, bind_meta=bind_meta)
    chosen_attempt: Optional[InputAttempt] = None
    chosen_decision: Optional[BindDecision] = None
    chosen_score: Optional[Tuple[int, int, int]] = None

    for attempt in attempts:
        for candidate in attempt.candidates:
            if candidate.bind != bind_name:
                continue
            if device is not None and candidate.device != device:
                continue
            score = _attempt_score(candidate, attempt, select=select)
            if score is None:
                continue
            if chosen_score is None or score > chosen_score:
                chosen_attempt = attempt
                chosen_decision = candidate
                chosen_score = score

    return ExplainReport(bind=bind_name, attempt=chosen_attempt, decision=chosen_decision)



def _attempt_score(candidate: BindDecision, attempt: InputAttempt, *, select: ExplainSelect) -> Optional[Tuple[int, int, int]]:
    if select == "last":
        return (0, attempt.ts_ns, attempt.event_id)
    if select == "last_fired":
        if not (candidate.fired or candidate.dispatch.finished or candidate.dispatch.async_finished):
            return None
        return (0, attempt.ts_ns, attempt.event_id)
    if select == "last_failed":
        if _success_rank(candidate) > 0 or _intermediate_rank(candidate) > 0:
            return None
        return (0, attempt.ts_ns, attempt.event_id)

    return (_meaningful_rank(candidate), attempt.ts_ns, attempt.event_id)


def _meaningful_rank(candidate: BindDecision) -> int:
    success = _success_rank(candidate)
    if success:
        return success
    failure = _failure_rank(candidate)
    if failure:
        return failure
    intermediate = _intermediate_rank(candidate)
    if intermediate:
        return intermediate
    return 1


def _success_rank(candidate: BindDecision) -> int:
    if candidate.dispatch.async_error:
        return 100
    if candidate.dispatch.callback_error:
        return 99
    if candidate.dispatch.async_finished:
        return 96
    if candidate.dispatch.finished:
        return 95
    if candidate.fired:
        return 90
    return 0


def _failure_rank(candidate: BindDecision) -> int:
    reason = candidate.terminal_reason
    if reason in ("check_raised", "check_failed", "window_mismatch", "injected_ignored", "injected_only_but_physical"):
        return 80
    if reason in ("sequence_timeout", "sequence_reset_foreign_key", "strict_order_invalid", "strict_order_attempt_invalid", "cooldown_active", "max_fires_reached", "hold_not_long_enough", "hold_timer_cancelled", "repeat_cancelled", "button_mismatch"):
        return 70
    if reason.startswith("suppressed_"):
        return 65
    if reason == "trigger_not_satisfied":
        return 60
    return 0


def _intermediate_rank(candidate: BindDecision) -> int:
    reason = candidate.terminal_reason
    if reason in ("sequence_waiting_for_next_step", "waiting_for_release", "waiting_for_full_release", "click_waiting_for_release", "hold_waiting_or_cancelled", "repeat_waiting_for_first_tick", "repeat_active", "double_tap_waiting_for_second_tap"):
        return 20
    if reason in ("chord_not_complete", "release_not_armed", "chord_was_not_fully_pressed", "hold_not_started", "repeat_not_started", "click_not_started", "double_tap_not_started", "event_seen_but_bind_not_ready"):
        return 10
    return 0


def _is_relevant_candidate(candidate: BindDecision, raw: Optional[DiagnosticRecord]) -> bool:
    if _success_rank(candidate) > 0 or _failure_rank(candidate) > 0:
        return True

    reason = candidate.terminal_reason
    details = candidate.trigger_details
    raw_details = raw.details if raw is not None else {}
    raw_vk = raw_details.get('vk')
    raw_button = raw_details.get('button')

    if reason == 'sequence_waiting_for_next_step':
        steps = int(details.get('steps_matched', details.get('seq_index', 0)) or 0)
        return steps > 0
    if reason in ('hold_waiting_or_cancelled', 'repeat_waiting_for_first_tick', 'repeat_active', 'double_tap_waiting_for_second_tap', 'click_waiting_for_release', 'waiting_for_release', 'waiting_for_full_release'):
        return True
    if reason == 'chord_not_complete':
        return bool(details.get('any_chord_key_pressed') or details.get('full') or details.get('chord_full'))
    if reason == 'event_seen_but_bind_not_ready':
        return bool(details.get('any_chord_key_pressed') or details.get('seq_index') or details.get('hold_timer_started') or details.get('repeat_started') or details.get('tap_count'))
    if reason in ('hold_not_started', 'repeat_not_started', 'click_not_started', 'double_tap_not_started', 'release_not_armed', 'chord_was_not_fully_pressed'):
        if raw_button is not None:
            button_name = str(raw_button).lower()
            return candidate.bind.lower() == button_name or candidate.bind.lower().endswith(button_name)
        if raw_vk is not None:
            text = candidate.bind.lower()
            return str(raw_vk) in text or bool(details.get('any_chord_key_pressed') or details.get('seq_index'))
        return False
    return _intermediate_rank(candidate) > 0

def render_explain_report(report: ExplainReport, *, verbosity: ExplainVerbosity = "normal") -> str:
    attempt = report.attempt
    decision = report.decision
    if attempt is None or decision is None:
        return (
            f"Bind: {report.bind}\n"
            "Result: no meaningful attempts found\n"
            "Primary reason: this bind did not become a real candidate in the selected time window"
        )

    trigger = decision.trigger or (decision.metadata.trigger if decision.metadata is not None else None) or 'unknown'
    stage = _stage_text(decision.terminal_stage)
    result = _result_text(decision)
    reason = _reason_text(decision.terminal_reason, decision.terminal_details, decision.metadata)

    lines = [
        f"Bind: {report.bind}",
        f"Result: {result}",
        f"Stopped at: {stage}",
        f"Primary reason: {reason}",
    ]

    if verbosity == "short":
        return "\n".join(lines)

    lines.extend([
        "",
        "Details:",
        f"- Attempt: #{attempt.event_id}",
        f"- Trigger: {trigger}",
    ])

    detail_lines = _detail_lines(decision, verbosity=verbosity)
    for detail in detail_lines:
        lines.append(f"- {detail}")

    if verbosity == "detailed":
        candidate_lines = _other_candidate_lines(attempt, decision)
        if candidate_lines:
            lines.extend(["", "Other relevant candidates:"])
            lines.extend(candidate_lines)

    return "\n".join(lines)


def _detail_lines(decision: BindDecision, *, verbosity: ExplainVerbosity) -> List[str]:
    lines: List[str] = []
    lines.extend(_primary_detail_lines(decision))

    trigger_lines = _trigger_lines(decision)
    if verbosity == "normal":
        trigger_lines = trigger_lines[:2]
    for line in trigger_lines:
        if line not in lines:
            lines.append(line)

    dispatch_line = f"Dispatch: {_dispatch_text(decision.dispatch)}"
    if dispatch_line not in lines:
        lines.append(dispatch_line)

    if verbosity == "detailed":
        raw_detail_lines = _raw_input_lines(decision)
        for line in raw_detail_lines:
            if line not in lines:
                lines.append(line)

    return lines


def _primary_detail_lines(decision: BindDecision) -> List[str]:
    reason = decision.terminal_reason
    details = decision.terminal_details
    out: List[str] = []

    if decision.scope_ok is False:
        out.append('Window scope: did not match')
    elif decision.scope_ok is True:
        out.append('Window scope: passed')

    if decision.injected_ok is False:
        out.append('Injected policy: rejected event')
    elif decision.injected_ok is True:
        out.append('Injected policy: passed')

    if decision.checks:
        failed_or_raised = [chk for chk in decision.checks if (not chk.passed) or chk.raised]
        if failed_or_raised:
            chk = failed_or_raised[0]
            if chk.raised:
                extra = f" ({chk.error_type or 'Exception'}: {chk.error})" if chk.error else f" ({chk.error_type or 'Exception'})"
                out.append(f"Check: {chk.name} raised{extra}")
            else:
                out.append(f"Check: {chk.name} failed")
        else:
            out.append('Checks: all passed')
    else:
        out.append('Checks: none')

    if reason == 'sequence_reset_foreign_key':
        vk = details.get('vk')
        if vk is not None:
            out.append(f"Interrupting key: vk={vk}")
    elif reason == 'sequence_timeout':
        expected = details.get('expected_next')
        if expected is not None:
            out.append(f"Expected next step: {expected}")
    elif reason == 'hold_not_long_enough':
        req = details.get('hold_ms') or (decision.metadata.hold_ms if decision.metadata is not None else None)
        actual = details.get('duration_ms')
        if req is not None:
            out.append(f"Required hold time: {req} ms")
        if actual is not None:
            out.append(f"Actual hold time: {actual} ms")
    elif reason == 'hold_timer_cancelled':
        req = details.get('hold_ms') or (decision.metadata.hold_ms if decision.metadata is not None else None)
        actual = details.get('duration_ms')
        if req is not None:
            out.append(f"Required hold time: {req} ms")
        if actual is not None:
            out.append(f"Actual hold time: {actual} ms")
    elif reason in ('repeat_not_started', 'repeat_waiting_for_first_tick', 'repeat_active', 'repeat_cancelled'):
        delay = details.get('repeat_delay_ms') or (decision.metadata.repeat_delay_ms if decision.metadata is not None else None)
        if delay is not None:
            out.append(f"Repeat delay: {delay} ms")
        ticks = decision.trigger_details.get('repeat_ticks')
        if ticks:
            out.append(f"Repeat ticks fired: {ticks}")
    elif reason in ('double_tap_waiting_for_second_tap', 'double_tap_not_started'):
        window_ms = details.get('double_tap_window_ms') or (decision.metadata.double_tap_window_ms if decision.metadata is not None else None)
        if window_ms is not None:
            out.append(f"Double-tap window: {window_ms} ms")
    elif reason in ('chord_not_complete', 'release_not_armed', 'chord_was_not_fully_pressed', 'waiting_for_release', 'waiting_for_full_release', 'bind_fired', 'callback_finished', 'callback_error', 'async_finished', 'async_error'):
        full = decision.trigger_details.get('full')
        if full is not None:
            out.append(f"Chord matched: {'yes' if bool(full) else 'no'}")

    if decision.suppression_reasons:
        out.append(f"Suppression: {_reason_text(decision.suppression_reasons[0], decision.terminal_details, decision.metadata)}")
    else:
        out.append('Suppression: none')

    return out


def _other_candidate_lines(attempt: InputAttempt, decision: BindDecision) -> List[str]:
    lines: List[str] = []
    others = [cand for cand in attempt.candidates if cand.bind != decision.bind]
    if not others:
        return lines
    ranked = sorted(others, key=lambda cand: (_meaningful_rank(cand), cand.bind), reverse=True)
    for cand in ranked[:3]:
        lines.append(f"- {cand.bind}: {_candidate_summary(cand)}")
    return lines


def _raw_input_lines(decision: BindDecision) -> List[str]:
    for rec in decision.records:
        if rec.kind == 'raw':
            details = rec.details
            parts: List[str] = []
            if details.get('action') is not None:
                parts.append(f"action={details['action']}")
            if details.get('vk') is not None:
                parts.append(f"vk={details['vk']}")
            if details.get('button') is not None:
                parts.append(f"button={details['button']}")
            if 'injected' in details:
                parts.append(f"injected={bool(details['injected'])}")
            if parts:
                return [f"Input: {', '.join(parts)}"]
    return []


def _stage_text(stage: str) -> str:
    mapping = {
        'scope': 'scope',
        'policy': 'policy',
        'checks': 'checks',
        'constraints': 'constraints',
        'trigger': 'trigger',
        'match': 'match',
        'dispatch': 'dispatch',
        'async': 'dispatch',
        'suppression': 'suppression',
        'unknown': 'unknown',
    }
    return mapping.get(stage, stage)


def _build_bind_decision(bind_name: str, records: Sequence[DiagnosticRecord], metadata: Optional[BindMetadata] = None) -> BindDecision:
    sorted_records = sorted(records, key=lambda r: r.seq)
    checks: List[CheckDecision] = []
    suppression_reasons: List[str] = []
    scope_ok: Optional[bool] = None
    injected_ok: Optional[bool] = None
    fired = False
    suppressed = False
    dispatch = DispatchOutcome()
    trigger = metadata.trigger if metadata is not None else None
    trigger_details: Dict[str, Any] = {}

    terminal_stage = 'unknown'
    terminal_reason = 'no_terminal_reason'
    terminal_details: Dict[str, Any] = {}

    for rec in sorted_records:
        reason = rec.reason
        details = rec.details
        if rec.trigger:
            trigger = rec.trigger
        if reason == 'window_mismatch':
            scope_ok = False
        elif scope_ok is None and reason in ('focus_restored',):
            scope_ok = True
        elif reason.startswith('injected_'):
            injected_ok = reason not in ('injected_ignored', 'injected_only_but_physical')
        elif reason == 'check_passed':
            checks.append(CheckDecision(name=str(details.get('check', '<check>')), passed=True))
        elif reason == 'check_failed':
            checks.append(CheckDecision(name=str(details.get('check', '<check>')), passed=False))
        elif reason == 'check_raised':
            checks.append(CheckDecision(name=str(details.get('check', '<check>')), passed=False, raised=True, error_type=_string_or_none(details.get('error_type')), error=_string_or_none(details.get('error'))))
        elif rec.kind == 'suppress':
            suppressed = True
            suppression_reasons.append(reason)
        elif rec.kind == 'fire':
            fired = True
            terminal_stage = 'match'
            terminal_reason = reason
            terminal_details = dict(details)
        elif rec.kind == 'dispatch':
            if reason == 'callback_queued':
                dispatch = _replace_dispatch(dispatch, queued=True)
            elif reason == 'callback_started':
                dispatch = _replace_dispatch(dispatch, started=True)
            elif reason == 'callback_finished':
                dispatch = _replace_dispatch(dispatch, finished=True)
                terminal_stage = 'dispatch'
                terminal_reason = reason
                terminal_details = dict(details)
            elif reason == 'callback_returned_awaitable':
                dispatch = _replace_dispatch(dispatch, returned_awaitable=True)
            elif reason == 'async_scheduled':
                dispatch = _replace_dispatch(dispatch, async_scheduled=True)
            elif reason == 'async_finished':
                dispatch = _replace_dispatch(dispatch, async_finished=True)
                terminal_stage = 'async'
                terminal_reason = reason
                terminal_details = dict(details)
        elif rec.kind == 'error':
            if reason == 'callback_error':
                dispatch = _replace_dispatch(dispatch, callback_error=_string_or_none(details.get('error')), callback_error_type=_string_or_none(details.get('error_type')))
                terminal_stage = 'dispatch'
                terminal_reason = reason
                terminal_details = dict(details)
            elif reason == 'async_error':
                dispatch = _replace_dispatch(dispatch, async_error=_string_or_none(details.get('error')), async_error_type=_string_or_none(details.get('error_type')))
                terminal_stage = 'async'
                terminal_reason = reason
                terminal_details = dict(details)
        elif rec.kind == 'skip':
            terminal_stage = _stage_for_reason(reason)
            terminal_reason = reason
            terminal_details = dict(details)
        elif rec.kind == 'match' and scope_ok is None:
            scope_ok = True

        _update_trigger_details(trigger_details, rec)

    if scope_ok is None and terminal_reason != 'window_mismatch':
        scope_ok = True
    if injected_ok is None and terminal_reason not in ('injected_ignored', 'injected_only_but_physical'):
        injected_ok = True

    if terminal_reason == 'no_terminal_reason':
        terminal_reason, terminal_stage, terminal_details = _infer_terminal_reason(sorted_records, metadata, trigger_details)

    return BindDecision(
        bind=bind_name,
        device=(sorted_records[0].device if sorted_records else None),
        trigger=trigger,
        records=list(sorted_records),
        checks=checks,
        dispatch=dispatch,
        scope_ok=scope_ok,
        injected_ok=injected_ok,
        fired=fired,
        suppressed=suppressed,
        suppression_reasons=suppression_reasons,
        terminal_stage=terminal_stage,
        terminal_reason=terminal_reason,
        terminal_details=terminal_details,
        trigger_details=trigger_details,
        metadata=metadata,
    )


def _update_trigger_details(trigger_details: Dict[str, Any], rec: DiagnosticRecord) -> None:
    reason = rec.reason
    details = rec.details
    if reason == 'candidate_state':
        trigger_details.update(details)
    elif reason == 'sequence_advanced':
        trigger_details['steps_matched'] = int(details.get('next_index', 0))
        trigger_details['seq_index'] = int(details.get('next_index', 0))
    elif reason == 'chord_became_full':
        trigger_details['chord_full'] = True
        if 'seq_index' in details:
            trigger_details['seq_index'] = details['seq_index']
    elif reason == 'click_started':
        trigger_details['click_started'] = True
    elif reason == 'hold_timer_started':
        trigger_details['hold_timer_started'] = True
        trigger_details['hold_ms'] = details.get('hold_ms', trigger_details.get('hold_ms'))
    elif reason == 'hold_timer_fired':
        trigger_details['hold_timer_fired'] = True
    elif reason == 'hold_timer_cancelled':
        trigger_details['hold_timer_cancelled'] = True
        trigger_details['hold_cancel_reason'] = details.get('reason_detail')
    elif reason == 'repeat_started':
        trigger_details['repeat_started'] = True
        trigger_details['repeat_delay_ms'] = details.get('repeat_delay_ms', trigger_details.get('repeat_delay_ms'))
        trigger_details['repeat_interval_ms'] = details.get('repeat_interval_ms', trigger_details.get('repeat_interval_ms'))
    elif reason == 'repeat_tick':
        trigger_details['repeat_ticks'] = int(trigger_details.get('repeat_ticks', 0)) + 1
    elif reason == 'repeat_cancelled':
        trigger_details['repeat_cancelled'] = details.get('reason_detail', True)
    elif reason == 'double_tap_progress':
        trigger_details['tap_count'] = details.get('tap_count')
        trigger_details['double_tap_window_ms'] = details.get('window_ms', trigger_details.get('double_tap_window_ms'))


def _infer_terminal_reason(records: Sequence[DiagnosticRecord], metadata: Optional[BindMetadata], trigger_details: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    trigger = metadata.trigger if metadata is not None else None
    for rec in reversed(records):
        if _is_direct_terminal_record(rec):
            return rec.reason, _stage_for_reason(rec.reason), dict(rec.details)
    if metadata is not None and metadata.is_sequence:
        steps_matched = int(trigger_details.get('steps_matched', trigger_details.get('seq_index', 0)))
        return 'sequence_waiting_for_next_step', 'constraints', {'steps_matched': steps_matched, 'bind': metadata.bind}
    if trigger == 'on_click':
        if trigger_details.get('click_started'):
            return 'click_waiting_for_release', 'trigger', dict(trigger_details)
        return 'click_not_started', 'trigger', dict(trigger_details)
    if trigger == 'on_hold':
        if trigger_details.get('hold_timer_started') and not trigger_details.get('hold_timer_fired'):
            return 'hold_waiting_or_cancelled', 'trigger', dict(trigger_details)
        return 'hold_not_started', 'trigger', dict(trigger_details)
    if trigger == 'on_repeat':
        if trigger_details.get('repeat_started') and not trigger_details.get('repeat_ticks'):
            return 'repeat_waiting_for_first_tick', 'trigger', dict(trigger_details)
        if trigger_details.get('repeat_ticks'):
            return 'repeat_active', 'trigger', dict(trigger_details)
        return 'repeat_not_started', 'trigger', dict(trigger_details)
    if trigger == 'on_double_tap':
        taps = trigger_details.get('tap_count')
        if taps == 1:
            return 'double_tap_waiting_for_second_tap', 'trigger', dict(trigger_details)
        return 'double_tap_not_started', 'trigger', dict(trigger_details)
    if trigger == 'on_release':
        if trigger_details.get('chord_full'):
            return 'waiting_for_release', 'trigger', dict(trigger_details)
        return 'release_not_armed', 'trigger', dict(trigger_details)
    if trigger == 'on_chord_released':
        if trigger_details.get('chord_full'):
            return 'waiting_for_full_release', 'trigger', dict(trigger_details)
        return 'chord_was_not_fully_pressed', 'trigger', dict(trigger_details)
    if trigger in ('on_press', 'on_chord_complete'):
        if trigger_details.get('full') is False:
            return 'chord_not_complete', 'constraints', dict(trigger_details)
    return 'event_seen_but_bind_not_ready', 'trigger', dict(trigger_details)



def _is_direct_terminal_record(rec: DiagnosticRecord) -> bool:
    if rec.kind in ('skip', 'error', 'fire'):
        return True
    if rec.kind == 'dispatch' and rec.reason in ('callback_finished', 'async_finished'):
        return True
    return False


def _replace_dispatch(dispatch: DispatchOutcome, *, queued: Optional[bool] = None, started: Optional[bool] = None, finished: Optional[bool] = None, returned_awaitable: Optional[bool] = None, async_scheduled: Optional[bool] = None, async_finished: Optional[bool] = None, callback_error: Optional[str] = None, async_error: Optional[str] = None, callback_error_type: Optional[str] = None, async_error_type: Optional[str] = None) -> DispatchOutcome:
    return DispatchOutcome(
        queued=dispatch.queued if queued is None else queued,
        started=dispatch.started if started is None else started,
        finished=dispatch.finished if finished is None else finished,
        returned_awaitable=dispatch.returned_awaitable if returned_awaitable is None else returned_awaitable,
        async_scheduled=dispatch.async_scheduled if async_scheduled is None else async_scheduled,
        async_finished=dispatch.async_finished if async_finished is None else async_finished,
        callback_error=dispatch.callback_error if callback_error is None else callback_error,
        async_error=dispatch.async_error if async_error is None else async_error,
        callback_error_type=dispatch.callback_error_type if callback_error_type is None else callback_error_type,
        async_error_type=dispatch.async_error_type if async_error_type is None else async_error_type,
    )


def _stage_for_reason(reason: str) -> str:
    if reason in ('window_mismatch',):
        return 'scope'
    if reason.startswith('injected_'):
        return 'policy'
    if reason.startswith('check_'):
        return 'checks'
    if reason.startswith('suppressed_'):
        return 'suppression'
    if reason in ('callback_error', 'callback_started', 'callback_finished', 'callback_queued'):
        return 'dispatch'
    if reason in ('async_scheduled', 'async_finished', 'async_error'):
        return 'async'
    if reason in ('debounce_filtered', 'sequence_timeout', 'strict_order_invalid', 'strict_order_attempt_invalid', 'sequence_reset_foreign_key', 'cooldown_active', 'max_fires_reached', 'trigger_not_satisfied', 'hold_not_long_enough', 'hold_timer_cancelled', 'repeat_cancelled', 'button_mismatch', 'chord_not_complete', 'sequence_waiting_for_next_step'):
        return 'constraints'
    if reason in ('bind_fired', 'sequence_advanced', 'chord_became_full'):
        return 'match'
    return 'trigger'


def _reason_text(reason: str, details: Dict[str, Any], metadata: Optional[BindMetadata]) -> str:
    trigger = metadata.trigger if metadata is not None else None
    if reason == 'window_mismatch':
        return 'window scope did not match'
    if reason == 'check_failed':
        return f"check failed: {details.get('check', '<check>')}"
    if reason == 'check_raised':
        check = details.get('check', '<check>')
        et = details.get('error_type', 'Exception')
        err = details.get('error')
        return f"check raised: {check} ({et}: {err})" if err else f"check raised: {check} ({et})"
    if reason == 'injected_ignored':
        return 'input was injected and this bind ignores injected events'
    if reason == 'injected_only_but_physical':
        return 'input was physical but this bind only accepts injected events'
    if reason == 'sequence_reset_foreign_key':
        vk = details.get('vk')
        return f"sequence reset by unrelated key{f' (vk={vk})' if vk is not None else ''}"
    if reason == 'sequence_timeout':
        return 'sequence timed out before the next step was completed'
    if reason == 'sequence_waiting_for_next_step':
        steps = details.get('steps_matched', 0)
        return f"sequence started but is still waiting for the next step (matched {steps} step{'s' if steps != 1 else ''})"
    if reason == 'strict_order_invalid':
        return 'strict order chord rejected the current key order'
    if reason == 'strict_order_attempt_invalid':
        return 'strict order recoverable tail was entered in the wrong order'
    if reason == 'cooldown_active':
        return 'cooldown blocked the callback'
    if reason == 'max_fires_reached':
        return 'max_fires limit was reached'
    if reason == 'debounce_filtered':
        return 'debounce filtered this input'
    if reason == 'trigger_not_satisfied':
        detail = details.get('detail')
        return f"trigger not satisfied: {detail}" if detail else 'trigger not satisfied'
    if reason == 'hold_not_long_enough':
        if trigger == 'on_click':
            return 'press lasted too long to count as a click'
        return 'hold duration was too short'
    if reason == 'hold_timer_cancelled':
        detail = details.get('reason_detail')
        return f"hold timer cancelled: {detail}" if detail else 'hold timer cancelled'
    if reason == 'hold_waiting_or_cancelled':
        if details.get('hold_cancel_reason'):
            return f"hold did not complete: {details['hold_cancel_reason']}"
        hold_ms = details.get('hold_ms')
        return f"hold is waiting for {hold_ms} ms to elapse" if hold_ms is not None else 'hold has started but has not fired yet'
    if reason == 'hold_not_started':
        return 'hold timer never started'
    if reason == 'repeat_cancelled':
        detail = details.get('reason_detail')
        return f"repeat stopped: {detail}" if detail else 'repeat stopped'
    if reason == 'repeat_waiting_for_first_tick':
        delay = details.get('repeat_delay_ms')
        return f"repeat was armed and is waiting for the first tick after {delay} ms" if delay is not None else 'repeat was armed but no tick fired yet'
    if reason == 'repeat_active':
        ticks = details.get('repeat_ticks', 0)
        return f"repeat is active ({ticks} tick{'s' if ticks != 1 else ''} fired)"
    if reason == 'repeat_not_started':
        return 'repeat did not start'
    if reason == 'double_tap_waiting_for_second_tap':
        window_ms = details.get('double_tap_window_ms')
        return f"waiting for the second tap within {window_ms} ms" if window_ms is not None else 'waiting for the second tap'
    if reason == 'double_tap_not_started':
        return 'double tap has not started yet'
    if reason == 'click_waiting_for_release':
        return 'click started and is waiting for button release'
    if reason == 'click_not_started':
        return 'click did not start'
    if reason == 'waiting_for_release':
        return 'chord was completed and is waiting for release'
    if reason == 'waiting_for_full_release':
        return 'chord was completed and is waiting for all keys to be released'
    if reason == 'release_not_armed':
        return 'release trigger was not armed because the chord was not completed'
    if reason == 'chord_was_not_fully_pressed':
        return 'chord was never fully pressed'
    if reason == 'chord_not_complete':
        return 'required keys/buttons were not all active at the same time'
    if reason == 'suppressed_always':
        return 'input was suppressed by ALWAYS policy'
    if reason == 'suppressed_while_active':
        return 'input was suppressed while the bind was active'
    if reason == 'suppressed_while_evaluating':
        return 'input was suppressed while the bind was being evaluated'
    if reason == 'suppressed_when_matched':
        return 'input was suppressed after a successful match'
    if reason == 'bind_fired':
        return 'bind matched and entered the callback path'
    if reason == 'callback_finished':
        return 'callback completed successfully'
    if reason == 'callback_error':
        et = details.get('error_type', 'Exception')
        err = details.get('error')
        return f"callback raised {et}: {err}" if err else f"callback raised {et}"
    if reason == 'async_finished':
        return 'async callback completed successfully'
    if reason == 'async_error':
        et = details.get('error_type', 'Exception')
        err = details.get('error')
        return f"async callback raised {et}: {err}" if err else f"async callback raised {et}"
    if reason == 'event_seen_but_bind_not_ready':
        return 'event reached the bind, but the bind was not ready to fire yet'
    return reason.replace('_', ' ')


def _trigger_lines(decision: BindDecision) -> List[str]:
    d = decision.trigger_details
    out: List[str] = []
    trigger = decision.trigger or (decision.metadata.trigger if decision.metadata is not None else None)
    if decision.metadata is not None and decision.metadata.is_sequence:
        out.append(f"sequence expression: {decision.bind}")
        steps = int(d.get('steps_matched', d.get('seq_index', 0)))
        out.append(f"matched steps: {steps}")
        return out
    if trigger in ('on_press', 'on_chord_complete'):
        full = d.get('full')
        if full is not None:
            out.append(f"chord full on this event: {bool(full)}")
        if d.get('pressed_count') is not None:
            out.append(f"active keys/buttons seen: {d.get('pressed_count')}")
    elif trigger == 'on_release':
        out.append('fires only after a completed press is released')
        if d.get('chord_full'):
            out.append('chord became full before the release')
    elif trigger == 'on_chord_released':
        out.append('fires after the completed chord/button is fully released')
        if d.get('chord_full'):
            out.append('chord had already become full')
    elif trigger == 'on_click':
        if d.get('click_started'):
            out.append('press/click started and is waiting for release to count as a click')
        hold_ms = (decision.metadata.hold_ms if decision.metadata is not None else None) or d.get('hold_ms')
        if hold_ms is not None:
            out.append(f"max click duration: {hold_ms} ms")
    elif trigger == 'on_hold':
        hold_ms = d.get('hold_ms') or (decision.metadata.hold_ms if decision.metadata is not None else None)
        if hold_ms is not None:
            out.append(f"Required hold time: {hold_ms} ms")
        out.append(f"hold timer started: {bool(d.get('hold_timer_started'))}")
        if d.get('hold_cancel_reason'):
            out.append(f"hold cancel reason: {d['hold_cancel_reason']}")
    elif trigger == 'on_repeat':
        delay = d.get('repeat_delay_ms') or (decision.metadata.repeat_delay_ms if decision.metadata is not None else None)
        interval = d.get('repeat_interval_ms') or (decision.metadata.repeat_interval_ms if decision.metadata is not None else None)
        if delay is not None:
            out.append(f"repeat delay: {delay} ms")
        if interval is not None:
            out.append(f"repeat interval: {interval} ms")
        out.append(f"repeat started: {bool(d.get('repeat_started'))}")
        if d.get('repeat_ticks'):
            out.append(f"repeat ticks fired: {d['repeat_ticks']}")
        if d.get('repeat_cancelled'):
            out.append(f"repeat stop reason: {d['repeat_cancelled']}")
    elif trigger == 'on_double_tap':
        window_ms = d.get('double_tap_window_ms') or (decision.metadata.double_tap_window_ms if decision.metadata is not None else None)
        if window_ms is not None:
            out.append(f"double-tap window: {window_ms} ms")
        if d.get('tap_count') is not None:
            out.append(f"tap count observed: {d['tap_count']}")
    return out


def _dispatch_text(dispatch: DispatchOutcome) -> str:
    parts: List[str] = []
    if dispatch.queued:
        parts.append('queued')
    if dispatch.started:
        parts.append('started')
    if dispatch.finished:
        parts.append('finished')
    if dispatch.returned_awaitable:
        parts.append('returned awaitable')
    if dispatch.async_scheduled:
        parts.append('async scheduled')
    if dispatch.async_finished:
        parts.append('async finished')
    if dispatch.callback_error:
        parts.append('callback error')
    if dispatch.async_error:
        parts.append('async error')
    if not parts:
        return 'not reached'
    return ', '.join(parts)


def _candidate_summary(candidate: BindDecision) -> str:
    summary = _reason_text(candidate.terminal_reason, candidate.terminal_details, candidate.metadata)
    if candidate.fired:
        if candidate.dispatch.callback_error or candidate.dispatch.async_error:
            return f"fired, but {summary}"
        if candidate.dispatch.finished or candidate.dispatch.async_finished:
            return 'fired successfully'
        return f"fired ({_dispatch_text(candidate.dispatch)})"
    return f"not fired, {summary}"


def _result_text(decision: BindDecision) -> str:
    if decision.dispatch.callback_error or decision.dispatch.async_error:
        return 'callback failed'
    if decision.dispatch.finished or decision.dispatch.async_finished:
        return 'callback completed'
    if decision.fired:
        return 'callback entered'
    return 'callback not fired'


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _status_text(value: Optional[bool], ok_text: str, fail_text: str, unknown_text: str) -> str:
    if value is True:
        return ok_text
    if value is False:
        return fail_text
    return unknown_text
