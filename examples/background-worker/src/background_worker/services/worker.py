"""Convention followed: **Service pattern** — the queue and its consumer
live behind plain classes started/stopped by the provider lifecycle; the
same phases you would use to connect to a real broker later.

Work queue and bounded-concurrency engine for the Background Worker demo.
"""

from __future__ import annotations

import asyncio
from typing import Any


class TaskQueue:
    """In-process work queue with simple counters."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.enqueued = 0
        self.processed = 0
        self.failed = 0

    def submit(self, payload: dict[str, Any]) -> None:
        """Enqueue one unit of work (never blocks; the queue is unbounded)."""
        self._queue.put_nowait(payload)
        self.enqueued += 1

    async def next(self, timeout: float) -> dict[str, Any]:
        """Await the next task, raising ``TimeoutError`` after ``timeout``."""
        return await asyncio.wait_for(self._queue.get(), timeout=timeout)

    def pending(self) -> int:
        """Return how many tasks are waiting right now."""
        return self._queue.qsize()


class WorkerEngine:
    """Consumes tasks off the queue with a bounded concurrency pool."""

    def __init__(
        self, queue: TaskQueue, concurrency: int = 2, poll_timeout: float = 0.05
    ) -> None:
        self._queue = queue
        self._concurrency = concurrency
        self._poll_timeout = poll_timeout
        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()

    async def _process(self, payload: dict[str, Any]) -> None:
        # Failure injection for demos/tests: {"fail": true} raises, the
        # worker records it and keeps consuming subsequent tasks.
        if payload.get("fail") is True:
            raise RuntimeError("injected task failure")
        # Simulate real work; replace with your domain call.
        await asyncio.sleep(float(payload.get("duration", 0.05)))

    async def _loop(self, worker_id: int) -> None:
        while not self._stopping.is_set():
            try:
                payload = await self._queue.next(self._poll_timeout)
            except TimeoutError:
                continue
            try:
                await self._process(payload)
                self._queue.processed += 1
            except Exception:
                self._queue.failed += 1

    def start(self) -> None:
        """Spawn the bounded pool of worker coroutines."""
        for worker_id in range(self._concurrency):
            self._tasks.append(asyncio.create_task(self._loop(worker_id)))

    async def stop(self) -> None:
        """Signal stop, cancel the pool, and drain the tasks."""
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()


__all__ = ["TaskQueue", "WorkerEngine"]
