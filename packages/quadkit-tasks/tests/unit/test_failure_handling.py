"""Tests for dead-letter handling (send_to_dlq)."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.tasks.execution._failure_handling import send_to_dlq
from quadkit.tasks.models.job import JobProtocol


def _job() -> JobProtocol:
    return JobProtocol(
        id="job-1",
        name="my-task",
        args=(1, 2),
        kwargs={"a": 1},
        priority=5,
        max_retries=3,
        status="failed",
    )


class _RecordingDLQ:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def add(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class _Queue:
    def __init__(self, with_dlq_method: bool = False) -> None:
        self.enqueued: list[JobProtocol] = []
        self.dlq_enqueued: list[JobProtocol] = []
        if with_dlq_method:
            self.enqueue_dlq = self._enqueue_dlq

    async def _enqueue_dlq(self, job: JobProtocol) -> None:
        self.dlq_enqueued.append(job)

    async def enqueue(self, job: JobProtocol) -> None:
        self.enqueued.append(job)


class _Logger:
    def __init__(self) -> None:
        self.infos: list[tuple[str, ...]] = []

    def info(self, msg: str, *args: Any) -> None:
        self.infos.append((msg, *args))


class TestDedicatedDLQ:
    """Dedicated DeadLetterQueue path."""

    @pytest.mark.asyncio
    async def test_uses_dlq_add(self) -> None:  # noqa: D102
        dlq = _RecordingDLQ()
        job = _job()
        await send_to_dlq(
            dlq, _Queue(), job, "boom", worker_id="w1", logger_instance=_Logger()
        )
        assert len(dlq.calls) == 1
        call = dlq.calls[0]
        assert call["job"] is job
        assert call["error"] == "boom"
        assert call["attempt_count"] == job.retry_count

    @pytest.mark.asyncio
    async def test_error_falls_back_to_last_error(self) -> None:  # noqa: D102
        dlq = _RecordingDLQ()
        job = _job()
        job.last_error = "stored error"
        await send_to_dlq(
            dlq, _Queue(), job, "", worker_id="w1", logger_instance=_Logger()
        )
        assert dlq.calls[0]["error"] == "stored error"

    @pytest.mark.asyncio
    async def test_error_falls_back_to_unknown(self) -> None:  # noqa: D102
        dlq = _RecordingDLQ()
        job = _job()
        job.last_error = None
        await send_to_dlq(
            dlq, _Queue(), job, "", worker_id="w1", logger_instance=_Logger()
        )
        assert dlq.calls[0]["error"] == "Unknown error"

    @pytest.mark.asyncio
    async def test_does_not_re_enqueue(self) -> None:  # noqa: D102
        dlq = _RecordingDLQ()
        queue = _Queue()
        job = _job()
        await send_to_dlq(
            dlq, queue, job, "boom", worker_id="w1", logger_instance=_Logger()
        )
        assert queue.enqueued == []
        assert queue.dlq_enqueued == []


class TestFallbackReEnqueue:
    """Fallback DLQ-prefixed re-enqueue path."""

    @pytest.mark.asyncio
    async def test_re_enqueues_with_dlq_prefix(self) -> None:  # noqa: D102
        queue = _Queue(with_dlq_method=False)
        job = _job()
        await send_to_dlq(
            None, queue, job, "boom", worker_id="w1", logger_instance=_Logger()
        )
        assert len(queue.enqueued) == 1
        dlq_job = queue.enqueued[0]
        assert dlq_job.id == "dlq:job-1"
        assert dlq_job.name == "dlq:my-task"
        assert dlq_job.max_retries == 0
        assert dlq_job.args == (1, 2)
        assert dlq_job.kwargs == {"a": 1}
        assert dlq_job.priority == 5

    @pytest.mark.asyncio
    async def test_prefers_enqueue_dlq_method(self) -> None:  # noqa: D102
        queue = _Queue(with_dlq_method=True)
        job = _job()
        await send_to_dlq(
            None, queue, job, "boom", worker_id="w1", logger_instance=_Logger()
        )
        assert len(queue.dlq_enqueued) == 1
        assert queue.enqueued == []

    @pytest.mark.asyncio
    async def test_logs_report(self) -> None:  # noqa: D102
        queue = _Queue(with_dlq_method=False)
        logger = _Logger()
        job = _job()
        await send_to_dlq(
            None, queue, job, "boom", worker_id="w2", logger_instance=logger
        )
        assert len(logger.infos) == 1
        assert "w2" in str(logger.infos[0])
        assert "job-1" in str(logger.infos[0])
