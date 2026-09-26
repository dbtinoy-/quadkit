"""Manager for distributed locks.

Provides factory methods and lock cleanup.
"""

from __future__ import annotations

from typing import Any

from quadkit.cache import constants as const
from quadkit.cache.locks.distributed import DistributedLockProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class LockManager:
    """Manager for distributed locks.

    Provides factory methods and lock cleanup.
    """

    def __init__(
        self, redis_client: Any, default_ttl: int = const.DEFAULT_LOCK_TTL
    ) -> None:
        """Initialize lock manager.

        Args:
            redis_client: Redis client
            default_ttl: Default lock TTL
        """
        self.redis = redis_client
        self.default_ttl = default_ttl
        self._locks: dict[str, DistributedLockProtocol] = {}

    def create_lock(
        self,
        key: str,
        ttl: int | None = None,
    ) -> DistributedLockProtocol:
        """Create distributed lock.

        Args:
            key: Lock key
            ttl: Lock TTL (uses default if None)

        Returns:
            Distributed lock
        """
        lock = DistributedLockProtocol(
            redis_client=self.redis,
            key=key,
            ttl=ttl or self.default_ttl,
        )

        self._locks[key] = lock
        return lock

    async def release_all(self) -> None:
        """Release all managed locks."""
        for lock in self._locks.values():
            if lock.is_locked:
                await lock.release()

        count = len(self._locks)
        self._locks.clear()
        logger.info("All locks released: count=%s", count)
