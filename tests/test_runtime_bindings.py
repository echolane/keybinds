from __future__ import annotations

import time


def _wait_until(predicate, *, timeout: float = 0.4, interval: float = 0.005) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_hook_bind_press_and_unbind_runtime(runtime_env):
    Trigger = runtime_env.types.Trigger
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    bind = hook.bind('ctrl+a', lambda: hits.append('press'))

    assert bind.config.trigger is Trigger.ON_PRESS
    assert driver.key(runtime_env.winput.VK_CONTROL, 'down') == runtime_env.winput.WP_CONTINUE
    assert driver.key(ord('A'), 'down') == runtime_env.winput.WP_CONTINUE
    assert hits == ['press']

    driver.key(ord('A'), 'up')
    driver.key(runtime_env.winput.VK_CONTROL, 'up')
    hook.unbind(bind)

    driver.key(runtime_env.winput.VK_CONTROL, 'down')
    driver.key(ord('A'), 'down')
    assert hits == ['press']


def test_hook_bind_release_with_when_matched_suppression_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    SuppressPolicy = runtime_env.types.SuppressPolicy
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind(
        'ctrl+r',
        lambda: hits.append('release'),
        config=BindConfig(trigger=Trigger.ON_RELEASE, suppress=SuppressPolicy.WHEN_MATCHED),
    )

    driver.key(runtime_env.winput.VK_CONTROL, 'down')
    flags_down = driver.key(ord('R'), 'down')
    flags_up = driver.key(ord('R'), 'up')

    assert flags_down & runtime_env.winput.WP_DONT_PASS_INPUT_ON
    assert flags_up & runtime_env.winput.WP_DONT_PASS_INPUT_ON
    assert hits == ['release']


def test_hook_bind_sequence_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind(
        'g,k,i',
        lambda: hits.append('sequence'),
        config=BindConfig(trigger=Trigger.ON_SEQUENCE, timing=Timing(chord_timeout_ms=200)),
    )

    for vk in (ord('G'), ord('K'), ord('I')):
        driver.key(vk, 'down')
        driver.key(vk, 'up')

    assert hits == ['sequence']


def test_hook_bind_strict_order_chord_complete_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    ChordPolicy = runtime_env.types.ChordPolicy
    Constraints = runtime_env.types.Constraints
    OrderPolicy = runtime_env.types.OrderPolicy
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind(
        'ctrl+shift+a',
        lambda: hits.append('strict'),
        config=BindConfig(
            trigger=Trigger.ON_CHORD_COMPLETE,
            constraints=Constraints(
                chord_policy=ChordPolicy.STRICT,
                order_policy=OrderPolicy.STRICT,
            ),
        ),
    )

    driver.key(runtime_env.winput.VK_SHIFT, 'down')
    driver.key(runtime_env.winput.VK_CONTROL, 'down')
    driver.key(ord('A'), 'down')
    assert hits == []

    driver.key(ord('A'), 'up')
    driver.key(runtime_env.winput.VK_CONTROL, 'up')
    driver.key(runtime_env.winput.VK_SHIFT, 'up')

    driver.key(runtime_env.winput.VK_CONTROL, 'down')
    driver.key(runtime_env.winput.VK_SHIFT, 'down')
    driver.key(ord('A'), 'down')
    assert hits == ['strict']


def test_hook_bind_click_and_hold_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind('space', lambda: hits.append('click'), config=BindConfig(trigger=Trigger.ON_CLICK, timing=Timing(hold_ms=40)))
    hook.bind('f', lambda: hits.append('hold'), config=BindConfig(trigger=Trigger.ON_HOLD, timing=Timing(hold_ms=20)))

    driver.key(runtime_env.winput.VK_SPACE, 'down')
    driver.key(runtime_env.winput.VK_SPACE, 'up', dt=10)
    assert hits == ['click']

    driver.key(ord('F'), 'down')
    assert _wait_until(lambda: hits.count('hold') == 1)
    driver.key(ord('F'), 'up')
    assert hits == ['click', 'hold']


