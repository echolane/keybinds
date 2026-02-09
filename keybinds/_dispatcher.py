from __future__ import annotations

import queue
import threading
from traceback import print_exc
from typing import Callable, List, Optional


class _CallbackDispatcher:
    """Executes user callbacks on a small worker pool.

    Critical for low-level hooks: do *not* create a new Thread per event.
    """

    def __init__(self, workers: int = 1) -> None:
        self._q: "queue.SimpleQueue[Optional[Callable[[], None]]]" = queue.SimpleQueue()
        self._threads: List[threading.Thread] = []
        self._workers = max(1, int(workers))
        for i in range(self._workers):
            t = threading.Thread(target=self._worker, name=f"bind-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)

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
                fn()
            except Exception:
                # never let user callbacks kill the worker
                print_exc()
