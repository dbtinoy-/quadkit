"""Daemon-thread executor transport shared by the Bedrock client.

The synchronous ``boto3`` calls issued by :class:`~quadkit.ai.llm.clients.aws_bedrock.BedrockClient`
run in a small shared thread pool so the event loop is never blocked. The
pool uses daemon workers so it never blocks interpreter shutdown or trips
test teardown assertions.
"""

from __future__ import annotations

import atexit
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.thread import _threads_queues, _worker
import threading
from typing import Any
import weakref

__all__ = ["get_thread_pool"]

_thread_pool: ThreadPoolExecutor | None = None


class _DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor whose workers are daemon threads.

    Keeps the pool off the non-daemon thread list so it never blocks
    interpreter shutdown or trips test teardown assertions. Mirrors the
    CPython 3.13 worker-spawn logic with ``daemon=True``.
    """

    def _adjust_thread_count(self) -> None:
        if self._idle_semaphore.acquire(timeout=0):
            return

        def weakref_cb(_: Any, q: Any = self._work_queue) -> None:
            q.put(None)

        num_threads = len(self._threads)
        if num_threads < self._max_workers:
            thread_name = f"{self._thread_name_prefix or self}_{num_threads}"
            t = threading.Thread(
                name=thread_name,
                target=_worker,
                args=(
                    weakref.ref(self, weakref_cb),
                    self._work_queue,
                    self._initializer,
                    self._initargs,
                ),
                daemon=True,
            )
            t.start()
            self._threads.add(t)  # type: ignore[attr-defined]
            _threads_queues[t] = self._work_queue  # type: ignore[index]


def get_thread_pool() -> ThreadPoolExecutor:
    """Get the shared executor, creating it lazily on first use."""
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = _DaemonThreadPoolExecutor(
            max_workers=4, thread_name_prefix="bedrock-sync"
        )
        atexit.register(_thread_pool.shutdown)
    return _thread_pool
