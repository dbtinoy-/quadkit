"""Redis task queue implementation

This module provides a Redis-based task queue using sorted sets for priority ordering.
Suitable for production deployments with distributed workers.

Score formula (ZSET)
--------------------
Each task is stored in a sorted set with score::

    score = -(priority * _PRIORITY_SCALE) + sequence

where ``sequence`` is obtained via ``INCR {queue}:seq`` on every enqueue.

- Lower score -> ZPOPMIN returns the task first -> higher priority dequeued first.
- Within the same priority, a lower sequence (earlier enqueue) yields a lower score
  -> FIFO tiebreaking within the same priority level.

``_PRIORITY_SCALE`` is large enough (10**12) to separate any two adjacent priority
levels regardless of how large the sequence counter grows in practice.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.infra.tasks import TaskQueueProtocol
from quadkit.result import Ok, Result
from quadkit.serialization import dumps, loads
from quadkit.tasks.exceptions import TaskError
from quadkit.tasks.hooks import TaskEnqueuedHook
from quadkit.tasks.models.job import JobProtocol

if TYPE_CHECKING:
    from quadkit.contracts.core import HookRegistryProtocol

# Optional Redis dependency
try:
    import redis.asyncio as redis

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    redis = None  # type: ignore[assignment]

# Multiplier that separates every pair of adjacent priority levels in the ZSET
# score.  Because score = -(priority * _PRIORITY_SCALE) + seq, a task at
# priority P will always have a lower score than one at priority P-1 as long as
# seq < _PRIORITY_SCALE, i.e. fewer than 10**12 enqueues per queue lifetime.
# Float64 represents integers exactly up to 2**53 (~9e15), so the formula
# is exact for any priority 0-255 and sequence up to ~8.75e15.
_PRIORITY_SCALE: int = 1_000_000_000_000


class RedisTaskQueue(TaskQueueProtocol):
    """Redis-based task queue implementation

    Uses Redis sorted sets for priority-based ordering and hashes
    for task data storage. Supports distributed workers and provides
    persistence across restarts.

    Characteristics:
    - Storage: Redis sorted sets for priority, hashes for data
    - Features: Distributed, persistent, atomic operations
    - Use Case: Production deployments, multi-instance scaling
    - Dependencies: redis>=4.6.0

    Storage Structure:
    - Sorted Set: {queue_name} - task IDs with priority as score
    - Hash: {queue_name}:tasks - task ID -> task data mapping

    Example:
        ```python
        queue = RedisTaskQueue(redis_url="redis://localhost:6379/0")
        await queue.enqueue(task)
        task = await queue.dequeue()
        await queue.close()
        ```
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        queue_name: str = "tasks",
    ):
        """Initialize Redis task queue

        Args:
            redis_url: Redis connection URL
            queue_name: Name of the queue (Redis key prefix)

        Raises:
            ImportError: If redis package is not installed
        """
        if not HAS_REDIS:
            raise ImportError(
                "redis is required for Redis task queue. "
                "Install with: pip install quadkit-tasks[redis]",
            )

        self.redis_url = redis_url
        self.queue_name = queue_name
        self.redis: redis.Redis | None = None
        self._hooks: HookRegistryProtocol | None = None

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry after provider boot wiring."""
        self._hooks = hooks

    async def _emit_action(self, hook_name: str, payload: object) -> None:
        """Emit a task action hook when a registry is available."""
        hooks = getattr(self, "_hooks", None)
        if hooks is None:
            return

        await hooks.call_action(hook_name, payload=payload)

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection

        Returns:
            Redis connection instance
        """
        if not self.redis:
            # ``redis.asyncio.from_url`` is a SYNCHRONOUS factory that
            # returns the client directly — awaiting it raises TypeError
            # against the real driver (mocks hide this because
            # AsyncMock makes everything awaitable).
            self.redis = redis.from_url(self.redis_url)
        assert self.redis is not None  # noqa: S101  # assigned just above when absent
        return self.redis

    async def enqueue(self, task: JobProtocol) -> Result[str, TaskError]:  # type: ignore[override]
        """Add a task to the queue, returning Ok(task_id) or Err(TaskError) on failure.

        Uses sorted set for priority ordering and hash for data storage.
        The ZSET score encodes both priority and insertion order::

            score = -(priority * _PRIORITY_SCALE) + sequence

        This guarantees higher-priority tasks have a lower score (ZPOPMIN
        returns them first) and equal-priority tasks are ordered FIFO.

        Args:
            task: Task to enqueue

        Returns:
            Ok containing the enqueued task id, or Err containing a TaskError.
        """
        redis_conn = await self._get_redis()
        task_data: Any = dumps(task.to_dict())
        if isinstance(task_data, bytes):
            task_data_str = task_data.decode()
        else:
            task_data_str = task_data

        # Obtain a monotonically increasing sequence number for FIFO tiebreaking.
        # INCR is atomic in Redis, so this is safe across distributed workers.
        incr_res = cast("Any", redis_conn).incr(f"{self.queue_name}:seq")
        seq: int = int(await incr_res if asyncio.iscoroutine(incr_res) else incr_res)

        # Composite score: negate priority so ZPOPMIN returns highest-priority
        # tasks first; add sequence so equal-priority tasks are FIFO.
        score = -(task.priority * _PRIORITY_SCALE) + seq

        # Atomic operations: add to sorted set and store data
        async with redis_conn.pipeline(transaction=True) as pipe:
            await cast("Any", pipe.zadd(self.queue_name, {task.id: score}, nx=True))
            await cast(
                "Any",
                pipe.hset(f"{self.queue_name}:tasks", task.id, task_data_str),
            )
            await cast("Any", pipe.execute())
        await self._emit_action(
            "task.queued",
            TaskEnqueuedHook(task_name=task.name, queue_name=self.queue_name),
        )
        return Ok(task.id)

    async def dequeue(self) -> JobProtocol | None:
        """Remove and return the next task from the queue

        Uses ZPOPMIN for atomic removal of highest priority task.

        Returns:
            Next task or None if queue is empty
        """
        redis_conn = await self._get_redis()

        # Get the highest priority task (lowest score due to negative priority)
        res = cast("Any", redis_conn).zpopmin(self.queue_name, count=1)
        if asyncio.iscoroutine(res):
            result = await res
        else:
            result = res
        if not result:
            return None

        task_id = (
            result[0][0].decode() if isinstance(result[0][0], bytes) else result[0][0]
        )

        # Retrieve task data from hash
        td_res = cast("Any", redis_conn).hget(f"{self.queue_name}:tasks", task_id)
        if asyncio.iscoroutine(td_res):
            task_data_str = await td_res
        else:
            task_data_str = td_res

        if task_data_str:
            task_data = loads(task_data_str)
            # Move task data to processing hash (ack/nack will clean up)
            processing_key = f"{self.queue_name}:processing"
            data_to_store: str = (
                task_data_str.decode()
                if isinstance(task_data_str, bytes)
                else task_data_str
            )
            async with redis_conn.pipeline(transaction=True) as pipe:
                await cast("Any", pipe.hset(processing_key, task_id, data_to_store))
                await cast("Any", pipe.hdel(f"{self.queue_name}:tasks", task_id))
                await cast("Any", pipe.execute())
            return JobProtocol.from_dict(task_data)

        return None

    async def ack(self, task_id: str) -> None:
        """Acknowledge successful processing of a dequeued task

        Removes the task data from the processing hash, permanently
        discarding it.

        Args:
            task_id: ID of the task to acknowledge
        """
        redis_conn = await self._get_redis()
        hd_res = cast("Any", redis_conn).hdel(f"{self.queue_name}:processing", task_id)
        if asyncio.iscoroutine(hd_res):
            await hd_res

    async def nack(self, task_id: str, requeue: bool = True) -> None:
        """Negative-acknowledge a dequeued task, optionally requeuing it

        On ``requeue=True`` the task is moved back into the priority
        sorted set and data hash for another processing attempt.
        Either way, the task is removed from the processing hash.

        Args:
            task_id: ID of the task to negative-acknowledge
            requeue: If True, return the task to the queue for retry
        """
        redis_conn = await self._get_redis()
        processing_key = f"{self.queue_name}:processing"

        hg_res = cast("Any", redis_conn).hget(processing_key, task_id)
        task_data_str: str | bytes | None = (
            await hg_res if asyncio.iscoroutine(hg_res) else hg_res
        )

        if task_data_str and requeue:
            task_data = loads(task_data_str)
            job = JobProtocol.from_dict(task_data)
            data_str: str = (
                task_data_str.decode()
                if isinstance(task_data_str, bytes)
                else task_data_str
            )

            # Assign a new sequence so the requeued task goes to the back of
            # its priority level (correct retry semantics: don't starve others).
            incr_res = cast("Any", redis_conn).incr(f"{self.queue_name}:seq")
            seq: int = int(
                await incr_res if asyncio.iscoroutine(incr_res) else incr_res
            )
            score = -(job.priority * _PRIORITY_SCALE) + seq

            async with redis_conn.pipeline(transaction=True) as pipe:
                await cast(
                    "Any",
                    pipe.zadd(self.queue_name, {job.id: score}, nx=True),
                )
                await cast(
                    "Any",
                    pipe.hset(f"{self.queue_name}:tasks", job.id, data_str),
                )
                await cast("Any", pipe.hdel(processing_key, task_id))
                await cast("Any", pipe.execute())
        else:
            hd_res = cast("Any", redis_conn).hdel(processing_key, task_id)
            if asyncio.iscoroutine(hd_res):
                await hd_res

    async def get_task_count(self) -> int:
        """Get the number of tasks in the queue

        Returns:
            Number of pending tasks in sorted set
        """
        redis_conn = await self._get_redis()
        zc_res = cast("Any", redis_conn).zcard(self.queue_name)
        if isinstance(zc_res, int):
            return int(zc_res)
        # mypy cannot narrow here cleanly for Awaitable[int] | int
        zc_val = await zc_res
        return int(zc_val)

    async def clear(self) -> None:
        """Clear all tasks from the queue

        Deletes the sorted set, hash storage, and sequence counter so that
        the next enqueue after a clear starts from sequence 1 again.
        """
        redis_conn = await self._get_redis()
        await redis_conn.delete(
            self.queue_name,
            f"{self.queue_name}:tasks",
            f"{self.queue_name}:processing",
            f"{self.queue_name}:seq",
        )

    async def close(self) -> None:
        """Close the Redis connection

        Releases connection pool resources.
        """
        if self.redis:
            # ``aclose`` is the current name (redis-py >= 5.0.1); fall back
            # to ``close`` for the declared minimum (redis>=5.0.0).
            closer = getattr(self.redis, "aclose", None)
            if closer is None:
                closer = self.redis.close
            await closer()
            self.redis = None
