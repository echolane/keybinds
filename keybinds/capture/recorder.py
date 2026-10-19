import queue
import time
from typing import Callable, Optional

from .config import CaptureConfig, ChordEndPolicy, SuppressFilter
from .models import CapturedChord, CapturedKey, CapturedMouse
from .stream import KeyStream, MouseStream


def capture_key(
    hook,
    suppress: SuppressFilter = True,
    timeout: Optional[float] = None,
    config: Optional[CaptureConfig] = None,
) -> Optional[CapturedKey]:
    capture_config = config or CaptureConfig()
    with KeyStream(hook, suppress, capture_config) as stream:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            wait_timeout = (
                None if deadline is None else max(0, deadline - time.monotonic())
            )
            try:
                event = stream.get(wait_timeout)
            except queue.Empty:
                return None
            if event is None:
                return None
            if event.action == "press":
                if capture_config.cancel_key and event == capture_config.cancel_key:
                    return None
                return event


def capture_chord(
    hook,
    suppress: SuppressFilter = True,
    timeout: Optional[float] = None,
    on_change: Optional[Callable[[CapturedChord], None]] = None,
    config: Optional[CaptureConfig] = None,
) -> Optional[CapturedChord]:
    capture_config = config or CaptureConfig()
    pressed = {}
    seen = {}
    start_time = time.monotonic()
    with KeyStream(hook, suppress, capture_config) as stream:
        while True:
            wait_timeout = (
                None
                if timeout is None
                else max(0, timeout - (time.monotonic() - start_time))
            )
            try:
                event = stream.get(wait_timeout)
            except queue.Empty:
                return None
            if event is None:
                return None

            if event.action == "press":
                if capture_config.cancel_key and event == capture_config.cancel_key:
                    return None
                pressed[event.vk] = event
                seen.setdefault(event.vk, event)
            elif event.action == "release":
                pressed.pop(event.vk, None)

            chord = CapturedChord(tuple(pressed.values()))
            if on_change is not None:
                on_change(chord)

            if (
                capture_config.end_policy == ChordEndPolicy.FIRST_NON_MODIFIER
                and event.action == "press"
                and not event.is_modifier
            ):
                return chord
            if (
                capture_config.end_policy == ChordEndPolicy.FIRST_RELEASED
                and event.action == "release"
            ):
                return CapturedChord(tuple(seen.values()))
            if (
                capture_config.end_policy == ChordEndPolicy.ALL_RELEASED
                and not pressed
                and seen
            ):
                return CapturedChord(tuple(seen.values()))


def capture_mouse(
    hook,
    suppress: SuppressFilter = True,
    timeout: Optional[float] = None,
    config: Optional[CaptureConfig] = None,
) -> Optional[CapturedMouse]:
    with MouseStream(hook, suppress, config or CaptureConfig()) as stream:
        try:
            return stream.get(None if timeout is None else max(0, timeout))
        except queue.Empty:
            return None
