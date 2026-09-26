"""Cache-backend-backed result store for distributed task deployments.

Uses the platform ``CacheBackendProtocol`` protocol for storage so results are
shared across all processes and survive individual worker restarts.

Example:
    from quadkit.contracts.infra.cache import CacheBackendProtocol
    from quadkit.tasks.results import CacheBackendResultStore

    store = CacheBackendResultStore(cache, ttl=3600)
    await store.store("job-123", result)
    retrieved = await store.get("job-123")
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit import serialization as json
from quadkit.logging import get_logger
from quadkit.result import Result
from quadkit.tasks.models.job import JobResult
from quadkit.tasks.results.core import ResultStore

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache import CacheBackendProtocol

logger = get_logger(__name__)

_KEY_PREFIX = "quadkit:task:result:"
_INDEX_KEY = f"{_KEY_PREFIX}__index__"
_MAX_INDEX = 10000


class CacheBackendResultStore(ResultStore):
    """Distributed result store backed by the platform ``CacheBackendProtocol``.

    Stores serialised :class:`~quadkit.tasks.models.job.JobResult` objects
    in the configured cache backend so that results are visible to all worker
    processes.  TTL-based expiry is delegated to the backend.

    Args:
        cache: Platform cache backend (Redis, Memcached, …).
        ttl: Seconds before a result entry expires.  Defaults to 3600 (1 hour).
        poll_interval: Seconds between polls in :meth:`wait`.  Defaults to 0.5.
    """

    def __init__(
        self,
        cache: CacheBackendProtocol,
        *,
        ttl: int = 3600,
        poll_interval: float = 0.5,
    ) -> None:
        self._cache = cache
        self._ttl = ttl
        self._poll_interval = poll_interval

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _key(self, job_id: str) -> str:
        return f"{_KEY_PREFIX}{job_id}"

    def _unwrap(self, value: Any) -> Any:
        """Unwrap a Result returned by :class:`CacheBackendProtocol`."""
        if isinstance(value, Result):
            return value.unwrap() if value.is_ok() else None
        return value

    def _serialize(self, result: JobResult) -> str:
        return json.dumps(result.to_dict()).decode()

    def _deserialize(self, raw: Any) -> JobResult | None:
        try:
            raw = self._unwrap(raw)
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode()
            data = json.loads(raw)
            return JobResult.from_dict(data)
        except (ValueError, KeyError, TypeError, OSError):
            logger.warning("Failed to deserialise cached task result", exc_info=True)
            return None

    async def _index(self) -> list[str]:
        """Read the completion index, tolerating missing or corrupt entries."""
        raw = self._unwrap(await self._cache.get(_INDEX_KEY))
        if not raw:
            return []
        try:
            if isinstance(raw, bytes):
                raw = raw.decode()
            index = json.loads(raw)
            return index if isinstance(index, list) else []
        except (ValueError, TypeError, OSError):
            return []

    async def _record_index(self, job_id: str) -> None:
        """Append *job_id* to the completion index."""
        index = await self._index()
        if job_id not in index:
            index.append(job_id)
        payload = json.dumps(index[-_MAX_INDEX:]).decode()
        await self._cache.set(_INDEX_KEY, payload, ttl=self._ttl)

    # ------------------------------------------------------------------
    # ResultStore interface
    # ------------------------------------------------------------------

    async def store(self, job_id: str, result: JobResult) -> None:
        """Persist a job result in the cache backend with TTL."""
        payload = self._serialize(result)
        await self._cache.set(self._key(job_id), payload, ttl=self._ttl)
        await self._record_index(job_id)

    async def get(self, job_id: str) -> JobResult | None:
        """Return the stored result, or ``None`` if absent or expired."""
        raw: Any = await self._cache.get(self._key(job_id))
        if raw is None:
            return None
        return self._deserialize(raw)

    async def delete(self, job_id: str) -> bool:
        """Remove the result from the cache and return ``True`` if it existed."""
        result: Any = await self._cache.delete(self._key(job_id))
        if isinstance(result, Result):
            return result.unwrap() if result.is_ok() else False
        if isinstance(result, bool):
            return result
        return result.unwrap() if result.is_ok() else False

    async def get_completed(self, limit: int | None = None) -> list[JobResult]:
        """Return recently completed results, newest first.

        Args:
            limit: Maximum number of results to return; ``None`` for all.

        Returns:
            Successful results stored through this backend, newest first.
        """
        completed: list[JobResult] = []
        for job_id in reversed(await self._index()):
            result = await self.get(job_id)
            if result is not None and result.success:
                completed.append(result)
                if limit is not None and len(completed) >= limit:
                    break
        return completed

    async def get_failed(self, limit: int | None = None) -> list[JobResult]:
        """Return recently failed results, newest first.

        Args:
            limit: Maximum number of results to return; ``None`` for all.

        Returns:
            Failed results stored through this backend, newest first.
        """
        failed: list[JobResult] = []
        for job_id in reversed(await self._index()):
            result = await self.get(job_id)
            if result is not None and not result.success:
                failed.append(result)
                if limit is not None and len(failed) >= limit:
                    break
        return failed

    async def wait(
        self,
        job_id: str,
        *,
        timeout: float = 30.0,
        poll_interval: float | None = None,
    ) -> JobResult | None:
        """Poll the cache until the result appears or the timeout elapses."""
        interval = poll_interval if poll_interval is not None else self._poll_interval
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            result = await self.get(job_id)
            if result is not None:
                return result
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                return None
            await asyncio.sleep(min(interval, remaining))

    async def cleanup_expired(self) -> int:
        """No-op: the cache backend handles TTL expiry automatically."""
        return 0
