"""Tests for T-08: TaskWorker delegates retries to injected RetryPolicyProtocol."""
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.infra.tasks import JobStatus
from quadkit.tasks.execution.worker import TaskWorker, TaskWorkerServices
from quadkit.tasks.models.job import JobProtocol


class _SimpleRetryPolicy:
    """Minimal retry-policy stub: retries up to ``max_attempts`` times."""

    def __init__(self, max_attempts: int = 3) -> None:
        self._max_attempts = max_attempts

    async def execute(self, func, *args, **kwargs):  # type: ignore[no-untyped-def]
        last_exc: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
        assert last_exc is not None
        raise last_exc

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *_):  # type: ignore[no-untyped-def]
        pass


@pytest.mark.asyncio
async def test_handle_job_failure_sends_to_dlq_not_queue():
    """T-08: _handle_job_failure routes failed jobs to DLQ, no re-enqueue."""
    queue = AsyncMock()
    queue.enqueue = AsyncMock()

    # DLQ.add() is synchronous — use MagicMock
    dlq = MagicMock()

    worker = TaskWorker("worker-1", queue, handler_registry={}, services=TaskWorkerServices(dead_letter_queue=dlq))

    job = JobProtocol(id="job-1", name="test", max_retries=3)
    start_time = time.time()

    await worker._handle_job_failure(job, "error occurred", start_time)

    # JobProtocol should be marked as permanently failed
    assert job.status == JobStatus.FAILED
    assert job.last_error == "error occurred"

    # DLQ.add() should have been called (DLQ is sync)
    dlq.add.assert_called_once()

    # Queue should NOT have been asked to enqueue (T-08: no re-enqueue path)
    queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_job_retries_in_process():
    """T-08: with an injected retry_policy, the worker delegates retries to it."""
    queue = AsyncMock()
    queue.enqueue = AsyncMock()

    call_count = 0

    async def flaky_handler() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError(f"transient error attempt {call_count}")
        return "success"

    worker = TaskWorker(
        "worker-1",
        queue,
        handler_registry={"flaky": flaky_handler},
        services=TaskWorkerServices(retry_policy=_SimpleRetryPolicy(max_attempts=3)),
    )

    job = JobProtocol(id="job-1", name="flaky", max_retries=3)
    await worker._execute_job(job)

    # Handler should have been called 3 times: 2 failures + 1 success
    assert call_count == 3

    # JobProtocol should be marked as completed (not failed)
    assert job.status == JobStatus.COMPLETED

    # Queue should NOT have been enqueued (T-08: retries are in-process)
    queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_job_exhausted_retries_sends_to_dlq():
    """T-08: when all retries exhausted by policy, job ends up in DLQ."""
    queue = AsyncMock()
    queue.enqueue = AsyncMock()

    dlq = MagicMock()  # DLQ.add() is synchronous

    async def always_fails() -> None:
        raise ValueError("permanent failure")

    worker = TaskWorker(
        "worker-1",
        queue,
        handler_registry={"bad": always_fails},
        services=TaskWorkerServices(
            dead_letter_queue=dlq,
            retry_policy=_SimpleRetryPolicy(max_attempts=2),
        ),
    )

    job = JobProtocol(id="job-2", name="bad", max_retries=2)
    await worker._execute_job(job)

    # JobProtocol should be permanently failed
    assert job.status == JobStatus.FAILED

    # DLQ should have received the job once all retries exhausted
    dlq.add.assert_called_once()

    # Queue should NOT have been asked to enqueue
    queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_job_no_retry_policy_single_attempt():
    """Without a retry_policy, the worker executes exactly once (fail-open)."""
    queue = AsyncMock()
    dlq = MagicMock()

    call_count = 0

    async def flaky_handler() -> None:
        nonlocal call_count
        call_count += 1
        raise ValueError("transient")

    worker = TaskWorker(
        "worker-1",
        queue,
        handler_registry={"flaky": flaky_handler},
        services=TaskWorkerServices(dead_letter_queue=dlq),
    )

    job = JobProtocol(id="job-3", name="flaky", max_retries=5)
    await worker._execute_job(job)

    # Only called once — no retries without a policy
    assert call_count == 1
    assert job.status == JobStatus.FAILED
    dlq.add.assert_called_once()
