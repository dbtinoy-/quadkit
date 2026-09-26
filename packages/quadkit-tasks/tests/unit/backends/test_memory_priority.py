"""Priority-ordering tests for MemoryTaskQueue.

Verifies that the heap-based memory backend dequeues by descending priority
and uses FIFO (created_at) as a tiebreaker within the same priority level.
"""

from __future__ import annotations

import time

import pytest

from quadkit.tasks.backends.memory import MemoryTaskQueue
from quadkit.tasks.models.job import JobProtocol


def _make_job(job_id: str, priority: int, created_at: float | None = None) -> JobProtocol:
    """Build a minimal JobProtocol for queue tests."""
    job = JobProtocol(id=job_id, name=job_id, priority=priority)
    if created_at is not None:
        job.created_at = created_at
    return job


class TestMemoryTaskQueuePriority:
    """MemoryTaskQueue dequeues by descending priority, then by FIFO within a level."""

    @pytest.fixture
    def queue(self) -> MemoryTaskQueue:
        return MemoryTaskQueue()

    # ------------------------------------------------------------------
    # Priority ordering
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_higher_priority_dequeues_first(self, queue: MemoryTaskQueue) -> None:
        """Tasks enqueued out of priority order must come out highest-first."""
        now = time.time() - 10  # All tasks are immediately available

        low = _make_job("low", priority=1, created_at=now)
        high = _make_job("high", priority=10, created_at=now + 1)
        mid = _make_job("mid", priority=5, created_at=now + 2)

        await queue.enqueue(low)
        await queue.enqueue(high)
        await queue.enqueue(mid)

        first = await queue.dequeue()
        second = await queue.dequeue()
        third = await queue.dequeue()

        assert first is not None and first.id == "high"
        assert second is not None and second.id == "mid"
        assert third is not None and third.id == "low"

    @pytest.mark.asyncio
    async def test_critical_before_normal_before_low(self, queue: MemoryTaskQueue) -> None:
        """Framework Priority enum values (20, 5, 0) are respected."""
        from quadkit.tasks.types import Priority

        now = time.time() - 10

        normal = _make_job("normal", priority=Priority.NORMAL, created_at=now)
        critical = _make_job("critical", priority=Priority.CRITICAL, created_at=now)
        low = _make_job("low", priority=Priority.LOW, created_at=now)

        for job in (normal, critical, low):
            await queue.enqueue(job)

        assert (await queue.dequeue()).id == "critical"  # type: ignore[union-attr]
        assert (await queue.dequeue()).id == "normal"  # type: ignore[union-attr]
        assert (await queue.dequeue()).id == "low"  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # FIFO tiebreaking within the same priority
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_same_priority_maintains_fifo(self, queue: MemoryTaskQueue) -> None:
        """Within identical priority, insertion order (FIFO via created_at) is preserved."""
        base = time.time() - 100  # well in the past — available immediately

        job_a = _make_job("first", priority=5, created_at=base)
        job_b = _make_job("second", priority=5, created_at=base + 1)
        job_c = _make_job("third", priority=5, created_at=base + 2)

        await queue.enqueue(job_a)
        await queue.enqueue(job_b)
        await queue.enqueue(job_c)

        assert (await queue.dequeue()).id == "first"  # type: ignore[union-attr]
        assert (await queue.dequeue()).id == "second"  # type: ignore[union-attr]
        assert (await queue.dequeue()).id == "third"  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_empty_queue_returns_none(self, queue: MemoryTaskQueue) -> None:
        result = await queue.dequeue()
        assert result is None

    @pytest.mark.asyncio
    async def test_single_task_roundtrip(self, queue: MemoryTaskQueue) -> None:
        job = _make_job("only", priority=5)
        await queue.enqueue(job)
        result = await queue.dequeue()
        assert result is not None
        assert result.id == "only"
        assert await queue.dequeue() is None

    @pytest.mark.asyncio
    async def test_get_task_count_reflects_enqueued_items(self, queue: MemoryTaskQueue) -> None:
        assert await queue.get_task_count() == 0
        await queue.enqueue(_make_job("a", 5))
        await queue.enqueue(_make_job("b", 10))
        assert await queue.get_task_count() == 2

    @pytest.mark.asyncio
    async def test_ack_removes_from_in_flight(self, queue: MemoryTaskQueue) -> None:
        job = _make_job("acked", priority=5)
        await queue.enqueue(job)
        dequeued = await queue.dequeue()
        assert dequeued is not None
        await queue.ack(dequeued.id)
        # After ack the in-flight dict should be empty (no re-dequeue)
        assert await queue.dequeue() is None

    @pytest.mark.asyncio
    async def test_nack_requeues_task(self, queue: MemoryTaskQueue) -> None:
        job = _make_job("nacked", priority=7)
        await queue.enqueue(job)
        dequeued = await queue.dequeue()
        assert dequeued is not None
        await queue.nack(dequeued.id, requeue=True)
        requeued = await queue.dequeue()
        assert requeued is not None
        assert requeued.id == "nacked"
