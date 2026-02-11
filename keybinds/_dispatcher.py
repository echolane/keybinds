from __future__ import annotations

import queue
import threading
from traceback import print_exc
from typing import Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio


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
        self._q: "queue.SimpleQueue[Optional[Callable[[], None]]]" = queue.SimpleQueue()
        self._threads: List[threading.Thread] = []
        self._workers = max(1, int(workers))
        for i in range(self._workers):
            t = threading.Thread(target=self._worker, name=f"bind-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)

        self._async_loop: "Optional[asyncio.AbstractEventLoop]" = asyncio_loop
        self._on_async_error: Optional[Callable[[BaseException], None]] = on_async_error
        self._async = None  # lazy

    def _submit_awaitable(self, aw) -> None:
        if self._async is None:
            from ._async import _AsyncLoopThread
            self._async = _AsyncLoopThread(self._async_loop, on_async_error=self._on_async_error)
        self._async.submit(aw)

    def submit(self, fn: Callable[[], None]) -> None:
        self._q.put(fn)

    def stop(self) -> None:
        for _ in range(self._workers):
            self._q.put(None)

    def _worker(self) -> None:
        while True:
            fn = self._q.get()
            if fn is None:
                return
            try:
                res = fn()
                if _is_awaitable(res):
                    self._submit_awaitable(res)
            except Exception:
                # never let user callbacks kill the worker
                print_exc()
