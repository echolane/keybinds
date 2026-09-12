from __future__ import annotations

import pytest


def test_normalize_mouse_button_accepts_wheel_aliases(runtime_env):
    normalize = runtime_env._mouse._normalize_mouse_button
    MouseButton = runtime_env.types.MouseButton

    assert normalize("wheel_up") is MouseButton.WHEEL_UP
    assert normalize("scrollup") is MouseButton.WHEEL_UP
    assert normalize("wheel-down") is MouseButton.WHEEL_DOWN
    assert normalize("hwheel_left") is MouseButton.WHEEL_LEFT
    assert normalize("hwheel_right") is MouseButton.WHEEL_RIGHT
    assert normalize(MouseButton.WHEEL_UP) is MouseButton.WHEEL_UP

    with pytest.raises(ValueError):
        normalize("wheel")
    with pytest.raises(ValueError):
        normalize("tilt_left")


def test_wheel_bind_rejects_non_press_triggers(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    Trigger = runtime_env.types.Trigger
    hook = runtime_env.make_hook()

    with pytest.raises(ValueError, match="ON_PRESS"):
        hook.bind_mouse(
            "wheel_up",
            lambda: None,
            config=MouseBindConfig(trigger=Trigger.ON_HOLD),
        )


def test_wheel_delta_rejects_non_positive(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    with pytest.raises(ValueError, match="wheel_delta"):
        MouseBindConfig(wheel_delta=0)


def test_vertical_wheel_accumulates_to_configured_delta(runtime_env):
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    bind = hook.bind_mouse("wheel_up", lambda: hits.append("up"))
    hook.bind_mouse("wheel_down", lambda: hits.append("down"))

    assert bind.config.wheel_delta == 120
    assert driver.wheel(60) == runtime_env.winput.WP_CONTINUE
    assert hits == []
    assert bind._wheel_acc == 60

    assert driver.wheel(60) == runtime_env.winput.WP_CONTINUE
    assert hits == ["up"]
    assert bind._wheel_acc == 0


def test_custom_wheel_delta_changes_quantum(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse(
        "wheel_up",
        lambda: hits.append("up"),
        config=MouseBindConfig(wheel_delta=40),
    )

    driver.wheel(40)
    driver.wheel(80)
    assert hits == ["up", "up", "up"]


def test_wheel_delta_soft_merge_overrides_default(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    SuppressPolicy = runtime_env.types.SuppressPolicy

    merged = MouseBindConfig(suppress=SuppressPolicy.WHEN_MATCHED).soft_merge(
        MouseBindConfig(wheel_delta=30)
    )
    assert merged.wheel_delta == 30
    assert merged.suppress is SuppressPolicy.WHEN_MATCHED


def test_vertical_wheel_fires_once_per_notch_including_multiples(runtime_env):
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse("wheel_down", lambda: hits.append("down"))

    driver.wheel(-240)
    assert hits == ["down", "down"]


def test_opposite_vertical_direction_resets_remainder(runtime_env):
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    up = hook.bind_mouse("wheel_up", lambda: hits.append("up"))

    driver.wheel(60)
    assert up._wheel_acc == 60
    driver.wheel(-30)
    assert up._wheel_acc == 0
    driver.wheel(60)
    assert hits == []


def test_horizontal_wheel_is_independent_axis(runtime_env):
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse("wheel_left", lambda: hits.append("left"))
    hook.bind_mouse("wheel_right", lambda: hits.append("right"))
    hook.bind_mouse("wheel_up", lambda: hits.append("up"))

    driver.wheel(-120, horizontal=True)
    driver.wheel(120, horizontal=True)
    driver.wheel(120)

    assert hits == ["left", "right", "up"]


def test_wheel_when_matched_suppresses_only_after_a_notch(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    SuppressPolicy = runtime_env.types.SuppressPolicy
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse(
        "wheel_up",
        lambda: hits.append("up"),
        config=MouseBindConfig(suppress=SuppressPolicy.WHEN_MATCHED),
    )

    flags_partial = driver.wheel(40)
    flags_full = driver.wheel(80)

    assert flags_partial == runtime_env.winput.WP_CONTINUE
    assert flags_full & runtime_env.winput.WP_DONT_PASS_INPUT_ON
    assert hits == ["up"]


def test_wheel_is_never_pressed(runtime_env):
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    runtime_env.backend_singleton.current_state_snapshot = driver._state
    bind = hook.bind_mouse("wheel_up", lambda: None)

    driver.wheel(120)
    assert bind.is_pressed() is False
    assert bind.pressed_keys() == []


def test_wheel_respects_injected_ignore(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    InjectedPolicy = runtime_env.types.InjectedPolicy
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse(
        "wheel_up",
        lambda: hits.append("up"),
        config=MouseBindConfig(injected=InjectedPolicy.IGNORE),
    )

    driver.wheel(120, injected=True)
    driver.wheel(120, injected=False)
    assert hits == ["up"]
