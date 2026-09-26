"""Tests for sync handler execution, DLQ routing, and worker-loop resilience."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.tasks.execution.worker import TaskWorker
from quadkit.tasks.models.job import JobProtocol


@pytest.mark.asyncio
async def test_run_handler_supports_sync_handlers():
    """Sync handlers are executed correctly through the worker wrapper."""

    # Arrange
    def sync_handler(x):
        return x * 2

    worker = TaskWorker(
        "worker-1",
        queue=AsyncMock(),
        handler_registry={"double": sync_handler},
    )
    job = JobProtocol(id="job-1", name="double", args=(3,), max_retries=0)

    # Act
    result = await worker._run_handler(sync_handler, job)

    # Assert
    assert result == 6


@pytest.mark.asyncio
async def test_send_to_dlq_uses_enqueue_dlq_when_available():
    """Queues with DLQ support use their dedicated dead-letter path."""
    # Arrange
    queue = AsyncMock()
    queue.enqueue_dlq = AsyncMock()
    worker = TaskWorker("worker-1", queue, handler_registry={})

    job = JobProtocol(
        id="job-1",
        name="fail",
        args=(),
        kwargs={},
        priority=0,
        max_retries=0,
        status="failed",
        created_at=0,
        retry_count=3,
        last_error="boom",
    )

    # Act
    await worker._send_to_dlq(job)

    # Assert
    assert queue.enqueue_dlq.await_count == 1
    called_job = queue.enqueue_dlq.await_args.args[0]
    assert isinstance(called_job, JobProtocol)


@pytest.mark.asyncio
async def test_send_to_dlq_falls_back_to_enqueue_when_no_dlq_method():
    """Queues without DLQ helpers fall back to the standard enqueue method."""
    # Arrange
    # Create a queue mock that only exposes 'enqueue' (no 'enqueue_dlq')
    queue = AsyncMock(spec=["enqueue"])
    queue.enqueue = AsyncMock()
    worker = TaskWorker("worker-1", queue, handler_registry={})

    job = JobProtocol(
        id="job-2",
        name="fail2",
        args=(),
        kwargs={},
        priority=0,
        max_retries=0,
        status="failed",
        created_at=0,
        retry_count=2,
        last_error="boom2",
    )

    # Act
    await worker._send_to_dlq(job)

    # Assert
    assert queue.enqueue.await_count == 1
    called_job = queue.enqueue.await_args.args[0]
    assert isinstance(called_job, JobProtocol)


@pytest.mark.asyncio
async def test_work_loop_survives_unexpected_exception():
    """Unexpected dequeue failures are logged and do not kill the worker loop."""

    class UnexpectedWorkerError(Exception):
        pass

    queue = AsyncMock()
    dequeue_calls = 0

    worker = TaskWorker("worker-1", queue=queue, handler_registry={})
    worker.logger = MagicMock()
    worker.running = True

    async def dequeue_side_effect():
        nonlocal dequeue_calls
        dequeue_calls += 1
        if dequeue_calls == 1:
            raise UnexpectedWorkerError("boom")
        worker.running = False

    queue.dequeue.side_effect = dequeue_side_effect

    with patch(
        "quadkit.tasks.execution._concurrency.asyncio.sleep",
        new=AsyncMock(),
    ):
        await worker._work_loop()

    assert dequeue_calls == 2
    worker.logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_work_loop_executes_dequeued_job_protocol_directly():
    """Dequeued JobProtocol instances should execute without adapter conversion."""

    queue = AsyncMock()
    job = JobProtocol(id="job-3", name="queued-job")
    dequeue_calls = 0

    worker = TaskWorker("worker-1", queue=queue, handler_registry={})
    worker.logger = MagicMock()
    worker.running = True
    worker._execute_job = AsyncMock()

    async def dequeue_side_effect():
        nonlocal dequeue_calls
        dequeue_calls += 1
        if dequeue_calls == 1:
            return job
        worker.running = False
        return None

    queue.dequeue.side_effect = dequeue_side_effect

    with patch(
        "quadkit.tasks.execution._concurrency.asyncio.sleep",
        new=AsyncMock(),
    ):
        await worker._work_loop()

    assert dequeue_calls == 2
    worker._execute_job.assert_awaited_once_with(job)
    worker.logger.exception.assert_not_called()
