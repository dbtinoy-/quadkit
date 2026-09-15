"""Contract compliance suite for ``TaskQueueProtocol`` implementations.

Subclass :class:`TaskQueueCompliance` and implement
:meth:`create_queue` to verify that any task queue backend satisfies
the ``TaskQueueProtocol`` contract, including the ``ack``/``nack`` protocol::

    from quadkit.testing.compliance import TaskQueueCompliance

    class TestMemoryQueue(TaskQueueCompliance):
        async def create_queue(self):
            return MemoryTaskQueue()
"""

from __future__ import annotations

from abc import abstractmethod
import itertools
from typing import Any
from unittest.mock import MagicMock

import pytest

__all__ = ["TaskQueueCompliance"]

_JOB_COUNTER = itertools.count()


def _make_job(
    task_id: str = "job-1",
    name: str = "test_task",
    priority: int = 5,
) -> Any:
    """Return a minimal fake JobProtocol object satisfying the JobProtocol protocol.

    Uses a monotonically increasing ``created_at`` value so heapq never
    needs to fall back to comparing the JobProtocol objects themselves.
    """
    created_at = float(next(_JOB_COUNTER))
    job = MagicMock()
    job.id = task_id
    job.name = name
    job.priority = priority
    job.created_at = created_at
    job.scheduled_at = None
    job.to_dict.return_value = {
        "id": task_id,
        "name": name,
        "priority": priority,
        "args": [],
        "kwargs": {},
        "status": "pending",
        "max_retries": 3,
        "timeout": None,
        "created_at": created_at,
        "scheduled_at": None,
    }
    return job


class TaskQueueCompliance:
    """Reusable test suite for any ``TaskQueueProtocol`` implementation.

    Subclass and implement :meth:`create_queue`:

    .. code-block:: python

        class TestMyQueue(TaskQueueCompliance):
            async def create_queue(self):
                return MemoryTaskQueue()
    """

    @abstractmethod
    async def create_queue(self) -> Any:
        """Return a fresh, empty instance of the queue under test."""
        ...

    # ------------------------------------------------------------------
    # Core enqueue / dequeue contract
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_enqueue_returns_task_id(self) -> None:
        """enqueue returns the task id."""
        queue = await self.create_queue()
        job = _make_job("job-1")
        result = await queue.enqueue(job)
        # TaskQueueProtocol declares Result[str, TaskQueueError]; tolerate
        # plain-id backends as well.
        task_id = result.unwrap() if hasattr(result, "is_ok") else result
        assert task_id == "job-1"
        await queue.close()

    @pytest.mark.asyncio
    async def test_dequeue_returns_enqueued_task(self) -> None:
        """dequeue returns the task that was enqueued."""
        queue = await self.create_queue()
        job = _make_job("job-2")
        await queue.enqueue(job)
        dequeued = await queue.dequeue()
        assert dequeued is not None
        assert dequeued.id == "job-2"
        await queue.dequeue()  # consume so ack/nack tests start fresh
        await queue.close()

    @pytest.mark.asyncio
    async def test_dequeue_empty_returns_none(self) -> None:
        """dequeue on an empty queue returns None."""
        queue = await self.create_queue()
        result = await queue.dequeue()
        assert result is None
        await queue.close()

    # ------------------------------------------------------------------
    # ack contract
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ack_does_not_raise(self) -> None:
        """ack on a known in-flight task completes without error."""
        queue = await self.create_queue()
        job = _make_job("job-ack")
        await queue.enqueue(job)
        task = await queue.dequeue()
        assert task is not None
        # Must not raise
        await queue.ack(task.id)
        await queue.close()

    @pytest.mark.asyncio
    async def test_ack_unknown_id_is_noop(self) -> None:
        """ack on an unknown task id is a safe no-op."""
        queue = await self.create_queue()
        # Must not raise
        await queue.ack("nonexistent-id")
        await queue.close()

    # ------------------------------------------------------------------
    # nack contract
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_nack_requeue_returns_task_to_queue(self) -> None:
        """nack with requeue=True makes the task available for dequeue again."""
        queue = await self.create_queue()
        job = _make_job("job-nack-requeue")
        await queue.enqueue(job)
        task = await queue.dequeue()
        assert task is not None

        await queue.nack(task.id, requeue=True)

        retry = await queue.dequeue()
        assert retry is not None, "Task should be re-queued after nack(requeue=True)"
        assert retry.id == "job-nack-requeue"
        await queue.ack(retry.id)
        await queue.close()

    @pytest.mark.asyncio
    async def test_nack_discard_does_not_requeue(self) -> None:
        """nack with requeue=False permanently discards the task."""
        queue = await self.create_queue()
        job = _make_job("job-nack-discard")
        await queue.enqueue(job)
        task = await queue.dequeue()
        assert task is not None

        await queue.nack(task.id, requeue=False)

        gone = await queue.dequeue()
        assert gone is None, "Task should be discarded after nack(requeue=False)"
        await queue.close()

    @pytest.mark.asyncio
    async def test_nack_unknown_id_is_noop(self) -> None:
        """nack on an unknown task id is a safe no-op."""
        queue = await self.create_queue()
        # Must not raise for either requeue=True or requeue=False
        await queue.nack("nonexistent-id", requeue=True)
        await queue.nack("nonexistent-id", requeue=False)
        await queue.close()

    # ------------------------------------------------------------------
    # get_task_count / clear
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_task_count_reflects_pending(self) -> None:
        """get_task_count returns the number of tasks waiting to be dequeued."""
        queue = await self.create_queue()
        assert await queue.get_task_count() == 0
        await queue.enqueue(_make_job("c-1"))
        await queue.enqueue(_make_job("c-2"))
        assert await queue.get_task_count() == 2
        await queue.dequeue()
        assert await queue.get_task_count() == 1
        # Cleanup
        task = await queue.dequeue()
        if task:
            await queue.ack(task.id)
        await queue.close()

    @pytest.mark.asyncio
    async def test_clear_empties_the_queue(self) -> None:
        """clear removes all pending tasks."""
        queue = await self.create_queue()
        await queue.enqueue(_make_job("cl-1"))
        await queue.enqueue(_make_job("cl-2"))
        await queue.clear()
        assert await queue.get_task_count() == 0
        assert await queue.dequeue() is None
        await queue.close()
