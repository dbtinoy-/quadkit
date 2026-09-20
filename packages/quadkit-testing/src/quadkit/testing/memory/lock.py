"""In-memory distributed lock implementation.

Provides an in-memory implementation of DistributedLockProtocol for testing
and local development. Note that this implementation is process-local
and does not coordinate across multiple processes. For true distributed
locking, use RedisLock or database-backed implementations.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import time
from types import TracebackType
from typing import Self
from uuid import uuid4

from quadkit.contracts.core.lock import DistributedLockProtocol, LockInfo
from quadkit.contracts.exceptions.components import LockAcquisitionError
from quadkit.logging import get_logger

logger = get_logger(__name__)


@dataclass
class _LockEntry:
    """Internal representation of a held lock."""

    holder_id: str
    acquired_at: float
    expires_at: float


class InMemoryLockStore:
    """Holds the shared lock state for :class:`InMemoryDistributedLock` instances.

    Multiple ``InMemoryDistributedLock`` instances that reference the same
    ``InMemoryLockStore`` share a consistent view of which resources are locked.
    Inject the same store into all locks that must coordinate with each other.
    """

    def __init__(self) -> None:
        self._locks: dict[str, _LockEntry] = {}
        self._global_lock: asyncio.Lock = asyncio.Lock()


class InMemoryDistributedLock(DistributedLockProtocol):
    """In-memory distributed lock for testing and local development.

    This implementation provides lock semantics within a single process.
    It is NOT suitable for distributed scenarios across multiple processes
    or machines - use RedisLock or database locks for that.

    Features:
    - TTL-based automatic expiration
    - Context manager support
    - Blocking and non-blocking acquire
    - Lock extension

    Example::

        lock = InMemoryDistributedLock("resource-123", ttl=30.0)

        # Context manager (preferred)
        async with lock:
            await process()

        # Non-blocking
        if await lock.acquire():
            try:
                await process()
            finally:
                await lock.release()

        # Blocking with timeout
        if await lock.acquire_blocking(timeout=5.0):
            try:
                await process()
            finally:
                await lock.release()
    """

    def __init__(
        self,
        resource: str = "",
        *,
        ttl: float = 30.0,
        holder_id: str | None = None,
        store: InMemoryLockStore | None = None,
    ) -> None:
        """Initialize the lock.

        Args:
            resource: Unique identifier for the resource to lock
            ttl: Time-to-live in seconds (auto-expiration)
            holder_id: Unique identifier for this lock holder.
                Defaults to a random UUID.
            store: Shared lock store. Locks coordinate only when they are
                given the same store; without one this lock gets a private
                store, so tests never share lock state by accident. Pass an
                explicit :class:`InMemoryLockStore` to the locks that must
                coordinate with each other.
        """
        self.resource = resource
        self.ttl = ttl
        self.holder_id = holder_id or str(uuid4())
        self._held = False
        self._store: InMemoryLockStore = (
            store if store is not None else InMemoryLockStore()
        )

    async def acquire(self) -> bool:
        """Attempt to acquire the lock non-blocking.

        Returns:
            True if lock was acquired, False if already held
        """
        async with self._store._global_lock:
            # Check if lock exists and is not expired
            existing = self._store._locks.get(self.resource)
            if existing:
                if time() < existing.expires_at:
                    # Lock is held and not expired
                    logger.debug(
                        "lock_acquire_failed",
                        resource=self.resource,
                        holder=existing.holder_id,
                    )
                    return False
                # Lock expired, can steal it
                logger.debug("lock_expired", resource=self.resource)

            # Acquire the lock
            now = time()
            self._store._locks[self.resource] = _LockEntry(
                holder_id=self.holder_id,
                acquired_at=now,
                expires_at=now + self.ttl,
            )
            self._held = True

            logger.debug(
                "lock_acquired",
                resource=self.resource,
                holder=self.holder_id,
                ttl=self.ttl,
            )
            return True

    async def acquire_blocking(self, timeout: float | None = None) -> bool:
        """Attempt to acquire the lock with optional timeout.

        Args:
            timeout: Maximum seconds to wait. None means wait forever.

        Returns:
            True if lock was acquired, False if timeout expired
        """
        start_time = time()

        while True:
            if await self.acquire():
                return True

            # Check timeout
            if timeout is not None:
                elapsed = time() - start_time
                if elapsed >= timeout:
                    logger.debug(
                        "lock_acquire_timeout",
                        resource=self.resource,
                        timeout=timeout,
                    )
                    return False

            # Wait a bit before retrying
            await asyncio.sleep(0.1)

    async def release(self) -> bool:
        """Release the lock.

        Returns:
            True if lock was released by this call,
            False if lock was not held by us or already expired
        """
        async with self._store._global_lock:
            existing = self._store._locks.get(self.resource)

            if not existing:
                self._held = False
                return False

            if existing.holder_id != self.holder_id:
                # We don't hold this lock
                logger.warning(
                    "lock_release_not_held",
                    resource=self.resource,
                    attempted_holder=self.holder_id,
                    actual_holder=existing.holder_id,
                )
                self._held = False
                return False

            # Release the lock
            del self._store._locks[self.resource]
            self._held = False

            logger.debug(
                "lock_released",
                resource=self.resource,
                holder=self.holder_id,
            )
            return True

    async def is_held(self) -> bool:
        """Check if this instance currently holds the lock.

        Returns:
            True if this instance holds the lock
        """
        async with self._store._global_lock:
            if not self._held:
                return False

            existing = self._store._locks.get(self.resource)
            if not existing:
                self._held = False
                return False

            if existing.holder_id != self.holder_id:
                self._held = False
                return False

            # Check expiration
            if time() >= existing.expires_at:
                # Lock expired, clean it up
                del self._store._locks[self.resource]
                self._held = False
                return False

            return True

    async def extend(self, additional_time: float) -> bool:
        """Extend the lock TTL.

        Args:
            additional_time: Seconds to add to the TTL

        Returns:
            True if TTL was extended, False if lock not held
        """
        async with self._store._global_lock:
            existing = self._store._locks.get(self.resource)

            if not existing or existing.holder_id != self.holder_id:
                return False

            existing.expires_at += additional_time

            logger.debug(
                "lock_extended",
                resource=self.resource,
                holder=self.holder_id,
                additional_time=additional_time,
                new_expires=existing.expires_at,
            )
            return True

    async def __aenter__(self) -> Self:
        """Enter context manager, acquiring the lock.

        Raises:
            LockAcquisitionError: If lock cannot be acquired
        """
        if not await self.acquire():
            raise LockAcquisitionError(
                resource=self.resource,
                message=f"Could not acquire lock on '{self.resource}'",
            )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, releasing the lock."""
        await self.release()

    def get_info(self) -> LockInfo | None:
        """Get information about the lock.

        Returns:
            LockInfo if lock is held, None otherwise
        """
        existing = self._store._locks.get(self.resource)
        if not existing:
            return None

        return LockInfo(
            resource=self.resource,
            holder=existing.holder_id,
            acquired_at=existing.acquired_at,
            expires_at=existing.expires_at,
        )

    @classmethod
    async def force_release(
        cls,
        resource: str,
        *,
        store: InMemoryLockStore,
    ) -> bool:
        """Force release a lock regardless of holder.

        Use with caution - this bypasses normal ownership checks.

        Args:
            resource: The resource to unlock
            store: The lock store holding the lock — locks own their state, so
                the caller names the store explicitly.

        Returns:
            True if a lock was released, False if no lock existed
        """
        _store = store
        async with _store._global_lock:
            if resource in _store._locks:
                del _store._locks[resource]
                logger.warning("lock_force_released", resource=resource)
                return True
            return False

    @classmethod
    def get_all_locks(
        cls,
        *,
        store: InMemoryLockStore,
    ) -> dict[str, LockInfo]:
        """Get information about all held locks.

        Args:
            store: The lock store to query.

        Returns:
            Dictionary mapping resource names to LockInfo
        """
        _store = store
        result = {}
        now = time()

        for resource, entry in _store._locks.items():
            if now < entry.expires_at:
                result[resource] = LockInfo(
                    resource=resource,
                    holder=entry.holder_id,
                    acquired_at=entry.acquired_at,
                    expires_at=entry.expires_at,
                )

        return result


