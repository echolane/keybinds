from __future__ import annotations

import threading
import traceback
from typing import Any, Callable, Coroutine, Optional, TYPE_CHECKING

from .diagnostics import _NULL_DISPATCH_TRACE, _DispatchTrace

if TYPE_CHECKING:
    import asyncio
    from concurrent.futures import Future


def _default_on_async_error(exc: BaseException) -> None:
    print("keybinds: async callback raised an exception:")
    traceback.print_exception(type(exc), exc, exc.__traceback__)


class _AsyncLoopThread:
    """Lazy asyncio loop runner."""

    def __init__(
        self,
        loop: "Optional[asyncio.AbstractEventLoop]" = None,
        *,
        on_async_error: Optional[Callable[[BaseException], None]] = None,
        thread_name: str = "keybinds-asyncio",
    ) -> None:
        self._own_loop = loop is None
        self._loop = loop  # if None and needed, we'll create
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._stopped = False
        self._lock = threading.Lock()
        self._thread_name = thread_name
        self._on_async_error = on_async_error or _default_on_async_error

    @property
    def loop(self) -> "Optional[asyncio.AbstractEventLoop]":
        return self._loop

    def _run(self) -> None:
        import asyncio
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

        # best-effort cleanup
        try:
            pending = asyncio.all_tasks(self._loop)
            for t in pending:
                t.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        try:
            self._loop.close()
        except Exception:
            pass

    def _ensure_started(self) -> None:
        if not self._own_loop:
            # user-provided loop: assume running
            return
        if self._started:
            return

        with self._lock:
            if self._started or self._stopped:
                return

            import asyncio
            if self._loop is None:
                self._loop = asyncio.new_event_loop()

            self._thread = threading.Thread(
                target=self._run,
                name=self._thread_name,
                daemon=True,
            )
            self._thread.start()
            self._started = True

    def submit(self, coro: Coroutine[Any, Any, Any], trace: Optional[_DispatchTrace] = None) -> Future:
        import asyncio
        self._ensure_started()
        assert self._loop is not None
        if trace is None:
            trace = _NULL_DISPATCH_TRACE
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)

        def _done(done_fut: Future) -> None:
            self._done_callback(done_fut, trace)

        fut.add_done_callback(_done)
        return fut

    def _done_callback(self, fut: Future, trace: _DispatchTrace) -> None:
        try:
            exc = fut.exception()
        except Exception:
            return
        if exc is not None:
            trace.async_error(exc)
            try:
                self._on_async_error(exc)
            except Exception:
                pass
        else:
            trace.async_finished()

    def stop(self) -> None:
        if not self._own_loop:
            return
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
        if not self._started or self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass
