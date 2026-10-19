import queue
import time
from typing import Iterator, Optional

from ..types import TextBackspacePolicy
from .stream import KeyStream


class TextAccumulator:
    """Collect characters and apply the configured Backspace behavior."""

    def __init__(
        self,
        backspace_policy: TextBackspacePolicy = TextBackspacePolicy.EDIT_BUFFER,
    ) -> None:
        self._text = []
        self.policy = backspace_policy

    def feed(self, key) -> Optional[str]:
        if key.action not in ("press", "repeat"):
            return None
        if key.token == "backspace":
            if self.policy == TextBackspacePolicy.IGNORE:
                return None
            if self.policy == TextBackspacePolicy.CLEAR_BUFFER:
                self._text.clear()
                return ""
            if self.policy == TextBackspacePolicy.CLEAR_WORD:
                while self._text and self._text[-1].isspace():
                    self._text.pop()
                while self._text and not self._text[-1].isspace():
                    self._text.pop()
                return ""
            if self._text:
                self._text.pop()
                return ""
            return None
        if key.char:
            self._text.append(key.char)
            return key.char
        return None

    def get_text(self) -> str:
        return "".join(self._text)

    def clear(self) -> None:
        self._text.clear()


class TextStream:
    """Yield the current text buffer as captured characters arrive."""

    def __init__(
        self,
        hook,
        until: str = "enter",
        cancel_key: Optional[str] = "esc",
        suppress=True,
        backspace_policy: TextBackspacePolicy = TextBackspacePolicy.EDIT_BUFFER,
        timeout: Optional[float] = None,
        config=None,
        **kwargs
    ) -> None:
        from .config import CaptureConfig

        self.hook = hook
        self.until = until
        self.cancel_key = cancel_key
        self.stream = hook.stream_keys(
            suppress=suppress, config=config or CaptureConfig()
        )
        self.accumulator = TextAccumulator(backspace_policy)
        self.text = ""
        self.cancelled = False
        self.timeout = timeout

    def __enter__(self) -> "TextStream":
        self.stream.__enter__()
        return self

    def __exit__(self, *args) -> None:
        self.stream.__exit__(*args)

    def __iter__(self) -> Iterator[str]:
        deadline = None if self.timeout is None else time.monotonic() + self.timeout
        while True:
            wait_timeout = (
                None if deadline is None else max(0, deadline - time.monotonic())
            )
            try:
                event = self.stream.get(wait_timeout)
            except queue.Empty:
                return
            if event is None:
                return
            if event.action not in ("press", "repeat"):
                continue
            if self.cancel_key and event == self.cancel_key:
                self.cancelled = True
                break
            if event == self.until:
                break
            self.accumulator.feed(event)
            self.text = self.accumulator.get_text()
            yield self.text

    @property
    def result(self) -> Optional[str]:
        return None if self.cancelled else self.text


def read_text(hook, **kwargs) -> Optional[str]:
    with TextStream(hook, **kwargs) as stream:
        for _ in stream:
            pass
    return stream.result
