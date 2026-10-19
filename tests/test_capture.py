from __future__ import annotations

import asyncio
import importlib
from typing import Iterable, Optional

import pytest


class FakeCaptureHook:
    """Small hook double that feeds configured events into capture sessions."""

    def __init__(self, events: Optional[Iterable[object]] = None) -> None:
        self.events = list(events or ())
        self.pause_count = 0
        self.resume_count = 0
        self.capture_sessions = []
        self.interceptors = []

    def pause(self) -> None:
        self.pause_count += 1

    def resume(self) -> None:
        self.resume_count += 1

    def _register_capture(self, session) -> None:
        self.capture_sessions.append(session)
        for event in self.events:
            if session._device == "keyboard":
                session.handle_event(event)
            else:
                session._queue.put(event)

    def _unregister_capture(self, session) -> None:
        self.capture_sessions.remove(session)

    def _capture_target_matches(self, hwnd) -> bool:
        return True

    def _register_interceptor(self, interceptor) -> None:
        self.interceptors.append(interceptor)

    def _unregister_interceptor(self, interceptor) -> None:
        self.interceptors.remove(interceptor)

    def stream_keys(self, suppress=False, config=None):
        capture = importlib.import_module("keybinds.capture")
        return capture.KeyStream(self, suppress=suppress, config=config)

    def stream_mouse(self, suppress=False, config=None):
        capture = importlib.import_module("keybinds.capture")
        return capture.MouseStream(self, suppress=suppress, config=config)

    def stream_text(self, **kwargs):
        capture = importlib.import_module("keybinds.capture")
        return capture.TextStream(self, **kwargs)

    def intercept(self, keyboard=True, mouse=False, config=None):
        capture = importlib.import_module("keybinds.capture")
        return capture.InterceptStream(
            self, config=config, keyboard=keyboard, mouse=mouse
        )

    def capture_key(self, *args, **kwargs):
        recorder = importlib.import_module("keybinds.capture.recorder")
        return recorder.capture_key(self, *args, **kwargs)

    def capture_chord(self, *args, **kwargs):
        recorder = importlib.import_module("keybinds.capture.recorder")
        return recorder.capture_chord(self, *args, **kwargs)

    def capture_mouse(self, *args, **kwargs):
        recorder = importlib.import_module("keybinds.capture.recorder")
        return recorder.capture_mouse(self, *args, **kwargs)


@pytest.fixture
def capture_api(kb_env):
    capture = importlib.import_module("keybinds.capture")
    return capture


def key_event(capture_api, vk, token, action="press", char=None, modifier=False):
    return capture_api.CapturedKey(
        vk=vk,
        scan_code=vk,
        token=token,
        char=char,
        action=action,
        is_modifier=modifier,
        injected=False,
        timestamp=1.0,
    )


def mouse_event(capture_api, button="left", action="press", delta=0):
    return capture_api.CapturedMouse(
        button=button,
        action=action,
        x=120,
        y=240,
        wheel_delta=delta,
        injected=False,
        timestamp=1.0,
    )


def test_capture_chord_returns_physical_and_logical_expressions(capture_api):
    hook = FakeCaptureHook(
        [
            key_event(capture_api, 0x11, "ctrl", modifier=True),
            key_event(capture_api, 0x52, "r", char="r"),
        ]
    )

    chord = hook.capture_chord(suppress=False)

    assert chord.physical_expr == "ctrl+r"
    assert chord.logical_expr == "ctrl+r"
    assert chord.tokens == ("ctrl", "r")
    assert chord.vks == frozenset((0x11, 0x52))
    assert chord.modifiers == ("ctrl",)
    assert hook.pause_count == hook.resume_count == 1


def test_capture_key_returns_none_when_cancel_key_is_pressed(capture_api):
    hook = FakeCaptureHook([key_event(capture_api, 0x1B, "esc")])

    assert hook.capture_key(suppress=False) is None
    assert hook.pause_count == hook.resume_count == 1


def test_capture_mouse_returns_button_event(capture_api):
    expected = mouse_event(capture_api, "left")
    hook = FakeCaptureHook([expected])

    captured = hook.capture_mouse(suppress=False)

    assert captured == "left"
    assert captured.action == "press"


def test_keyboard_stream_observes_events_without_pausing_binds(capture_api):
    hook = FakeCaptureHook(
        [key_event(capture_api, 0x52, "r", char="r"), key_event(capture_api, 0x1B, "esc")]
    )

    with hook.stream_keys() as stream:
        events = []
        for event in stream:
            events.append(event)
            if event == "esc":
                break

    assert [event.token for event in events] == ["r", "esc"]
    assert hook.pause_count == 0
    assert hook.capture_sessions == []


