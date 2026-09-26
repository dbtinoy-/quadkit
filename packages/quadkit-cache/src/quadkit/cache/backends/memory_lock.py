"""In-memory lock store implementation"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.stores import LockStoreProtocol
from quadkit.primitives import clock as ambient_clock


class MemoryLockStore(LockStoreProtocol):
    """In-memory lock store for testing"""

    def __init__(self) -> None:
        self._locks: dict[str, dict[str, Any]] = {}

    async def is_locked(self, key: str) -> bool:
        """Check if a key is locked"""
        if key in self._locks:
            lock_info = self._locks[key]
            if lock_info["expires_at"] > ambient_clock.timestamp():
                return True
            # Lock expired, remove it
            del self._locks[key]
        return False

    async def acquire(
        self,
        lock_name: str,
        owner: str,
        ttl: int,
    ) -> bool:
        """Attempt to acquire a lock.

        Args:
            lock_name: Name of the lock.
            owner: Lock owner identifier.
            ttl: Lock TTL in seconds.

        Returns:
            True if lock was acquired.
        """
        # Clean expired locks first
        await self._cleanup_expired(lock_name)

        if lock_name in self._locks:
            # Lock already exists
            return False

        # Acquire the lock
        expires_at = ambient_clock.timestamp() + ttl
        self._locks[lock_name] = {
            "expires_at": expires_at,
            "owner": owner,
        }
        return True

    async def release(self, lock_name: str, owner: str) -> bool:
        """Release a lock.

        Args:
            lock_name: Name of the lock.
            owner: Lock owner identifier.

        Returns:
            True if released successfully.
        """
        info = self._locks.get(lock_name)
        if not info:
            return False

        if info.get("owner") == owner:
            del self._locks[lock_name]
            return True

        # Cannot release someone else's lock
        return False

    async def _cleanup_expired(self, key: str) -> None:
        """Remove expired lock for a single key (internal helper)."""
        if key in self._locks:
            lock_info = self._locks[key]
            if lock_info["expires_at"] <= ambient_clock.timestamp():
                del self._locks[key]

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check the health of the lock store"""
        return HealthCheckResult(
            component="memory-lock",
            status=HealthStatus.HEALTHY,
            details={"driver": "memory", "locks_count": len(self._locks)},
        )
