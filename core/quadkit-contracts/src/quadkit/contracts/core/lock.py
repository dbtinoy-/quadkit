"""Distributed Lock protocol for Quadkit Framework.

Provides the DistributedLockProtocol protocol for distributed locking across
multiple processes or services. Implementations may use Redis,
PostgreSQL advisory locks, ZooKeeper, or other coordination services.

Example::

    from quadkit.contracts.core.lock import DistributedLockProtocol

    async def process_with_lock(lock: DistributedLockProtocol) -> None:
        if await lock.acquire():
            try:
                # Critical section - only one process holds the lock
                await process_data()
            finally:
                await lock.release()
        else:
            logger.info("Could not acquire lock, skipping")

    # Or use as context manager
    async with lock:
        await process_data()
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager
    from types import TracebackType


@runtime_checkable
class DistributedLockProtocol(Protocol):
    """Protocol for distributed locking.

    Distributed locks coordinate access to shared resources across
    multiple processes, threads, or services. They provide:

    - Mutual exclusion: Only one holder at a time
    - Safety: Locks expire after a TTL to prevent deadlocks
    - Non-blocking acquire: Returns immediately if lock is held

    Implementations must be safe for use in async contexts and
    handle network partitions gracefully.

    Example::

        lock = RedisLock(redis, "my-resource", ttl=30)

        # Non-blocking acquire
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

        # Context manager (preferred)
        async with lock:
            await process()
    """

    @abstractmethod
    async def acquire(self) -> bool:
        """Attempt to acquire the lock non-blocking.

        Returns immediately with True if the lock was acquired,
        False if the lock is already held by another process.

        Returns:
            True if lock was acquired, False otherwise
        """
        ...

    @abstractmethod
    async def acquire_blocking(self, timeout: float | None = None) -> bool:
        """Attempt to acquire the lock with optional timeout.

        Blocks until the lock is acquired or the timeout expires.

        Args:
            timeout: Maximum seconds to wait. None means wait forever.

        Returns:
            True if lock was acquired, False if timeout expired
        """
        ...

    @abstractmethod
    async def release(self) -> bool:
        """Release the lock.

        Returns:
            True if lock was released by this call,
            False if lock was not held or already expired
        """
        ...

    @abstractmethod
    async def is_held(self) -> bool:
        """Check if this instance currently holds the lock.

        Returns:
            True if this instance holds the lock
        """
        ...

    @abstractmethod
    async def extend(self, additional_time: float) -> bool:
        """Extend the lock TTL.

        Useful for long-running operations that need to
        prevent the lock from expiring mid-operation.

        Args:
            additional_time: Seconds to add to the TTL

        Returns:
            True if TTL was extended, False if lock not held
        """
        ...

    @abstractmethod
    async def __aenter__(self) -> DistributedLockProtocol:
        """Enter context manager, acquiring the lock.

        Raises:
            LockAcquisitionError: If lock cannot be acquired
        """
        ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, releasing the lock."""
        ...


@dataclass(frozen=True)
class LockInfo:
    """Immutable snapshot of a distributed lock's state.

    Attributes:
        resource: The resource being locked.
        holder: Identifier of the current holder.
        acquired_at: Unix timestamp when the lock was acquired.
        expires_at: Unix timestamp when the lock expires (TTL).
        metadata: Additional implementation-specific data.
    """

    resource: str
    holder: str | None = None
    acquired_at: float | None = None
    expires_at: float | None = None
    metadata: dict[str, Any] | None = None

    @property
    def is_expired(self) -> bool:
        """Check if the lock has expired."""
        from time import time

        if self.expires_at is None:
            return False
        return time() > self.expires_at

    @property
    def ttl_remaining(self) -> float | None:
        """Get remaining TTL in seconds."""
        from time import time

        if self.expires_at is None:
            return None
        return max(0.0, self.expires_at - time())


@runtime_checkable
class AsyncLockProtocol(Protocol):
    """Protocol for a simple in-process async mutual-exclusion lock.

    Mirrors the interface of :class:`asyncio.Lock`.  Implementations are
    **single-process** (i.e. not distributed); use :class:`DistributedLockProtocol`
    or :class:`LockManagerProtocol` when cross-process coordination is
    required.

    Example::

        from quadkit.contracts.core.lock import AsyncLockProtocol

        async def protected(lock: AsyncLockProtocol) -> None:
            async with lock:
                await do_critical_work()

    Container registration::

        container.singleton(AsyncLockProtocol, InMemoryAsyncLock)
    """

    async def acquire(self) -> bool:
        """Acquire the lock, blocking until it becomes available.

        Returns:
            ``True`` once the lock has been acquired.
        """
        ...

    def release(self) -> None:
        """Release the lock.

        Raises:
            RuntimeError: If the lock is not currently held.
        """
        ...

    def locked(self) -> bool:
        """Return ``True`` if the lock is currently held by any coroutine."""
        ...

    async def __aenter__(self) -> Self:
        """Acquire the lock on context entry."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Release the lock on context exit."""
        ...


@runtime_checkable
class LockManagerProtocol(Protocol):
    """Protocol for a process-local or distributed lock manager.

    A lock manager creates and tracks named locks for coordinating mutual
    exclusion of concurrent operations.  Callers use :meth:`acquire` to
    obtain a per-key async context manager.

    Implementations range from purely in-memory (single-process deduplication)
    to Redis-backed or advisory-lock-backed distributed variants.

    Example::

        from quadkit.contracts.core.lock import LockManagerProtocol

        async def process(manager: LockManagerProtocol) -> None:
            async with manager.acquire("resource:42", timeout=30):
                await do_work()

    Container registration::

        container.singleton(LockManagerProtocol, InMemoryLockManager)
    """

    @abstractmethod
    def acquire(
        self, key: str, timeout: float = 60.0
    ) -> AbstractAsyncContextManager[Any]:
        """Return an async context manager that holds the named lock.

        The caller **must** use the returned value as an async context manager.
        The lock is acquired on ``__aenter__`` and released on ``__aexit__``.

        Args:
            key: Unique, stable identifier for the resource to protect.
            timeout: Informational TTL in seconds; implementations may use
                this to automatically expire stale locks.

        Returns:
            An ``AbstractAsyncContextManager`` for the named lock.
        """
        ...


__all__ = [
    "AsyncLockProtocol",
    "DistributedLockProtocol",
    "LockInfo",
    "LockManagerProtocol",
]
