from __future__ import annotations

import pytest


def test_bind_key_uses_default_hook_and_attaches_created_binds(kb_env):
    decorators = kb_env.decorators
    Trigger = kb_env.types.Trigger
    SuppressPolicy = kb_env.types.SuppressPolicy

    @decorators.bind_key(['ctrl+e', 'ctrl+r'], trigger_on_release=True, suppress=True)
    def callback():
        return None

    assert len(kb_env.default_hook.calls) == 2
    kinds = [call[0] for call in kb_env.default_hook.calls]
    assert kinds == ['bind', 'bind']

    for _, args, kwargs, bind in kb_env.default_hook.calls:
        assert args[1] is callback
        assert kwargs['config'].trigger is Trigger.ON_RELEASE
        assert kwargs['config'].suppress is SuppressPolicy.WHEN_MATCHED
        assert bind in callback.binds

    assert callback.bind == callback.binds


def test_logical_text_and_abbreviation_decorators_delegate_to_hook(kb_env):
    hook = kb_env.FakeHook()
    decorators = kb_env.decorators

    @decorators.bind_logical(['ctrl+A', 'ß'], hook=hook)
    def logical_cb():
        return None

    @decorators.bind_text(['hello', 'world'], hook=hook)
    def text_cb():
        return None

    @decorators.bind_abbreviation(['brb', 'omw'], 'be right back', hook=hook)
    def abbr_cb():
        return None

    kinds = [call[0] for call in hook.calls]
    assert kinds == [
        'bind_logical',
        'bind_logical',
        'bind_text',
        'bind_text',
        'add_abbreviation',
        'add_abbreviation',
    ]
    assert len(logical_cb.binds) == 2
    assert len(text_cb.binds) == 2
    assert len(abbr_cb.binds) == 2


def test_add_abbreviation_function_returns_bind_from_default_hook(kb_env):
    result = kb_env.decorators.add_abbreviation('idk', "I don't know")

    assert result.kind == 'abbreviation'
    assert kb_env.default_hook.calls[-1][0] == 'add_abbreviation'


def test_simple_build_config_validates_conflicts_and_priorities(kb_env):
    simple = kb_env.simple
    Trigger = kb_env.types.Trigger

    with pytest.raises(ValueError):
        simple._build_config(release=True, hold=100)

    cfg = simple._build_config(sequence=True, timeout=650, suppress=True)
    assert cfg.trigger is Trigger.ON_SEQUENCE
    assert cfg.timing.chord_timeout_ms == 650
    assert cfg.suppress is kb_env.types.SuppressPolicy.WHEN_MATCHED

    cfg = simple._build_config(triple_tap=True, triple_tap_window=275)
    assert cfg.trigger is Trigger.ON_TRIPLE_TAP
    assert cfg.timing.triple_tap_window_ms == 275

    mouse_cfg = simple._build_mouse_config(triple_tap=True, triple_tap_window=325)
    assert mouse_cfg.trigger is Trigger.ON_TRIPLE_TAP
    assert mouse_cfg.timing.triple_tap_window_ms == 325


def test_simple_hotkey_builds_config_and_flows_into_decorator_binding(kb_env):
    simple = kb_env.simple
    Trigger = kb_env.types.Trigger

    hook = kb_env.FakeHook()

    @simple.hotkey('g,k,i', sequence=True, timeout=600, hook=hook)
    def secret():
        return None

    kind, args, kwargs, _ = hook.calls[0]
    assert kind == 'bind'
    assert args[0] == 'g,k,i'
    assert args[1] is secret
    assert kwargs['config'].trigger is Trigger.ON_SEQUENCE
    assert kwargs['config'].timing.chord_timeout_ms == 600
