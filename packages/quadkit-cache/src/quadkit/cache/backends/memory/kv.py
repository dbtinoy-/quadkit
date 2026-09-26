"""In-memory storage implementation for Quadkit."""

from __future__ import annotations

import asyncio
import contextlib
import fnmatch
from typing import Any

from quadkit.cache.backends.memory_state import MemoryStateStore
from quadkit.contracts.infra.storage import StorageBackendProtocol, StorageType
from quadkit.logging import get_logger

logger = get_logger(__name__)


class InMemoryStorage(StorageBackendProtocol):
    """Namespace-aware in-memory storage backend backed by MemoryStateStore.

    Each namespace is served by its own :class:`MemoryStateStore`, which
    provides LRU eviction and TTL support.  Async coroutine safety is
    handled by a single ``asyncio.Lock`` at the container level.
    """

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: int | None = None,
        cleanup_interval: int = 60,
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self._stores: dict[str, MemoryStateStore] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None
        self._connected = False

    @property
    def storage_type(self) -> StorageType:
        return StorageType.MEMORY

    def _get_store(self, namespace: str) -> MemoryStateStore:
        """Return (or create) the MemoryStateStore for *namespace*."""
        if namespace not in self._stores:
            self._stores[namespace] = MemoryStateStore(  # type: ignore[abstract]
                max_size=self.max_size,
            )
        return self._stores[namespace]

    async def connect(self) -> None:
        self._connected = True
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def disconnect(self) -> None:
        self._connected = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        async with self._lock:
            self._stores.clear()

    async def get(self, key: str, namespace: str | None = None) -> Any | None:
        ns = namespace or "default"
        async with self._lock:
            return await self._get_store(ns).get(key)

    async def set(
        self,
        key: str,
        value: Any,
        namespace: str | None = None,
        ttl: int | None = None,
    ) -> bool:
        ns = namespace or "default"
        async with self._lock:
            effective_ttl = ttl or self.default_ttl
            return await self._get_store(ns).set(key, value, effective_ttl)

    async def delete(self, key: str, namespace: str | None = None) -> bool:
        ns = namespace or "default"
        async with self._lock:
            return await self._get_store(ns).delete(key)

    async def exists(self, key: str, namespace: str | None = None) -> bool:
        val = await self.get(key, namespace)
        return val is not None

    async def list_keys(
        self,
        pattern: str | None = None,
        namespace: str | None = None,
    ) -> list[str]:
        ns = namespace or "default"
        async with self._lock:
            store = self._get_store(ns)
            store._evict_expired()
            keys = list(store._data.keys())

        if pattern:
            keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
        return keys

    async def clear(self, namespace: str | None = None) -> bool:
        ns = namespace or "default"
        async with self._lock:
            self._stores.pop(ns, None)
        return True

    async def _periodic_cleanup(self) -> None:
        while self._connected:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception:  # noqa: BLE001 — a foreign cleanup error must not kill the cleanup task
                logger.exception("Error in storage cleanup task")

    async def _cleanup_expired(self) -> None:
        async with self._lock:
            for store in self._stores.values():
                store._evict_expired()

    def get_stats(self) -> dict[str, Any]:
        """Return basic statistics about memory usage."""
        stats: dict[str, Any] = {"namespaces": {}, "total_entries": 0}
        for ns, store in self._stores.items():
            count = len(store._data)
            stats["namespaces"][ns] = {"entries": count}
            stats["total_entries"] += count
        return stats
