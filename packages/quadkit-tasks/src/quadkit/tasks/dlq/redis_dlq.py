"""Redis-backed dead-letter queue backend for failed task storage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from quadkit.logging import get_logger
from quadkit.serialization import dumps_str, loads_str

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)

__all__ = ["RedisDLQBackend"]

_DLQ_KEY = "quadkit:dlq:{queue_name}"
_MAX_ENTRIES = 100_000


class RedisDLQBackend:
    """Redis-backed dead-letter queue using a capped list.

    Failed jobs are prepended to a Redis list (LPUSH), keeping the most
    recent failures first. The list is capped at ``max_entries`` via LTRIM.
    Jobs survive process restarts and server failures.

    Args:
        redis: Async Redis client.
        queue_name: Logical queue name (used to namespace the DLQ key).
        max_entries: Maximum number of DLQ entries to retain (default 100K).
    """

    def __init__(
        self,
        redis: Redis,
        queue_name: str = "default",
        max_entries: int = _MAX_ENTRIES,
    ) -> None:
        self._redis = redis
        self._key = _DLQ_KEY.format(queue_name=queue_name)
        self._max_entries = max_entries

    async def push(self, job: Any, error: str) -> None:
        """Store a failed job in the DLQ.

        Args:
            job: The failed job (must have id, queue, payload, retry_count attributes).
            error: The error message or traceback string.
        """
        entry = dumps_str(
            {
                "job_id": job.id,
                "queue": job.queue,
                "payload": job.payload,
                "error": error,
                "failed_at": datetime.now(UTC).isoformat(),
                "retry_count": getattr(job, "retry_count", 0),
            }
        )
        pipe = self._redis.pipeline()
        pipe.lpush(self._key, entry)
        pipe.ltrim(self._key, 0, self._max_entries - 1)
        await pipe.execute()

        logger.info("dlq_job_stored", job_id=job.id, queue=job.queue, key=self._key)

    async def list_entries(self, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieve the most recent DLQ entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of DLQ entry dicts, most recent first.
        """
        raw = await cast("Any", self._redis.lrange(self._key, 0, limit - 1))
        return [loads_str(entry) for entry in raw]

    async def size(self) -> int:
        """Return the current number of entries in the DLQ.

        Returns:
            Integer count of DLQ entries.
        """
        count: int = await cast("Any", self._redis.llen(self._key))
        return count