def test_hook_bind_mouse_release_and_double_tap_runtime(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse('right', lambda: hits.append('release'), config=MouseBindConfig(trigger=Trigger.ON_RELEASE))
    hook.bind_mouse('left', lambda: hits.append('double'), config=MouseBindConfig(trigger=Trigger.ON_DOUBLE_TAP, timing=Timing(double_tap_window_ms=200)))

    driver.mouse('right', 'down')
    driver.mouse('right', 'up')
    assert hits == ['release']

    driver.mouse('left', 'down')
    driver.mouse('left', 'up')
    driver.mouse('left', 'down', dt=50)
    assert hits == ['release', 'double']


def test_hook_bind_mouse_repeat_runtime(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse(
        'left',
        lambda: hits.append(time.monotonic()),
        config=MouseBindConfig(
            trigger=Trigger.ON_REPEAT,
            timing=Timing(hold_ms=0, repeat_delay_ms=5, repeat_interval_ms=10),
        ),
    )

    driver.mouse('left', 'down')
    assert _wait_until(lambda: len(hits) >= 2)
    before_release = len(hits)
    driver.mouse('left', 'up')
    time.sleep(0.05)
    assert len(hits) == before_release


def test_hook_bind_logical_layout_aware_chord_runtime(runtime_env):
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    runtime_env.translate.LogicalTranslator.char_map[ord('S')] = 'ß'
    hook.bind_logical('ctrl+ß', lambda: hits.append('logical'))

    driver.key(runtime_env.winput.VK_CONTROL, 'down')
    driver.key(ord('S'), 'down')
    assert hits == ['logical']


def test_hook_bind_logical_text_sequence_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_logical('h,e,l,l,o', lambda: hits.append('hello'), config=BindConfig(trigger=Trigger.ON_SEQUENCE))

    for vk in (ord('H'), ord('E'), ord('L'), ord('L'), ord('O')):
        driver.key(vk, 'down')
        driver.key(vk, 'up')

    assert hits == ['hello']


def test_hook_bind_text_whole_word_runtime(runtime_env):
    LogicalConfig = runtime_env.types.LogicalConfig
    TextBoundaryPolicy = runtime_env.types.TextBoundaryPolicy

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_text(
        'brb',
        lambda: hits.append('text'),
        logical_config=LogicalConfig(text_boundary_policy=TextBoundaryPolicy.WHOLE_WORD),
    )

    for vk in (ord('B'), ord('R'), ord('B'), runtime_env.winput.VK_SPACE):
        driver.key(vk, 'down')
        driver.key(vk, 'up')

    assert hits == ['text']


def test_hook_add_abbreviation_runtime(runtime_env):
    LogicalConfig = runtime_env.types.LogicalConfig
    TextBoundaryPolicy = runtime_env.types.TextBoundaryPolicy

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    callbacks = []

    hook.add_abbreviation(
        'teh',
        'the',
        lambda: callbacks.append('expanded'),
        logical_config=LogicalConfig(text_boundary_policy=TextBoundaryPolicy.WHOLE_WORD),
    )

    for vk in (ord('T'), ord('E'), ord('H'), runtime_env.winput.VK_SPACE):
        driver.key(vk, 'down')
        driver.key(vk, 'up')

    assert callbacks == ['expanded']
    assert runtime_env.translate.sent_backspaces == [3]
    assert runtime_env.translate.sent_unicode_text == ['he ']


def test_hook_bind_chord_released_and_double_tap_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind('ctrl+d', lambda: hits.append('released'), config=BindConfig(trigger=Trigger.ON_CHORD_RELEASED))
    hook.bind('q', lambda: hits.append('double'), config=BindConfig(trigger=Trigger.ON_DOUBLE_TAP, timing=Timing(double_tap_window_ms=200)))

    driver.key(runtime_env.winput.VK_CONTROL, 'down')
    driver.key(ord('D'), 'down')
    driver.key(ord('D'), 'up')
    driver.key(runtime_env.winput.VK_CONTROL, 'up')
    assert hits == ['released']

    driver.key(ord('Q'), 'down')
    driver.key(ord('Q'), 'up')
    driver.key(ord('Q'), 'down', dt=50)
    assert hits == ['released', 'double']


def test_hook_bind_mouse_press_click_and_hold_runtime(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse('left', lambda: hits.append('press'))
    hook.bind_mouse('right', lambda: hits.append('click'), config=MouseBindConfig(trigger=Trigger.ON_CLICK, timing=Timing(hold_ms=40)))
    hook.bind_mouse('x1', lambda: hits.append('hold'), config=MouseBindConfig(trigger=Trigger.ON_HOLD, timing=Timing(hold_ms=20)))

    driver.mouse('left', 'down')
    assert hits == ['press']
    driver.mouse('left', 'up')

    driver.mouse('right', 'down')
    driver.mouse('right', 'up', dt=10)
    assert hits == ['press', 'click']

    driver.mouse('x1', 'down')
    assert _wait_until(lambda: hits.count('hold') == 1)
    driver.mouse('x1', 'up')
    assert hits == ['press', 'click', 'hold']


def test_hook_bind_keyboard_triple_tap_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind('q', lambda: hits.append('triple'), config=BindConfig(trigger=Trigger.ON_TRIPLE_TAP, timing=Timing(triple_tap_window_ms=200)))

    driver.key(ord('Q'), 'down')
    driver.key(ord('Q'), 'up')
    driver.key(ord('Q'), 'down', dt=50)
    driver.key(ord('Q'), 'up')
    assert hits == []

    driver.key(ord('Q'), 'down', dt=50)
    assert hits == ['triple']


def test_hook_bind_mouse_triple_tap_runtime(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse('left', lambda: hits.append('triple'), config=MouseBindConfig(trigger=Trigger.ON_TRIPLE_TAP, timing=Timing(triple_tap_window_ms=200)))

    driver.mouse('left', 'down')
    driver.mouse('left', 'up')
    driver.mouse('left', 'down', dt=50)
    driver.mouse('left', 'up')
    assert hits == []

    driver.mouse('left', 'down', dt=50)
    assert hits == ['triple']


def test_hook_bind_logical_triple_tap_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_logical('q', lambda: hits.append('triple'), config=BindConfig(trigger=Trigger.ON_TRIPLE_TAP, timing=Timing(triple_tap_window_ms=200)))

    driver.key(ord('Q'), 'down')
    driver.key(ord('Q'), 'up')
    driver.key(ord('Q'), 'down', dt=50)
    driver.key(ord('Q'), 'up')
    assert hits == []

    driver.key(ord('Q'), 'down', dt=50)
    assert hits == ['triple']
