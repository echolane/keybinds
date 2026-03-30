from __future__ import annotations

import time


def _wait_until(predicate, *, timeout: float = 0.4, interval: float = 0.005) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _tap_key(driver, vk: int, *, dt_down: int | None = None, dt_up: int | None = None, injected: bool = False):
    driver.key(vk, 'down', dt=dt_down, injected=injected)
    driver.key(vk, 'up', dt=dt_up, injected=injected)


def test_hook_bind_overlapping_sequence_prefix_and_longer_match_both(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind('g,k', lambda: hits.append('short'), config=BindConfig(trigger=Trigger.ON_SEQUENCE))
    hook.bind('g,k,i', lambda: hits.append('long'), config=BindConfig(trigger=Trigger.ON_SEQUENCE))

    for vk in (ord('G'), ord('K'), ord('I')):
        _tap_key(driver, vk)

    assert hits == ['short', 'long']


def test_hook_bind_sequence_timeout_and_foreign_key_policies(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    ChordPolicy = runtime_env.types.ChordPolicy
    Constraints = runtime_env.types.Constraints
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind(
        'g,k',
        lambda: hits.append('timeout'),
        config=BindConfig(trigger=Trigger.ON_SEQUENCE, timing=Timing(chord_timeout_ms=30)),
    )
    hook.bind(
        'h,j',
        lambda: hits.append('strict_reset'),
        config=BindConfig(trigger=Trigger.ON_SEQUENCE),
    )
    hook.bind(
        'u,i',
        lambda: hits.append('relaxed'),
        config=BindConfig(
            trigger=Trigger.ON_SEQUENCE,
            constraints=Constraints(chord_policy=ChordPolicy.RELAXED),
        ),
    )

    _tap_key(driver, ord('G'))
    _tap_key(driver, ord('K'), dt_down=80)

    _tap_key(driver, ord('H'))
    _tap_key(driver, ord('X'))
    _tap_key(driver, ord('J'))

    _tap_key(driver, ord('U'))
    _tap_key(driver, ord('X'))
    _tap_key(driver, ord('I'))

    assert hits == ['relaxed']


def test_hook_bind_sequence_allows_extra_modifier_by_default(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind('g,k', lambda: hits.append('matched'), config=BindConfig(trigger=Trigger.ON_SEQUENCE))

    _tap_key(driver, ord('G'))
    driver.key(runtime_env.winput.VK_SHIFT, 'down')
    driver.key(runtime_env.winput.VK_SHIFT, 'up')
    _tap_key(driver, ord('K'))

    assert hits == ['matched']


def test_hook_bind_chord_policy_relaxed_accepts_extra_non_modifier(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    ChordPolicy = runtime_env.types.ChordPolicy
    Constraints = runtime_env.types.Constraints

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind(
        'ctrl+a',
        lambda: hits.append('strictish'),
    )
    hook.bind(
        'ctrl+b',
        lambda: hits.append('relaxed'),
        config=BindConfig(constraints=Constraints(chord_policy=ChordPolicy.RELAXED)),
    )

    driver.key(runtime_env.winput.VK_CONTROL, 'down')
    driver.key(ord('X'), 'down')
    driver.key(ord('A'), 'down')
    driver.key(ord('B'), 'down')

    assert hits == ['relaxed']


def test_hook_keyboard_injected_policy_ignore_and_only_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    InjectedPolicy = runtime_env.types.InjectedPolicy

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind('a', lambda: hits.append('ignore'), config=BindConfig(injected=InjectedPolicy.IGNORE))
    hook.bind('b', lambda: hits.append('only'), config=BindConfig(injected=InjectedPolicy.ONLY))

    _tap_key(driver, ord('A'), injected=True)
    _tap_key(driver, ord('A'))
    _tap_key(driver, ord('B'))
    _tap_key(driver, ord('B'), injected=True)

    assert hits == ['ignore', 'only']


def test_hook_mouse_injected_policy_and_suppress_while_evaluating_runtime(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    InjectedPolicy = runtime_env.types.InjectedPolicy
    SuppressPolicy = runtime_env.types.SuppressPolicy

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse('left', lambda: hits.append('only'), config=MouseBindConfig(injected=InjectedPolicy.ONLY))
    hook.bind_mouse('right', lambda: hits.append('eval'), config=MouseBindConfig(suppress=SuppressPolicy.WHILE_EVALUATING))

    physical_flags = driver.mouse('left', 'down')
    injected_flags = driver.mouse('left', 'down', injected=True)
    driver.mouse('left', 'up', injected=True)

    right_down = driver.mouse('right', 'down')
    right_up = driver.mouse('right', 'up')

    assert physical_flags == runtime_env.winput.WP_CONTINUE
    assert injected_flags == runtime_env.winput.WP_CONTINUE
    assert hits == ['only', 'eval']
    assert right_down & runtime_env.winput.WP_DONT_PASS_INPUT_ON
    assert right_up & runtime_env.winput.WP_DONT_PASS_INPUT_ON


def test_hook_bind_suppress_while_evaluating_and_always_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    SuppressPolicy = runtime_env.types.SuppressPolicy

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)

    hook.bind('ctrl+a', lambda: None, config=BindConfig(suppress=SuppressPolicy.WHILE_EVALUATING))
    hook.bind('z', lambda: None, config=BindConfig(suppress=SuppressPolicy.ALWAYS))

    ctrl_flags = driver.key(runtime_env.winput.VK_CONTROL, 'down')
    a_flags = driver.key(ord('A'), 'down')
    z_down = driver.key(ord('Z'), 'down')
    z_up = driver.key(ord('Z'), 'up')

    assert ctrl_flags & runtime_env.winput.WP_DONT_PASS_INPUT_ON
    assert a_flags & runtime_env.winput.WP_DONT_PASS_INPUT_ON
    assert z_down & runtime_env.winput.WP_DONT_PASS_INPUT_ON
    assert z_up & runtime_env.winput.WP_DONT_PASS_INPUT_ON


def test_hook_pause_resume_resets_sequence_progress_runtime(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind('g,k', lambda: hits.append('sequence'), config=BindConfig(trigger=Trigger.ON_SEQUENCE))

    _tap_key(driver, ord('G'))
    hook.pause()
    _tap_key(driver, ord('K'))
    hook.resume()
    _tap_key(driver, ord('K'))
    assert hits == []

    _tap_key(driver, ord('G'))
    _tap_key(driver, ord('K'))
    assert hits == ['sequence']


def test_hook_window_scoped_bind_respects_focus_and_blur_resets_state(runtime_env):
    BindConfig = runtime_env.types.BindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    class FakeWindow:
        def __init__(self):
            self.focused = True

        def is_focused(self):
            return self.focused

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []
    window = FakeWindow()

    bind = hook.bind(
        'g,k',
        lambda: hits.append('sequence'),
        hwnd=123,
        config=BindConfig(trigger=Trigger.ON_SEQUENCE, timing=Timing(window_focus_cache_ms=0)),
    )
    bind.window = window

    window.focused = False
    _tap_key(driver, ord('G'))
    assert hits == []

    window.focused = True
    _tap_key(driver, ord('G'))
    window.focused = False
    _tap_key(driver, ord('X'))
    window.focused = True
    _tap_key(driver, ord('K'))
    assert hits == []

    _tap_key(driver, ord('G'))
    _tap_key(driver, ord('K'))
    assert hits == ['sequence']


def test_hook_bind_text_word_boundaries_runtime(runtime_env):
    LogicalConfig = runtime_env.types.LogicalConfig
    TextBoundaryPolicy = runtime_env.types.TextBoundaryPolicy

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_text('brb', lambda: hits.append('start'), logical_config=LogicalConfig(text_boundary_policy=TextBoundaryPolicy.WORD_START))
    hook.bind_text('end', lambda: hits.append('end'), logical_config=LogicalConfig(text_boundary_policy=TextBoundaryPolicy.WORD_END))

    for vk in (ord('X'), ord('B'), ord('R'), ord('B')):
        _tap_key(driver, vk)
    for vk in (runtime_env.winput.VK_SPACE, ord('B'), ord('R'), ord('B')):
        _tap_key(driver, vk)

    for vk in (ord('X'), ord('E'), ord('N'), ord('D')):
        _tap_key(driver, vk)
    _tap_key(driver, runtime_env.winput.VK_SPACE)

    assert hits == ['start', 'end']


def test_hook_bind_text_backspace_policies_runtime(runtime_env):
    LogicalConfig = runtime_env.types.LogicalConfig
    TextBackspacePolicy = runtime_env.types.TextBackspacePolicy

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_text('ac', lambda: hits.append('edit'), logical_config=LogicalConfig(text_backspace_policy=TextBackspacePolicy.EDIT_BUFFER))
    hook.bind_text('zz', lambda: hits.append('ignore'), logical_config=LogicalConfig(text_backspace_policy=TextBackspacePolicy.IGNORE))
    hook.bind_text('mn', lambda: hits.append('clear_non_text'), logical_config=LogicalConfig(text_clear_buffer_on_non_text=True))
    hook.bind_text('qr', lambda: hits.append('clear_buffer'), logical_config=LogicalConfig(text_backspace_policy=TextBackspacePolicy.CLEAR_BUFFER))

    for vk in (ord('A'), ord('B'), runtime_env.winput.VK_BACK, ord('C')):
        _tap_key(driver, vk)

    for vk in (ord('Z'), runtime_env.winput.VK_BACK, ord('Z')):
        _tap_key(driver, vk)

    for vk in (ord('M'), runtime_env.winput.VK_F1, ord('N')):
        _tap_key(driver, vk)

    for vk in (ord('Q'), runtime_env.winput.VK_BACK, ord('R')):
        _tap_key(driver, vk)

    assert hits == ['edit', 'ignore']


def test_hook_bind_text_clear_buffer_and_ignore_ctrl_combo_runtime(runtime_env):
    LogicalConfig = runtime_env.types.LogicalConfig

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_text('ab', lambda: hits.append('text'), logical_config=LogicalConfig(text_clear_buffer_on_non_text=True))

    _tap_key(driver, ord('A'))
    _tap_key(driver, runtime_env.winput.VK_F1)
    _tap_key(driver, ord('B'))
    assert hits == []

    _tap_key(driver, ord('A'))
    driver.key(runtime_env.winput.VK_CONTROL, 'down')
    _tap_key(driver, ord('B'))
    driver.key(runtime_env.winput.VK_CONTROL, 'up')
    assert hits == []

    _tap_key(driver, ord('B'))
    assert hits == ['text']


def test_hook_bind_text_os_repeat_policies_runtime(runtime_env):
    LogicalConfig = runtime_env.types.LogicalConfig
    OsKeyRepeatPolicy = runtime_env.types.OsKeyRepeatPolicy

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_text('aaa', lambda: hits.append('match'), logical_config=LogicalConfig(os_key_repeat_policy=OsKeyRepeatPolicy.MATCH))
    hook.bind_text('bbb', lambda: hits.append('ignore'), logical_config=LogicalConfig(os_key_repeat_policy=OsKeyRepeatPolicy.IGNORE))
    hook.bind_text('ccc', lambda: hits.append('reset'), logical_config=LogicalConfig(os_key_repeat_policy=OsKeyRepeatPolicy.RESET))

    driver.key(ord('A'), 'down')
    driver.key(ord('A'), 'down')
    driver.key(ord('A'), 'down')
    driver.key(ord('A'), 'up')

    driver.key(ord('B'), 'down')
    driver.key(ord('B'), 'down')
    driver.key(ord('B'), 'down')
    driver.key(ord('B'), 'up')

    driver.key(ord('C'), 'down')
    driver.key(ord('C'), 'down')
    driver.key(ord('C'), 'down')
    driver.key(ord('C'), 'up')

    assert hits == ['match']


def test_hook_bind_logical_text_sequence_repeat_policy_runtime(runtime_env):
    LogicalConfig = runtime_env.types.LogicalConfig
    OsKeyRepeatPolicy = runtime_env.types.OsKeyRepeatPolicy
    BindConfig = runtime_env.types.BindConfig
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_logical(
        'a,a,a',
        lambda: hits.append('logical'),
        config=BindConfig(trigger=Trigger.ON_SEQUENCE),
        logical_config=LogicalConfig(os_key_repeat_policy=OsKeyRepeatPolicy.MATCH),
    )
    hook.bind_logical(
        'b,b,b',
        lambda: hits.append('reset'),
        config=BindConfig(trigger=Trigger.ON_SEQUENCE),
        logical_config=LogicalConfig(os_key_repeat_policy=OsKeyRepeatPolicy.RESET),
    )

    driver.key(ord('A'), 'down')
    driver.key(ord('A'), 'down')
    driver.key(ord('A'), 'down')
    driver.key(ord('A'), 'up')

    driver.key(ord('B'), 'down')
    driver.key(ord('B'), 'down')
    driver.key(ord('B'), 'down')
    driver.key(ord('B'), 'up')

    assert hits == ['logical']


def test_hook_add_abbreviation_replacement_policies_runtime(runtime_env):
    LogicalConfig = runtime_env.types.LogicalConfig
    ReplacementPolicy = runtime_env.types.ReplacementPolicy

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)

    hook.add_abbreviation('omw', 'on my way', logical_config=LogicalConfig(replacement_policy=ReplacementPolicy.MINIMAL_DIFF))
    for vk in (ord('O'), ord('M'), ord('W')):
        _tap_key(driver, vk)
    assert runtime_env.translate.sent_backspaces == [2]
    assert runtime_env.translate.sent_unicode_text == ['n my way']

    runtime_env.translate.sent_backspaces.clear()
    runtime_env.translate.sent_unicode_text.clear()

    hook.add_abbreviation('def', 'define', logical_config=LogicalConfig(replacement_policy=ReplacementPolicy.APPEND_SUFFIX))
    for vk in (ord('D'), ord('E'), ord('F')):
        _tap_key(driver, vk)
    assert runtime_env.translate.sent_backspaces == [0]
    assert runtime_env.translate.sent_unicode_text == ['ine']

    runtime_env.translate.sent_backspaces.clear()
    runtime_env.translate.sent_unicode_text.clear()

    hook.add_abbreviation('abc', 'xyz', logical_config=LogicalConfig(replacement_policy=ReplacementPolicy.REPLACE_ALL))
    for vk in (ord('A'), ord('B'), ord('C')):
        _tap_key(driver, vk)
    assert runtime_env.translate.sent_backspaces == [3]
    assert runtime_env.translate.sent_unicode_text == ['xyz']


def test_hook_add_abbreviation_ignores_injected_input_by_default_runtime(runtime_env):
    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    callbacks = []

    hook.add_abbreviation('ty', 'thank you', lambda: callbacks.append('expanded'))

    _tap_key(driver, ord('T'), injected=True)
    _tap_key(driver, ord('Y'), injected=True)
    assert callbacks == []
    assert runtime_env.translate.sent_backspaces == []
    assert runtime_env.translate.sent_unicode_text == []

    _tap_key(driver, ord('T'))
    _tap_key(driver, ord('Y'))
    assert callbacks == ['expanded']
    assert runtime_env.translate.sent_backspaces == [1]
    assert runtime_env.translate.sent_unicode_text == ['hank you']


def test_hook_bind_mouse_repeat_stops_after_pause_runtime(runtime_env):
    MouseBindConfig = runtime_env.types.MouseBindConfig
    Timing = runtime_env.types.Timing
    Trigger = runtime_env.types.Trigger

    hook = runtime_env.make_hook()
    driver = runtime_env.HookDriver(runtime_env, hook)
    hits = []

    hook.bind_mouse(
        'x2',
        lambda: hits.append(time.monotonic()),
        config=MouseBindConfig(
            trigger=Trigger.ON_REPEAT,
            timing=Timing(hold_ms=0, repeat_delay_ms=5, repeat_interval_ms=10),
        ),
    )

    driver.mouse('x2', 'down')
    assert _wait_until(lambda: len(hits) >= 1)
    hook.pause()
    frozen = len(hits)
    time.sleep(0.05)
    assert len(hits) == frozen