class InMemoryAsyncLock:
    """In-process async mutual-exclusion lock backed by :class:`asyncio.Lock`.

    Provides the kernel-side implementation of
    :class:`quadkit.contracts.lock.AsyncLockProtocol` for tasks that need a
    lightweight, single-process lock without any distributed coordination.

    Thread safety: this class inherits the single-event-loop constraints of
    ``asyncio.Lock``; it is **not** safe to share across threads.

    Example::

        lock = InMemoryAsyncLock()

        async with lock:
            # critical section
            ...

        # Or explicit acquire/release:
        acquired = await lock.acquire()
        try:
            ...
        finally:
            lock.release()
    """

    __slots__ = ("_lock",)

    def __init__(self) -> None:
        self._lock: asyncio.Lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire the lock, blocking until it is available.

        Returns:
            Always ``True`` once the lock is held.
        """
        await self._lock.acquire()
        return True

    def release(self) -> None:
        """Release the lock.

        Raises:
            RuntimeError: If the lock is not currently held.
        """
        self._lock.release()

    def locked(self) -> bool:
        """Return ``True`` if the lock is currently held.

        Returns:
            Boolean indicating whether the lock is acquired.
        """
        return self._lock.locked()

    async def __aenter__(self) -> Self:
        """Acquire the lock on context entry."""
        await self._lock.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Release the lock on context exit regardless of exceptions."""
        self._lock.release()