def test_stream_can_suppress_selected_key(capture_api):
    hook = FakeCaptureHook()
    stream = hook.stream_keys(suppress={"r"})
    event = key_event(capture_api, 0x52, "r", char="r")

    with stream:
        assert stream.handle_event(event) == 4


def test_mouse_stream_yields_button_and_wheel_details(capture_api):
    hook = FakeCaptureHook(
        [mouse_event(capture_api, "left"), mouse_event(capture_api, "wheel_up", "scroll", 120)]
    )

    with hook.stream_mouse() as stream:
        events = []
        for event in stream:
            events.append(event)
            if event.action == "scroll":
                break

    assert [(event.button, event.action) for event in events] == [
        ("left", "press"),
        ("wheel_up", "scroll"),
    ]
    assert events[1].wheel_delta == 120


def test_event_models_compare_with_user_facing_values(capture_api):
    key = key_event(capture_api, 0x52, "r", char="R")
    mouse = mouse_event(capture_api, "left")

    assert key == "r"
    assert key == "R"
    assert key == 0x52
    assert key.is_printable is True
    assert mouse == "left"


def test_text_accumulator_handles_repeat_and_backspace(capture_api, kb_env):
    policy = kb_env.types.TextBackspacePolicy
    accumulator = capture_api.TextAccumulator(policy.EDIT_BUFFER)

    assert accumulator.feed(key_event(capture_api, 0x41, "a", char="a")) == "a"
    assert accumulator.feed(
        key_event(capture_api, 0x42, "b", action="repeat", char="b")
    ) == "b"
    assert accumulator.get_text() == "ab"
    assert accumulator.feed(key_event(capture_api, 0x08, "backspace")) == ""
    assert accumulator.get_text() == "a"


def test_text_stream_includes_repeats_only_when_enabled(capture_api):
    events = [
        key_event(capture_api, 0x41, "a", char="a"),
        key_event(capture_api, 0x41, "a", action="repeat", char="a"),
        key_event(capture_api, 0x0D, "enter"),
    ]

    default_hook = FakeCaptureHook(events)
    with default_hook.stream_text() as stream:
        default_values = list(stream)

    repeat_hook = FakeCaptureHook(events)
    config = capture_api.CaptureConfig(include_repeats=True, pause_binds=False)
    with repeat_hook.stream_text(config=config) as stream:
        repeat_values = list(stream)

    assert default_values == ["a"]
    assert repeat_values == ["a", "aa"]
    assert stream.result == "aa"


def test_stream_context_managers_support_async_iteration(capture_api):
    hook = FakeCaptureHook([key_event(capture_api, 0x52, "r", char="r")])

    async def scenario():
        received = []
        async with hook.stream_keys() as stream:
            async for event in stream:
                received.append(event.token)
                break
        return received

    assert asyncio.run(scenario()) == ["r"]
    assert hook.pause_count == 0
    assert hook.capture_sessions == []


def test_async_intercept_allows_consumer_to_suppress_event(capture_api):
    hook = FakeCaptureHook()
    intercepted = key_event(capture_api, 0x52, "r", char="r")

    async def scenario():
        loop = asyncio.get_running_loop()
        with hook.intercept(keyboard=True, mouse=False) as stream:
            pending = loop.run_in_executor(None, stream.handle_event, intercepted)
            async for event in stream:
                event.suppress()
                break
            return await asyncio.wait_for(pending, timeout=1)

    assert asyncio.run(scenario()) == 4
    assert hook.interceptors == []


def test_async_intercept_auto_accepts_event_when_context_exits(capture_api):
    hook = FakeCaptureHook()
    intercepted = mouse_event(capture_api, "left")

    async def scenario():
        loop = asyncio.get_running_loop()
        async with hook.intercept(keyboard=False, mouse=True) as stream:
            pending = loop.run_in_executor(None, stream.handle_event, intercepted)
            async for event in stream:
                assert event == "left"
                break
            return await asyncio.wait_for(pending, timeout=1)

    assert asyncio.run(scenario()) == 0
    assert hook.interceptors == []


def test_intercept_uses_default_action_after_timeout(capture_api):
    hook = FakeCaptureHook()
    config = capture_api.InterceptConfig(
        hook_timeout=0.01,
        default_action=capture_api.InterceptAction.SUPPRESS,
    )
    stream = hook.intercept(config=config)
    event = key_event(capture_api, 0x52, "r", char="r")

    with stream:
        assert stream.handle_event(event) == 4
