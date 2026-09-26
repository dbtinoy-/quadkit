"""In-memory KV storage backend for Quadkit.

Intended for testing, local development, and ephemeral caching where no
external infrastructure is available.  All data is lost when the process
exits.

TTL precision is nanosecond-accurate via :func:`time.monotonic_ns`; keys are
evicted **lazily** (expired entries are purged only when accessed, not on a
timer).  If strict eviction timing is required, use the Redis backend instead.
"""

from __future__ import annotations

import fnmatch
import time
from typing import Any

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.infra.storage import StorageBackendProtocol, StorageType
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

logger = get_logger(__name__)

# Nanoseconds per second — used to convert TTL seconds → monotonic deadline.
_NS_PER_S: int = 1_000_000_000


class InMemoryKVStorage(StorageBackendProtocol):
    """Pure in-memory :class:`~quadkit.contracts.StorageBackendProtocol` implementation.

    Data is stored in a plain :class:`dict` keyed by ``"<namespace>:<key>"``
    (or just ``"<key>"`` when no namespace is given).  TTLs are tracked as
    monotonic deadlines and checked lazily on every read operation.

    Thread safety:
        Not thread-safe.  For concurrent async usage on a single event-loop
        thread this is fine; do **not** share an instance across OS threads.

    Attributes:
        _store: Maps full keys to ``(value, deadline_ns | None)`` tuples.
            *deadline_ns* is a monotonic nanosecond timestamp after which the
            entry is considered expired, or ``None`` if the key has no TTL.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, int | None]] = {}
        self._connected: bool = False

    @property
    def storage_type(self) -> StorageType:
        """Return the fixed storage type ``MEMORY`` for this backend."""
        return StorageType.MEMORY

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Mark the backend as connected (no-op for in-memory storage)."""
        self._connected = True
        logger.debug("in_memory_kv.connected")

    async def disconnect(self) -> None:
        """Mark the backend as disconnected (no-op for in-memory storage)."""
        self._connected = False
        logger.debug("in_memory_kv.disconnected")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _full_key(key: str, namespace: str | None) -> str:
        """Combine *namespace* and *key* into a single storage key.

        Args:
            key: The caller-supplied storage key.
            namespace: Optional namespace prefix.

        Returns:
            ``"<namespace>:<key>"`` if a namespace is given, otherwise *key*.
        """
        return f"{namespace}:{key}" if namespace else key

    def _is_alive(self, deadline_ns: int | None) -> bool:
        """Return ``True`` if the entry has not yet expired.

        Args:
            deadline_ns: Monotonic nanosecond deadline, or ``None`` for
                entries without a TTL.

        Returns:
            ``True`` when *deadline_ns* is ``None`` or the current monotonic
            clock has not yet passed it.
        """
        if deadline_ns is None:
            return True
        return int(ambient_clock.monotonic() * _NS_PER_S) < deadline_ns

    # ------------------------------------------------------------------
    # StorageBackend protocol
    # ------------------------------------------------------------------

    async def get(self, key: str, namespace: str | None = None) -> Any | None:
        """Retrieve a value by key, respecting TTL expiry.

        Args:
            key: Storage key.
            namespace: Optional namespace.

        Returns:
            The stored value, or ``None`` if the key does not exist or has
            expired.
        """
        full_key = self._full_key(key, namespace)
        entry = self._store.get(full_key)
        if entry is None:
            return None
        value, deadline_ns = entry
        if not self._is_alive(deadline_ns):
            # Lazy eviction: remove stale entry on first access after expiry.
            del self._store[full_key]
            return None
        return value

    async def set(
        self,
        key: str,
        value: Any,
        namespace: str | None = None,
        ttl: int | None = None,
    ) -> bool:
        """Store a value, optionally with a time-to-live.

        TTL expiry is checked lazily on subsequent reads; there is no
        background eviction thread.

        Args:
            key: Storage key.
            value: Value to store (any Python object).
            namespace: Optional namespace.
            ttl: Seconds until the key expires.  ``None`` means no expiry.

        Returns:
            ``True`` always (in-memory writes cannot fail).
        """
        full_key = self._full_key(key, namespace)
        deadline_ns: int | None = None
        if ttl is not None and ttl > 0:
            deadline_ns = int(ambient_clock.monotonic() * _NS_PER_S) + ttl * _NS_PER_S
        self._store[full_key] = (value, deadline_ns)
        return True

    async def delete(self, key: str, namespace: str | None = None) -> bool:
        """Delete a key.

        Args:
            key: Storage key.
            namespace: Optional namespace.

        Returns:
            ``True`` if the key existed (and was deleted), ``False`` otherwise.
        """
        full_key = self._full_key(key, namespace)
        if full_key in self._store:
            del self._store[full_key]
            return True
        return False

    async def exists(self, key: str, namespace: str | None = None) -> bool:
        """Check whether a non-expired key exists.

        Args:
            key: Storage key.
            namespace: Optional namespace.

        Returns:
            ``True`` if the key is present and has not expired.
        """
        return await self.get(key, namespace) is not None

    async def list_keys(
        self,
        pattern: str | None = None,
        namespace: str | None = None,
    ) -> list[str]:
        """List non-expired keys, optionally filtered by glob pattern.

        Only the bare key portion (without the namespace prefix) is returned,
        mirroring the behaviour of :class:`~quadkit.storage.kv.local.LocalStorage`.

        Args:
            pattern: Glob-style pattern (e.g. ``"user:*"``).
            namespace: Restrict listing to this namespace.

        Returns:
            Sorted list of matching bare keys.
        """
        now_ns = int(ambient_clock.monotonic() * _NS_PER_S)
        stale: list[str] = []
        results: list[str] = []
        ns_prefix = f"{namespace}:" if namespace else ""

        for full_key, (_, deadline_ns) in self._store.items():
            if deadline_ns is not None and now_ns >= deadline_ns:
                stale.append(full_key)
                continue
            if namespace and not full_key.startswith(ns_prefix):
                continue
            bare = full_key[len(ns_prefix) :]
            if pattern and not fnmatch.fnmatch(bare, pattern):
                continue
            results.append(bare)

        # Lazily evict expired keys discovered during the scan.
        for key in stale:
            self._store.pop(key, None)

        return sorted(results)

    async def clear(self, namespace: str | None = None) -> bool:
        """Delete all keys, optionally scoped to a namespace.

        Args:
            namespace: If provided, only keys under this namespace are
                removed.  If ``None``, the entire store is cleared.

        Returns:
            ``True`` always.
        """
        if namespace is None:
            self._store.clear()
        else:
            prefix = f"{namespace}:"
            keys_to_delete = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._store[k]
        return True

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check health of the in-memory backend.

        Always returns a healthy status (memory is always available while the
        process is alive).

        Returns:
            :class:`~quadkit.contracts.HealthCheckResult` with status
            ``HEALTHY``.
        """
        start_ns = time.monotonic_ns()
        # Minimal round-trip: write + read + delete.
        probe_key = "__health_probe__"
        self._store[probe_key] = (True, None)
        _ = self._store.pop(probe_key, None)
        duration_ms = (time.monotonic_ns() - start_ns) / 1_000_000

        return HealthCheckResult(
            component="in_memory_kv",
            status=HealthStatus.HEALTHY,
            message="In-memory KV storage is operational.",
            duration_ms=duration_ms,
            details={"entry_count": len(self._store)},
        )


__all__ = ["InMemoryKVStorage"]
