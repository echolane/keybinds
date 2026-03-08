from __future__ import annotations

import queue
import threading
from traceback import print_exc
from typing import Any, Callable, List, Optional, Tuple, TYPE_CHECKING

from .types import Callback
from .diagnostics import _NULL_DISPATCH_TRACE, _DispatchTrace

if TYPE_CHECKING:
    import asyncio
    from ._async import _AsyncLoopThread


def _is_awaitable(obj) -> bool:
    return obj is not None and hasattr(obj, "__await__")


class _CallbackDispatcher:
    """Executes user callbacks on a small worker pool.

    Critical for low-level hooks: do *not* create a new Thread per event.
    """

    def __init__(
            self,
            workers: int = 1,
            asyncio_loop: "Optional[asyncio.AbstractEventLoop]" = None,
            on_async_error: Optional[Callable[[BaseException], None]] = None
    ) -> None:
        self._q: "queue.SimpleQueue[Optional[Tuple[Callback, _DispatchTrace]]]" = queue.SimpleQueue()
        self._threads: List[threading.Thread] = []
        self._workers = max(1, int(workers))

        self._async_loop: "Optional[asyncio.AbstractEventLoop]" = asyncio_loop
        self._on_async_error: Optional[Callable[[BaseException], None]] = on_async_error
        self._async: "Optional[_AsyncLoopThread]" = None  # lazy

        self._stopped: bool = False
        self.start()

    @property
    def asyncio_loop(self) -> "Optional[asyncio.AbstractEventLoop]":
        return self._async_loop or (self._async.loop if self._async is not None else None)

    @property
    def stopped(self) -> bool:
        return self._stopped

    def start(self) -> None:
        if self.stopped or not self._threads:
            self._stopped = False
            self._threads = []
            for i in range(self._workers):
                t = threading.Thread(target=self._worker, name="bind-worker-{0}".format(i), daemon=True)
                t.start()
                self._threads.append(t)

    def stop(self) -> None:
        if not self.stopped:
            self._stopped = True
            for _ in range(self._workers):
                self._q.put(None)

            self._threads.clear()

            if self._async is not None:
                self._async.stop()
                self._async = None

    def _submit_awaitable(self, aw: Any, trace: Optional[_DispatchTrace] = None) -> None:
        if self._async is None:
            from ._async import _AsyncLoopThread
            self._async = _AsyncLoopThread(self._async_loop, on_async_error=self._on_async_error)
        if trace is None:
            trace = _NULL_DISPATCH_TRACE
        trace.async_scheduled()
        self._async.submit(aw, trace=trace)

    def submit(self, fn: Callback, trace: Optional[_DispatchTrace] = None) -> None:
        if trace is None:
            trace = _NULL_DISPATCH_TRACE
        trace.queued()
        self._q.put((fn, trace))

    def _worker(self) -> None:
        while True:
            item: Optional[Tuple[Callback, _DispatchTrace]] = self._q.get()
            if item is None:
                return
            fn, trace = item
            if trace is None:
                trace = _NULL_DISPATCH_TRACE
            trace.started()
            try:
                res = fn()
                if _is_awaitable(res):
                    trace.returned_awaitable()
                    self._submit_awaitable(res, trace=trace)
                else:
                    trace.finished()
            except Exception as exc:
                trace.error(exc)
                # never let user callbacks kill the worker
                print_exc()
