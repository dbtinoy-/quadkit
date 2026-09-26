from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)


class AutoRenewingLock:
    """Distributed lock with automatic TTL renewal.

    Prevents lock expiration during long operations by automatically
    extending the TTL in the background.
    """

    def __init__(
        self,
        redis: Any,
        key: str,
        lock_id: str,
        ttl: int,
        auto_renew: bool = True,
        renew_interval: int | None = None,
    ) -> None:
        """Initialize auto-renewing lock.

        Args:
            redis: Redis client
            key: Lock key
            lock_id: Unique lock identifier (owner ID)
            ttl: Lock TTL in seconds
            auto_renew: Enable automatic renewal
            renew_interval: Renewal interval (default: ttl / 3)
        """
        self._redis = redis
        self._key = key
        self._lock_id = lock_id
        self._ttl = ttl
        self._auto_renew = auto_renew
        self._renew_interval = renew_interval or max(1, ttl // 3)

        self._renew_task: asyncio.Task[None] | None = None
        self._stop_renew = False
        self._acquired_at: datetime | None = None
        self._last_renewed_at: datetime | None = None
        self._renewal_count = 0

    async def start_auto_renewal(self) -> None:
        """Start background task to auto-renew lock."""
        if not self._auto_renew:
            return

        if self._renew_task is not None:
            logger.warning("Auto-renewal already started")
            return

        self._acquired_at = datetime.now(UTC)
        self._stop_renew = False

        self._renew_task = asyncio.create_task(self._renewal_loop())

        logger.info(
            "Started auto-renewal for lock %s (ttl=%ss, interval=%ss)",
            self._key,
            self._ttl,
            self._renew_interval,
        )

    async def stop_auto_renewal(self) -> None:
        """Stop background renewal task."""
        self._stop_renew = True

        task = self._renew_task
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        logger.info(
            "Stopped auto-renewal for lock %s (renewed %s times)",
            self._key,
            self._renewal_count,
        )

    async def _renewal_loop(self) -> None:
        """Background loop to renew lock TTL."""
        while not self._stop_renew:
            try:
                await asyncio.sleep(self._renew_interval)

                success = await self._extend_lock()

                if not success:
                    logger.error(
                        "Failed to renew lock %s. "
                        "Lock may have been released or stolen.",
                        self._key,
                    )
                    break

                self._renewal_count += 1
                self._last_renewed_at = datetime.now(UTC)

                if self._acquired_at is not None:
                    elapsed = (datetime.now(UTC) - self._acquired_at).total_seconds()
                else:
                    elapsed = 0
                logger.debug(
                    "Renewed lock %s (renewal #%s, held for %.1fs)",
                    self._key,
                    self._renewal_count,
                    elapsed,
                )

            except Exception as e:
                logger.error("Error in lock renewal loop: %s", e, exc_info=True)
                break

    async def _extend_lock(self) -> bool:
        """Extend lock TTL using Lua script."""
        lua_script = """
        local current = redis.call('GET', KEYS[1])
        if current == ARGV[1] then
            redis.call('EXPIRE', KEYS[1], ARGV[2])
            return 1
        else
            return 0
        end
        """

        # redis.eval(script, numkeys, *keys_and_args) — numkeys is a count,
        # keys and args follow as separate positional arguments.
        result = await self._redis.eval(
            lua_script,
            1,
            self._key,
            self._lock_id,
            str(self._ttl),
        )

        return bool(result)

    async def release(self) -> None:
        """Release lock and stop auto-renewal."""
        await self.stop_auto_renewal()

        lua_script = """
        local current = redis.call('GET', KEYS[1])
        if current == ARGV[1] then
            redis.call('DEL', KEYS[1])
            return 1
        else
            return 0
        end
        """

        result = await self._redis.eval(
            lua_script,
            1,
            self._key,
            self._lock_id,
        )

        if not result:
            logger.warning(
                "Lock %s was not owned when releasing "
                "(may have expired or been stolen)",
                self._key,
            )
