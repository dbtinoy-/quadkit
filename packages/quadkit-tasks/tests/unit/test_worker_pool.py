"""Tests for worker-pool service wiring."""

from unittest.mock import AsyncMock, patch

import pytest

from quadkit.tasks.dlq.core import DeadLetterQueue
from quadkit.tasks.execution.pool import WorkerPool
from quadkit.tasks.execution.worker import TaskWorker
from quadkit.tasks.middleware.core import (
    TaskExecutionContext,
    TaskMiddleware,
)


class _MarkerMiddleware(TaskMiddleware):
    """Middleware that records that it ran on each worker."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def before_execute(self, ctx: TaskExecutionContext) -> None:
        self.calls.append(ctx.job.id)


async def _noop_handler(**kwargs) -> None:
    return None


@pytest.mark.asyncio
async def test_worker_pool_injects_default_dead_letter_queue() -> None:
    """WorkerPool should give each worker a DLQ instead of the re-enqueue fallback."""

    queue = AsyncMock()
    pool = WorkerPool(queue, handler_registry={}, size=1)

    with patch.object(TaskWorker, "start", new=AsyncMock()):
        await pool.start()

    assert isinstance(pool.workers[0].dlq, DeadLetterQueue)


@pytest.mark.asyncio
async def test_worker_pool_forwards_middleware_pipeline() -> None:
    """WorkerPool should propagate the middleware pipeline to its workers."""
    from quadkit.tasks.backends.memory import MemoryTaskQueue
    from quadkit.tasks.middleware.core import TaskMiddlewarePipeline

    marker = _MarkerMiddleware()
    pipeline = TaskMiddlewarePipeline()
    pipeline.add(marker)

    queue = MemoryTaskQueue()
    pool = WorkerPool(
        queue,
        {"echo": _noop_handler},
        size=1,
        middleware_pipeline=pipeline,
    )
    await pool.start()
    try:
        assert len(pool.workers) == 1
        assert marker in pool.workers[0]._middleware._middleware  # noqa: SLF001
    finally:
        await pool.stop()
