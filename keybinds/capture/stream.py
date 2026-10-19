import asyncio
import queue
import threading
from typing import AsyncIterator, Iterator, Optional, Union

from .config import CaptureConfig, SuppressFilter
from .models import CapturedChord, CapturedKey


class KeyStream:
    """Context manager and iterator for captured keyboard events."""

    _device = "keyboard"

    def __init__(
        self,
        hook,
        suppress: SuppressFilter = False,
        config: Optional[CaptureConfig] = None,
    ) -> None:
        self.hook = hook
        self.config = config or CaptureConfig(pause_binds=False)
        self.suppress = suppress
        self._queue = queue.Queue()
        self._closed = False
        self._pressed = {}
        self._lock = threading.RLock()
        self._initial_pressed = set()
        self._initial_mouse = set()
        self._paused_hook = False
        self._entered = False

    def __enter__(self) -> "KeyStream":
        if self._closed:
            raise RuntimeError("A stopped input stream cannot be entered")
        if self._entered:
            return self
        self._entered = True
        try:
            if self.config.pause_binds:
                self.hook.pause()
                self._paused_hook = True
            self.hook._register_capture(self)
        except Exception:
            if self._paused_hook:
                self._paused_hook = False
                self.hook.resume()
            self._entered = False
            raise
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    async def __aenter__(self) -> "KeyStream":
        return self.__enter__()

    async def __aexit__(self, *args) -> None:
        self.stop()

    def __iter__(self) -> Iterator[CapturedKey]:
        while not self._closed:
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                break
            yield item

    def get(self, timeout: Optional[float] = None):
        return self._queue.get(timeout=timeout)

    def __aiter__(self) -> AsyncIterator[CapturedKey]:
        return self

    async def __anext__(self) -> CapturedKey:
        loop = asyncio.get_running_loop()
        while True:
            if self._closed:
                raise StopAsyncIteration
            item = await loop.run_in_executor(None, self._queue.get)
            if item is None:
                raise StopAsyncIteration
            return item

    def is_pressed(self, expr_or_token: Union[str, int]) -> bool:
        from .convert import token_to_vks

        with self._lock:
            if isinstance(expr_or_token, int):
                return expr_or_token in self._pressed
            try:
                return all(
                    bool(token_to_vks(part.strip()) & self._pressed.keys())
                    for part in expr_or_token.split("+")
                )
            except ValueError:
                return False

    def any_pressed(self, tokens) -> bool:
        return any(self.is_pressed(token) for token in tokens)

    def pressed_keys(self) -> tuple:
        with self._lock:
            return tuple(self._pressed.values())

    def current_chord(self) -> CapturedChord:
        return CapturedChord(self.pressed_keys())

    def handle_event(self, key: CapturedKey) -> int:
        from ..types import InjectedPolicy

        policy = self.config.injected
        if policy == InjectedPolicy.IGNORE and key.injected:
            return 0
        if policy == InjectedPolicy.ONLY and not key.injected:
            return 0
        if key.vk in self._initial_pressed:
            if key.action == "release":
                self._initial_pressed.discard(key.vk)
            return 0
        if not self.hook._capture_target_matches(self.config.hwnd):
            return 0

        with self._lock:
            if key.action == "press":
                self._pressed[key.vk] = key
            elif key.action == "repeat":
                self._pressed.setdefault(key.vk, key)
            else:
                self._pressed.pop(key.vk, None)

        if key.action != "repeat" or self.config.include_repeats:
            self._queue.put(key)
        return 4 if _should_suppress(self.suppress, key) else 0

    def stop(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.hook._unregister_capture(self)
        self._queue.put(None)
        if self._paused_hook:
            self._paused_hook = False
            self.hook.resume()
        self._entered = False


class MouseStream(KeyStream):
    """Context manager and iterator for captured mouse events."""

    _device = "mouse"


def _should_suppress(policy, event) -> bool:
    if policy is False or policy is None:
        return False
    if policy is True:
        return True
    if callable(policy):
        return bool(policy(event))
    return str(event) in {str(item).lower() for item in policy}
