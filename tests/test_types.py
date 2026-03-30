from __future__ import annotations

import pytest


def test_checks_coerce_accepts_none_callable_and_sequences(kb_env):
    Checks = kb_env.types.Checks

    empty = Checks.coerce(None)
    single = Checks.coerce(lambda event, state: True)
    many = Checks.coerce([lambda event, state: True, lambda event, state: False])

    assert tuple(empty) == ()
    assert len(tuple(single)) == 1
    assert len(tuple(many)) == 2


def test_bind_config_soft_merge_only_applies_non_default_values(kb_env):
    BindConfig = kb_env.types.BindConfig
    Trigger = kb_env.types.Trigger
    Timing = kb_env.types.Timing

    base = BindConfig(trigger=Trigger.ON_SEQUENCE, timing=Timing(chord_timeout_ms=900, hold_ms=111))
    patch = BindConfig(timing=Timing(repeat_interval_ms=25))

    merged = base.soft_merge(patch)

    assert merged.trigger is Trigger.ON_SEQUENCE
    assert merged.timing.chord_timeout_ms == 900
    assert merged.timing.hold_ms == 111
    assert merged.timing.repeat_interval_ms == 25


def test_bind_config_hard_merge_overwrites_with_defaults(kb_env):
    BindConfig = kb_env.types.BindConfig
    Trigger = kb_env.types.Trigger
    SuppressPolicy = kb_env.types.SuppressPolicy

    base = BindConfig(trigger=Trigger.ON_REPEAT, suppress=SuppressPolicy.WHEN_MATCHED)
    override = BindConfig()

    merged = base.hard_merge(override)

    assert merged.trigger is Trigger.ON_PRESS
    assert merged.suppress is SuppressPolicy.NEVER


@pytest.mark.parametrize('method', ['soft_merge', 'hard_merge'])
def test_bind_config_merge_rejects_wrong_types(kb_env, method):
    BindConfig = kb_env.types.BindConfig

    with pytest.raises(TypeError):
        getattr(BindConfig(), method)('not a config')


def test_mouse_bind_config_operator_sugar_matches_merge_methods(kb_env):
    MouseBindConfig = kb_env.types.MouseBindConfig
    Trigger = kb_env.types.Trigger
    SuppressPolicy = kb_env.types.SuppressPolicy

    lhs = MouseBindConfig(trigger=Trigger.ON_HOLD)
    rhs = MouseBindConfig(suppress=SuppressPolicy.WHEN_MATCHED)

    assert (lhs + rhs) == lhs.soft_merge(rhs)
    assert (lhs | rhs) == lhs.hard_merge(rhs)
