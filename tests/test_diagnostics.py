from __future__ import annotations

import time

import pytest


def _record(core, *, seq, kind, reason, bind=None, event_id=None, dispatch_id=None, device='keyboard', trigger=None, **details):
    return core.DiagnosticRecord(
        ts_ns=time.time_ns(),
        seq=seq,
        kind=kind,
        reason=reason,
        bind=bind,
        device=device,
        trigger=trigger,
        event_id=event_id,
        dispatch_id=dispatch_id,
        details=details,
    )


def test_named_check_and_memory_sink_behaviour(kb_env):
    core = kb_env.diagnostics_core

    check = core.named_check(' foreground ', lambda event, state: True)
    assert check.name == 'foreground'
    assert check(None, None) is True

    sink = core.MemorySink(maxlen=2)
    sink.emit(_record(core, seq=1, kind='skip', reason='one'))
    sink.emit(_record(core, seq=2, kind='skip', reason='two'))
    sink.emit(_record(core, seq=3, kind='skip', reason='three'))

    assert [item.reason for item in sink.get_recent()] == ['two', 'three']
    sink.clear()
    assert sink.get_recent() == []


@pytest.mark.parametrize('level', ['OFF', 'errors', 'trace'])
def test_diagnostics_config_normalizes_valid_levels(kb_env, level):
    cfg = kb_env.diagnostics_core.DiagnosticsConfig(enabled=True, level=level)
    assert cfg.normalized_level() == level.lower()


def test_diagnostics_config_rejects_unknown_level(kb_env):
    cfg = kb_env.diagnostics_core.DiagnosticsConfig(enabled=True, level='verbose')
    with pytest.raises(ValueError):
        cfg.normalized_level()


def test_collect_attempts_and_explain_records_choose_meaningful_candidate(kb_env):
    core = kb_env.diagnostics_core
    analysis = kb_env.diagnostics_analysis

    records = [
        _record(core, seq=1, kind='raw', reason='input_event', event_id=1, vk=69, action='down'),
        _record(core, seq=2, kind='skip', reason='check_failed', bind='ctrl+e', event_id=1, check='is_editor'),
        _record(core, seq=3, kind='raw', reason='input_event', event_id=2, vk=69, action='down'),
        _record(core, seq=4, kind='fire', reason='bind_fired', bind='ctrl+e', event_id=2, dispatch_id=21, trigger='ON_PRESS'),
        _record(core, seq=5, kind='dispatch', reason='callback_finished', bind='ctrl+e', event_id=2, dispatch_id=21),
    ]
    meta = {
        'ctrl+e': core.BindMetadata(bind='ctrl+e', device='keyboard', trigger='ON_PRESS')
    }

    attempts = analysis.collect_attempts(records, last_ms=5_000, bind_meta=meta)
    report = analysis.explain_records('ctrl+e', records, last_ms=5_000, bind_meta=meta)
    rendered = analysis.render_explain_report(report, verbosity='normal')

    assert len(attempts) == 2
    assert report.decision is not None
    assert report.decision.dispatch.finished is True
    assert report.decision.terminal_reason == 'callback_finished'
    assert 'Bind: ctrl+e' in rendered
    assert 'Primary reason:' in rendered


def test_explain_records_returns_empty_report_when_no_candidate_found(kb_env):
    analysis = kb_env.diagnostics_analysis
    report = analysis.explain_records('missing', [], last_ms=5_000)

    assert report.attempt is None
    assert 'no meaningful attempts found' in report.render_text()
