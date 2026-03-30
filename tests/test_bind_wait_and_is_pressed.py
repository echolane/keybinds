from __future__ import annotations

import threading
import time


def test_bind_wait_unblocks_on_fire(runtime_env):
    hook = runtime_env.make_hook(auto_start=False)
    called = []
    bind = hook.bind("a", lambda: called.append("fired"))

    result = {}

    def waiter():
        result["value"] = bind.wait(timeout=1.0)

    thread = threading.Thread(target=waiter)
    thread.start()
    time.sleep(0.05)

    driver = runtime_env.HookDriver(runtime_env, hook)
    runtime_env.backend_singleton.current_state_snapshot = driver._state
    driver.key(ord("A"), "down")

    thread.join(timeout=1.0)
    assert result.get("value") is True
    assert called == ["fired"]


def test_bind_wait_times_out(runtime_env):
    hook = runtime_env.make_hook(auto_start=False)
    bind = hook.bind("a", lambda: None)
    assert bind.wait(timeout=0.05) is False


def test_keyboard_bind_is_pressed(runtime_env):
    hook = runtime_env.make_hook(auto_start=False)
    bind = hook.bind("ctrl+a", lambda: None)
    driver = runtime_env.HookDriver(runtime_env, hook)
    runtime_env.backend_singleton.current_state_snapshot = driver._state

    assert bind.is_pressed() is False
    driver.key(runtime_env.winput.VK_CONTROL, "down")
    assert bind.is_pressed() is False
    driver.key(ord("A"), "down")
    assert bind.is_pressed() is True
    driver.key(ord("A"), "up")
    assert bind.is_pressed() is False


def test_mouse_bind_is_pressed(runtime_env):
    hook = runtime_env.make_hook(auto_start=False)
    bind = hook.bind_mouse("left", lambda: None)
    driver = runtime_env.HookDriver(runtime_env, hook)
    runtime_env.backend_singleton.current_state_snapshot = driver._state

    assert bind.is_pressed() is False
    driver.mouse("left", "down")
    assert bind.is_pressed() is True
    driver.mouse("left", "up")
    assert bind.is_pressed() is False


def test_logical_bind_is_pressed(runtime_env):
    hook = runtime_env.make_hook(auto_start=False)
    bind = hook.bind_logical("a", lambda: None)
    driver = runtime_env.HookDriver(runtime_env, hook)
    runtime_env.backend_singleton.current_state_snapshot = driver._state

    assert bind.is_pressed() is False
    driver.key(ord("A"), "down")
    assert bind.is_pressed() is True
    driver.key(ord("A"), "up")
    assert bind.is_pressed() is False


def test_text_abbreviation_bind_is_pressed(runtime_env):
    hook = runtime_env.make_hook(auto_start=False)
    bind = hook.bind_text("ab", lambda: None)
    driver = runtime_env.HookDriver(runtime_env, hook)
    runtime_env.backend_singleton.current_state_snapshot = driver._state

    assert bind.is_pressed() is False
    driver.key(ord("A"), "down")
    assert bind.is_pressed() is False
    driver.key(ord("B"), "down")
    assert bind.is_pressed() is True
    driver.key(ord("B"), "up")
    assert bind.is_pressed() is False


def test_keyboard_bind_is_pressed_prefers_policy_aware_snapshot(runtime_env):
    hook = runtime_env.make_hook(auto_start=False)
    bind = hook.bind("ctrl+a", lambda: None)
    driver = runtime_env.HookDriver(runtime_env, hook)
    runtime_env.backend_singleton.current_state_snapshot = driver._state

    driver.key(runtime_env.winput.VK_CONTROL, "down")
    driver.key(ord("A"), "down", injected=True)
    assert bind.is_pressed() is True

    driver.key(runtime_env.winput.VK_CONTROL, "up")
    assert bind.is_pressed() is False


def test_mouse_bind_is_pressed_prefers_policy_aware_snapshot(runtime_env):
    hook = runtime_env.make_hook(auto_start=False)
    bind = hook.bind_mouse("left", lambda: None)
    driver = runtime_env.HookDriver(runtime_env, hook)
    runtime_env.backend_singleton.current_state_snapshot = driver._state

    driver.mouse("left", "down", injected=True)
    assert bind.is_pressed() is True
