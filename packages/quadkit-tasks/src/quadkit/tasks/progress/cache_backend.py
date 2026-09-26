"""Cache-backend-backed progress store for distributed task deployments.

Uses the platform ``CacheBackendProtocol`` protocol so progress state is shared
across all worker processes and survives individual worker restarts.

Example:
    from quadkit.contracts.infra.cache import CacheBackendProtocol
    from quadkit.tasks.progress import CacheBackendProgressStore

    store = CacheBackendProgressStore(cache, ttl=3600)
    await store.save(info)
    progress = await store.get("job-123")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit import serialization as json
from quadkit.logging import get_logger
from quadkit.tasks.progress.core import ProgressInfo, ProgressStore

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache import CacheBackendProtocol

logger = get_logger(__name__)

_KEY_PREFIX = "quadkit:task:progress:"
_ACTIVE_SET_KEY = "quadkit:task:progress:__active__"


class CacheBackendProgressStore(ProgressStore):
    """Distributed progress store backed by the platform ``CacheBackendProtocol``.

    Stores serialised :class:`~quadkit.tasks.progress.core.ProgressInfo`
    objects in the configured cache backend so that progress is visible to
    all worker processes. TTL-based expiry is delegated to the backend.

    Args:
        cache: Platform cache backend (Redis, Memcached, …).
        ttl: Seconds before a progress entry expires. Defaults to 3600 (1 hour).
    """

    def __init__(self, cache: CacheBackendProtocol, *, ttl: int = 3600) -> None:
        self._cache = cache
        self._ttl = ttl

    def _key(self, job_id: str) -> str:
        return f"{_KEY_PREFIX}{job_id}"

    def _serialize(self, info: ProgressInfo) -> str:
        return json.dumps(  # type: ignore[return-value]
            {
                "job_id": info.job_id,
                "current": info.current,
                "total": info.total,
                "percentage": info.percentage,
                "message": info.message,
                "started_at": info.started_at,
                "updated_at": info.updated_at,
                "estimated_remaining_seconds": info.estimated_remaining_seconds,
                "metadata": info.metadata,
            }
        )

    def _deserialize(self, data: Any) -> ProgressInfo | None:
        if data is None:
            return None
        try:
            if isinstance(data, bytes):
                data = data.decode()
            d = json.loads(data) if isinstance(data, str) else data
            return ProgressInfo(
                job_id=d["job_id"],
                current=d.get("current", 0),
                total=d.get("total", 0),
                percentage=d.get("percentage", 0.0),
                message=d.get("message", ""),
                started_at=d.get("started_at", 0.0),
                updated_at=d.get("updated_at", 0.0),
                estimated_remaining_seconds=d.get("estimated_remaining_seconds"),
                metadata=d.get("metadata", {}),
            )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("tasks.progress.deserialize_error", error=str(exc))
            return None

    async def save(self, info: ProgressInfo) -> None:
        """Persist a ProgressInfo entry to the cache backend.

        Args:
            info: Progress state to save.
        """
        await self._cache.set(
            self._key(info.job_id), self._serialize(info), ttl=self._ttl
        )

    async def get(self, job_id: str) -> ProgressInfo | None:
        """Return the ProgressInfo for the given job ID, or None if not found.

        Args:
            job_id: Unique identifier for the job.
        """
        raw = await self._cache.get(self._key(job_id))
        return self._deserialize(raw)

    async def delete(self, job_id: str) -> None:
        """Remove the progress entry for the given job ID.

        Args:
            job_id: Unique identifier for the job.
        """
        await self._cache.delete(self._key(job_id))

    async def list_active(self) -> list[ProgressInfo]:
        """Return all active (incomplete) progress entries.

        .. note::
            This implementation scans the key prefix via ``get``, which may
            be slow on large datasets. Consider using a Redis-specific
            implementation with SCAN for production at scale.

        Returns:
            List of incomplete :class:`~quadkit.tasks.progress.core.ProgressInfo`.
        """
        # Without a SCAN-like API we cannot enumerate all keys efficiently.
        # Return an empty list; subclasses with backend-specific iteration can override.
        return []


__all__ = ["CacheBackendProgressStore"]
