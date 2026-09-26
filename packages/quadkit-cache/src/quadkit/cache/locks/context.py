from __future__ import annotations

from typing import Any
import uuid

from quadkit.cache.exceptions import LockAcquisitionError
from quadkit.cache.locks.auto_renewing import AutoRenewingLock


class LockContextManager:
    """Async context manager for distributed locks."""

    def __init__(
        self,
        redis: Any,
        key: str,
        ttl: int,
        auto_renew: bool,
    ) -> None:
        self._redis: Any = redis
        self._key = key
        self._ttl = ttl
        self._auto_renew = auto_renew
        self._lock: AutoRenewingLock | None = None

    async def __aenter__(self) -> AutoRenewingLock:
        lock_id = str(uuid.uuid4())

        acquired = await self._redis.set(
            self._key,
            lock_id,
            ex=self._ttl,
            nx=True,
        )

        if not acquired:
            raise LockAcquisitionError(f"Could not acquire lock: {self._key}")

        self._lock = AutoRenewingLock(
            self._redis,
            key=self._key,
            lock_id=lock_id,
            ttl=self._ttl,
            auto_renew=self._auto_renew,
        )

        await self._lock.start_auto_renewal()

        return self._lock

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if self._lock:
            await self._lock.release()
