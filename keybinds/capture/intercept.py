import asyncio
import queue
import threading
from typing import AsyncIterator, Iterator, Optional, Union

from .config import InterceptAction, InterceptConfig
from .models import CapturedKey, CapturedMouse


class InterceptedKey(CapturedKey):
    """Captured key whose propagation can be resolved by the consumer."""

    def __init__(self, key: CapturedKey, timeout: float, default: InterceptAction):
        super().__init__(
            key.vk,
            key.scan_code,
            key.token,
            key.char,
            key.action,
            key.is_modifier,
            key.injected,
            key.timestamp,
        )
        object.__setattr__(self, "_action", default)
        object.__setattr__(self, "_done_event", threading.Event())
        object.__setattr__(self, "_state_lock", threading.Lock())
        object.__setattr__(self, "is_resolved", False)
        object.__setattr__(self, "timed_out", False)
        object.__setattr__(self, "_timeout", timeout)

    def accept(self) -> None:
        self._resolve(InterceptAction.PASS)

    def suppress(self) -> None:
        self._resolve(InterceptAction.SUPPRESS)

    def _resolve(self, action: InterceptAction) -> None:
        with self._state_lock:
            if not self.is_resolved and not self.timed_out:
                object.__setattr__(self, "_action", action)
                object.__setattr__(self, "is_resolved", True)
                self._done_event.set()

    def _expire(self) -> bool:
        with self._state_lock:
            if self.is_resolved:
                return False
            object.__setattr__(self, "timed_out", True)
            return True


class InterceptedMouse(CapturedMouse):
    """Captured mouse event whose propagation can be resolved by the consumer."""

    def __init__(self, mouse: CapturedMouse, default: InterceptAction):
        super().__init__(
            mouse.button,
            mouse.action,
            mouse.x,
            mouse.y,
            mouse.wheel_delta,
            mouse.injected,
            mouse.timestamp,
        )
        object.__setattr__(self, "_action", default)
        object.__setattr__(self, "_done_event", threading.Event())
        object.__setattr__(self, "_state_lock", threading.Lock())
        object.__setattr__(self, "is_resolved", False)
        object.__setattr__(self, "timed_out", False)

    def accept(self) -> None:
        self._resolve(InterceptAction.PASS)

    def suppress(self) -> None:
        self._resolve(InterceptAction.SUPPRESS)

    def _resolve(self, action: InterceptAction) -> None:
        with self._state_lock:
            if not self.is_resolved and not self.timed_out:
                object.__setattr__(self, "_action", action)
                object.__setattr__(self, "is_resolved", True)
                self._done_event.set()

    def _expire(self) -> bool:
        with self._state_lock:
            if self.is_resolved:
                return False
            object.__setattr__(self, "timed_out", True)
            return True


class InterceptStream:
    """Synchronous and asynchronous stream for intercepted input events."""

    def __init__(
        self,
        hook,
        config: Optional[InterceptConfig] = None,
        keyboard: bool = True,
        mouse: bool = False,
    ) -> None:
        self._hook = hook
        self._config = config or InterceptConfig()
        self.keyboard = keyboard
        self.mouse = mouse
        self._channel = queue.Queue(maxsize=1)
        self._closed = threading.Event()
        self._current_event = None
        self._pressed = set()
        self._pressed_mouse = set()
        self._entered = False
        self._lifecycle_lock = threading.Lock()

    def __enter__(self) -> "InterceptStream":
        if self._closed.is_set():
            raise RuntimeError("A closed interceptor cannot be entered")
        if self._entered:
            return self
        self._entered = True
        try:
            if self._config.pause_binds:
                self._hook.pause()
            self._hook._register_interceptor(self)
        except Exception:
            if self._config.pause_binds:
                self._hook.resume()
            self._entered = False
            raise
        return self

    def __exit__(self, *args) -> None:
        self.close()

    async def __aenter__(self) -> "InterceptStream":
        return self.__enter__()

    async def __aexit__(self, *args) -> None:
        self.close()

    def __iter__(self) -> Iterator[Union[InterceptedKey, InterceptedMouse]]:
        while not self._closed.is_set():
            try:
                event = self._channel.get(timeout=0.05)
            except queue.Empty:
                continue
            if event is None:
                break
            self._current_event = event
            try:
                yield event
            finally:
                if not event.is_resolved and not event.timed_out:
                    event.accept()
                self._current_event = None

    def __aiter__(self) -> AsyncIterator[Union[InterceptedKey, InterceptedMouse]]:
        return self._iterate_events()

    async def _iterate_events(self):
        loop = asyncio.get_running_loop()
        while not self._closed.is_set():
            try:
                event = await loop.run_in_executor(
                    None, self._channel.get, True, 0.05
                )
            except queue.Empty:
                continue
            if event is None:
                break
            self._current_event = event
            try:
                yield event
            finally:
                self._finish_event(event)

    def _finish_event(self, event) -> None:
        if not event.is_resolved and not event.timed_out:
            event.accept()
        self._current_event = None

    def is_pressed(self, token: str) -> bool:
        if isinstance(token, str) and token.lower() in {
            "left", "right", "middle", "x1", "x2"
        }:
            return token.lower() in self._pressed_mouse
        from .convert import token_to_vks

        try:
            return all(
                bool(token_to_vks(part.strip()) & self._pressed)
                for part in token.split("+")
            )
        except ValueError:
            return False

    def handle_event(self, key: Union[CapturedKey, CapturedMouse]) -> int:
        with self._lifecycle_lock:
            if self._closed.is_set():
                return self._default_result()
            if isinstance(key, CapturedKey):
                event = InterceptedKey(
                    key, self._config.hook_timeout, self._config.default_action
                )
                if key.action == "press":
                    self._pressed.add(key.vk)
                elif key.action == "release":
                    self._pressed.discard(key.vk)
            else:
                event = InterceptedMouse(key, self._config.default_action)
                if key.action == "press":
                    self._pressed_mouse.add(key.button)
                elif key.action == "release":
                    self._pressed_mouse.discard(key.button)

            try:
                self._channel.put_nowait(event)
            except queue.Full:
                return self._default_result()

        if not event._done_event.wait(self._config.hook_timeout) and event._expire():
            return self._default_result()
        return 4 if event._action == InterceptAction.SUPPRESS else 0

    def _default_result(self) -> int:
        return 4 if self._config.default_action == InterceptAction.SUPPRESS else 0

    def close(self) -> None:
        with self._lifecycle_lock:
            if self._closed.is_set():
                return
            self._closed.set()
            if self._current_event and not self._current_event.is_resolved:
                self._current_event.accept()
            while True:
                try:
                    pending_event = self._channel.get_nowait()
                except queue.Empty:
                    break
                if pending_event is not None and not pending_event.is_resolved:
                    pending_event.accept()
            try:
                self._channel.put_nowait(None)
            except queue.Full:
                pass
        self._hook._unregister_interceptor(self)
        if self._entered and self._config.pause_binds:
            self._hook.resume()
        self._entered = False
