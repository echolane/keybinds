from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_register_bind_tracks_hook_and_kind(kb_env):
    bind = SimpleNamespace(hook=None)
    hook = object()

    kb_env.registry.register_bind(bind, hook, 'keyboard')

    assert kb_env.registry.hook_for_bind(bind) is hook
    assert kb_env.registry.kind_for_bind(bind) == 'keyboard'
    assert bind.hook is hook

    kb_env.registry.unregister_bind(bind)
    assert kb_env.registry.hook_for_bind(bind) is None
    assert kb_env.registry.kind_for_bind(bind) is None
    assert bind.hook is None


def test_register_bind_rejects_rebinding_to_another_hook(kb_env):
    bind = SimpleNamespace(hook=None)
    kb_env.registry.register_bind(bind, object(), 'keyboard')

    with pytest.raises(ValueError):
        kb_env.registry.register_bind(bind, object(), 'keyboard')


def test_add_and_remove_binds_keep_function_attributes_in_sync(kb_env):
    bind1 = SimpleNamespace()
    bind2 = SimpleNamespace()

    def callback():
        return None

    kb_env.registry.add_binds_to_func(callback, [bind1])
    assert callback.bind is bind1
    assert callback.binds == [bind1]
    assert kb_env.registry.owner_func_for_bind(bind1) is callback

    kb_env.registry.add_binds_to_func(callback, [bind2])
    assert callback.bind == [bind1, bind2]
    assert callback.binds == [bind1, bind2]

    kb_env.registry.remove_binds_from_func(callback, [bind1])
    assert callback.bind is bind2
    assert callback.binds == [bind2]
