"""Distributed lock with automatic TTL renewal.

Prevents lock expiration while critical section is still executing.
This implementation requires a Redis client.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import contextlib
from datetime import UTC, datetime
from typing import Any
import uuid

from quadkit.cache import constants as const
from quadkit.cache.exceptions import LockAcquisitionError
from quadkit.cache.types import DistributedLockInfo
from quadkit.logging import get_logger

logger = get_logger(__name__)


class DistributedLockProtocol:
    """Distributed lock with automatic TTL renewal.

    Prevents lock expiration while critical section is executing.
    Uses background task to renew lock periodically.
    """

    # Lua scripts — compare-and-delete / compare-and-expire atomically so a
    # lock that expires and is re-acquired by someone else between a GET and
    # a DEL/EXPIRE can never be deleted or extended by mistake.
    LUA_RELEASE_LOCK = """
        local cur = redis.call("GET", KEYS[1])
        if cur == false then
            return -1
        elseif cur == ARGV[1] then
            redis.call("DEL", KEYS[1])
            return 1
        else
            return 0
        end
        """

    LUA_EXTEND_LOCK = """
        local cur = redis.call("GET", KEYS[1])
        if cur == false then
            return -1
        elseif cur == ARGV[1] then
            redis.call("EXPIRE", KEYS[1], ARGV[2])
            return 1
        else
            return 0
        end
        """

    def __init__(
        self,
        redis_client: Any,
        key: str,
        ttl: int = const.DEFAULT_LOCK_TTL,
        renewal_interval: int | None = None,
    ) -> None:
        """Initialize distributed lock.

        Args:
            redis_client: Redis client
            key: Lock key
            ttl: Lock TTL in seconds
            renewal_interval: Renewal interval (defaults to TTL/2)
        """
        self.redis = redis_client
        self.key = f"{const.LOCK_KEY_PREFIX}{key}"
        self.ttl = ttl
        divisor = const.DEFAULT_LOCK_RENEWAL_INTERVAL_DIVISOR
        self.renewal_interval = renewal_interval or (ttl // divisor)

        # Generate unique owner ID
        self.owner = str(uuid.uuid4())
        self._lock_info: DistributedLockInfo | None = None

    async def acquire(self) -> bool:
        """Try to acquire the lock.

        Returns:
            True if lock acquired
        """
        try:
            # Try to set key with NX (only if not exists)
            acquired = await self.redis.set(
                self.key,
                self.owner,
                nx=True,
                ex=self.ttl,
            )

            if acquired:
                acquired_at = datetime.now(UTC)
                renewal_task = asyncio.create_task(self._renew_lock())
                renewal_task.add_done_callback(self._on_renewal_done)
                self._lock_info = DistributedLockInfo(
                    key=self.key,
                    owner=self.owner,
                    acquired_at=acquired_at,
                    ttl=self.ttl,
                    renewal_task=renewal_task,
                )
                logger.debug(
                    "lock_acquired",
                    key=self.key,
                    owner=self.owner,
                    ttl=self.ttl,
                )
                return True

            return False

        except Exception as e:  # noqa: BLE001 — any lock operation failure degrades gracefully, never a raw exception
            logger.error("lock_acquire_failed", key=self.key, error=str(e))
            return False

    async def release(self) -> bool:
        """Release the lock.

        Returns:
            True if lock released
        """
        try:
            # Cancel renewal task
            if self._lock_info and self._lock_info.renewal_task:
                self._lock_info.renewal_task.cancel()
                try:
                    await self._lock_info.renewal_task
                except asyncio.CancelledError:
                    pass

            # Atomically delete only if we own the lock
            res = await self.redis.eval(
                self.LUA_RELEASE_LOCK,
                1,
                self.key,
                self.owner,
            )

            if res == 1:
                logger.debug("lock_released", key=self.key, owner=self.owner)
                self._lock_info = None
                return True

            if res == -1:
                logger.warning(
                    "lock_release_failed_not_held",
                    key=self.key,
                    owner=self.owner,
                )
            else:
                logger.warning(
                    "lock_release_failed_not_owner",
                    key=self.key,
                    owner=self.owner,
                )
            return False

        except Exception as e:  # noqa: BLE001 — any lock operation failure degrades gracefully, never a raw exception
            logger.error("lock_release_failed", key=self.key, error=str(e))
            return False

    def _on_renewal_done(self, task: asyncio.Task[None]) -> None:
        """Callback invoked when the renewal task finishes.

        Logs any unhandled exception from the background renewal loop so
        that silent task failures are surfaced even if the caller never
        awaits the task directly.

        Args:
            task: The completed renewal task.
        """
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "lock_renewal_task_failed",
                key=self.key,
                error=str(exc),
            )

    async def _renew_lock(self) -> None:
        """Background task to renew lock periodically."""
        try:
            while True:
                await asyncio.sleep(self.renewal_interval)

                # Atomically extend the TTL only if we still own the lock
                res = await self.redis.eval(
                    self.LUA_EXTEND_LOCK,
                    1,
                    self.key,
                    self.owner,
                    str(self.ttl),
                )
                if res == 1:
                    logger.debug("lock_renewed", key=self.key, owner=self.owner)
                else:
                    reason = (
                        "lock_renewal_failed_not_held"
                        if res == -1
                        else "lock_renewal_failed_not_owner"
                    )
                    logger.warning(reason, key=self.key, owner=self.owner)
                    break

        except asyncio.CancelledError:
            logger.debug("lock_renewal_cancelled", key=self.key)
            raise

        except Exception as e:  # noqa: BLE001 — any lock operation failure degrades gracefully, never a raw exception
            logger.error("lock_renewal_failed", key=self.key, error=str(e))

    @contextlib.asynccontextmanager
    async def lock(self) -> AsyncIterator[DistributedLockProtocol]:
        """Async context manager for lock acquisition.

        Usage:
            async with lock.lock():
                # Critical section
                pass
        """
        acquired = await self.acquire()
        if not acquired:
            raise LockAcquisitionError(f"Could not acquire lock: {self.key}")

        try:
            yield self
        finally:
            await self.release()

    @property
    def is_locked(self) -> bool:
        """Check if this instance currently holds the lock."""
        return self._lock_info is not None

    @property
    def lock_info(self) -> DistributedLockInfo | None:
        """Get lock ownership information."""
        return self._lock_info
