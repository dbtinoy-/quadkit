"""In-process locking for task deduplication.

Provides process-local locks to prevent duplicate task execution within a
single worker process.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
import time
from typing import Any, Self

from quadkit.tasks.exceptions import TaskLockHeldError

_LOCK_POLL_INITIAL_DELAY = 0.01
_LOCK_POLL_MAX_DELAY = 0.25


class InMemoryLock:
    """In-memory lock for preventing duplicate task execution within a single process.

    Note: This is NOT a distributed lock. For true distributed locking across
    multiple processes/servers, use a Redis-based or database-based lock implementation.

    Example:
        ```python
        lock_manager = LockManager()
        async with lock_manager.acquire("user:123:sync", timeout=60):
            await sync_user_data(user_id=123)
        ```
    """

    def __init__(
        self,
        key: str,
        timeout: float,
        locks_dict: dict[str, tuple[float, asyncio.Lock]],
        locks_lock: asyncio.Lock,
    ):
        """Initialize in-memory lock.

        Args:
            key: Unique lock key
            timeout: Lock expiry in seconds; the key is considered expired
                once this many seconds have passed since acquisition and is
                purged on the next acquire attempt
            locks_dict: Shared locks dictionary (from LockManager)
            locks_lock: Shared lock for accessing locks_dict (from LockManager)
        """
        self.key = key
        self.timeout = timeout
        self.acquired = False
        self._lock: asyncio.Lock | None = None
        self._locks = locks_dict
        self._locks_lock = locks_lock

    async def acquire(self) -> bool:
        """Try to acquire the lock without waiting.

        Expired lock entries are purged before the ownership check, so an
        expired key can be re-acquired immediately.

        Returns:
            True if the lock was acquired, False if the key is already held.
        """
        async with self._locks_lock:
            # Clean up expired locks using monotonic time
            now = time.monotonic()
            expired = [k for k, (expiry, _) in self._locks.items() if expiry < now]
            for k in expired:
                del self._locks[k]

            # Try to acquire
            if self.key not in self._locks:
                lock = asyncio.Lock()
                await lock.acquire()
                self._locks[self.key] = (now + self.timeout, lock)
                self._lock = lock
                self.acquired = True
                return True

            return False

    async def try_acquire(self) -> bool:
        """Try to acquire lock without waiting.

        Returns:
            True if acquired, False if already held
        """
        return await self.acquire()

    async def acquire_wait(self, timeout: float | None = None) -> bool:
        """Block until the lock is acquired or *timeout* seconds elapse.

        Polls :meth:`acquire` with capped exponential backoff between
        attempts, so the caller never busy-waits. Each poll purges expired
        lock entries, so a timed-out holder loses the key to a waiting
        caller.

        Args:
            timeout: Maximum seconds to wait for the lock. When ``None``,
                wait until the lock is acquired or the calling task is
                cancelled.

        Returns:
            True when the lock was acquired, False if *timeout* elapsed
            without acquiring it.

        Example:
            ```python
            lock = lock_manager.acquire("user:123:sync", timeout=60)
            if await lock.acquire_wait(timeout=30):
                try:
                    await sync_user_data(user_id=123)
                finally:
                    await lock.release()
            ```
        """
        deadline = time.monotonic() + timeout if timeout is not None else None
        delay = _LOCK_POLL_INITIAL_DELAY
        while True:
            if await self.acquire():
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            sleep_for = delay
            if deadline is not None:
                sleep_for = min(delay, max(deadline - time.monotonic(), 0.0))
            if sleep_for > 0.0:
                await asyncio.sleep(sleep_for)
            delay = min(delay * 2, _LOCK_POLL_MAX_DELAY)

    async def release(self) -> None:
        """Release the lock.

        Only the registry entry that still belongs to this instance is
        removed: a stale release — after this lock's entry expired and the
        key was re-acquired by a different caller — leaves the current
        holder's entry untouched and only frees this instance's own
        ``asyncio.Lock``.
        """
        if self.acquired and self._lock:
            async with self._locks_lock:
                stored = self._locks.get(self.key)
                if stored is not None and stored[1] is self._lock:
                    del self._locks[self.key]
                self._lock.release()
            self.acquired = False

    async def __aenter__(self) -> Self:
        """Enter the lock, blocking until it is acquired.

        Equivalent to :meth:`acquire_wait` with no timeout.
        """
        await self.acquire_wait()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit."""
        await self.release()


class LockManager:
    """Manager for in-memory task-deduplication locks.

    Maintains a mapping of *key → (expiry_timestamp, asyncio.Lock)* and
    exposes the locks via :meth:`acquire`.  Use it as an async context manager
    to prevent the same logical task from running concurrently.

    **Lock hierarchy and fallback order**

    ``LockManager`` is a *process-local* lock only.  It protects against
    concurrent execution of the same task **within a single worker process**
    but provides no cross-process or cross-host guarantees.  For distributed
    locking across multiple workers or hosts, pair this with a Redis-based or
    database-backed lock (see ``the optional provider``).

    **Contention behaviour**

    * :meth:`InMemoryLock.acquire` is *non-blocking*: when the key is
      already held it returns ``False`` immediately, without suspending
      the caller. To wait for a key to become free, use
      :meth:`InMemoryLock.acquire_wait` or enter the lock with
      ``async with``.
    * The *timeout* value is enforced, not informational: an entry is
      considered expired once ``acquisition time + timeout`` has passed,
      and the next :meth:`InMemoryLock.acquire` call purges expired
      entries — freeing the key for a new acquirer even if the original
      holder never calls :meth:`InMemoryLock.release`.

    **Registration**

    Register as a container ``singleton`` so all workers within the same
    process share the same lock table::

        container.singleton(LockManager, LockManager)

    Example:
        ```python
        lock_manager = LockManager()
        async with lock_manager.acquire("user:123:sync", timeout=60):
            await sync_user_data(user_id=123)
        ```
    """

    def __init__(self) -> None:
        self._locks: dict[str, tuple[float, asyncio.Lock]] = {}
        self._locks_lock: asyncio.Lock = asyncio.Lock()

    def acquire(self, key: str, timeout: float = 60.0) -> InMemoryLock:
        """Create a lock for the given key.

        Args:
            key: Unique lock key
            timeout: Lock timeout in seconds

        Returns:
            InMemoryLock instance
        """
        return InMemoryLock(key, timeout, self._locks, self._locks_lock)


class UniqueTask:
    """Decorator for unique task execution.

    Prevents duplicate execution of the same task using in-memory locks.

    By default (``skip_if_locked=True``) a second caller whose lock key is
    already held returns ``None`` immediately. With
    ``skip_if_locked=False`` the second caller blocks until the key is free
    (up to *timeout* seconds), then returns ``None`` if the key is still
    held.

    Example:
        ```python
        lock_manager = LockManager()
        @UniqueTask(
            lock_manager=lock_manager,
            key_func=lambda user_id: f"sync_user:{user_id}",
            timeout=3600
        )
        async def sync_user(user_id: str):
            await sync_user_data(user_id)
        ```
    """

    def __init__(
        self,
        lock_manager: LockManager,
        key_func: Callable[[Any], str],
        timeout: float = 60.0,
        skip_if_locked: bool = True,
    ):
        """Initialize unique task decorator.

        Args:
            lock_manager: LockManager instance for creating locks
            key_func: Function to generate lock key from task args
            timeout: Lock expiry in seconds; also the maximum time the wait
                mode (skip_if_locked=False) blocks for the lock
            skip_if_locked: If True, skip execution (return None) if the
                lock is held; if False, wait up to *timeout* seconds for
                the lock, then skip if it is still held
        """
        self.lock_manager = lock_manager
        self.key_func = key_func
        self.timeout = timeout
        self.skip_if_locked = skip_if_locked

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap *func* so it runs under the lock for its key.

        Args:
            func: The async callable to wrap.

        Returns:
            The wrapped async callable; it returns ``None`` when execution
            is skipped because the lock could not be acquired.
        """

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate lock key
            lock_key = self.key_func(*args, **kwargs)
            lock = self.lock_manager.acquire(lock_key, self.timeout)

            if self.skip_if_locked:
                # Try to acquire, skip if can't
                if not await lock.try_acquire():
                    return None
                try:
                    return await func(*args, **kwargs)
                finally:
                    await lock.release()
            else:
                # Wait for the lock up to the timeout, then skip if still held
                if not await lock.acquire_wait(timeout=self.timeout):
                    return None
                try:
                    return await func(*args, **kwargs)
                finally:
                    await lock.release()

        return wrapper


# Convenience function for creating locks (deprecated - use LockManager instead)
@asynccontextmanager
async def distributed_lock(
    key: str,
    timeout: float = 60.0,
    lock_manager: LockManager | None = None,
) -> AsyncGenerator[InMemoryLock, None]:
    """Context manager for in-memory locks.

    Deprecated: Use LockManager.acquire() instead for better DI integration.

    Args:
        key: Unique lock key
        timeout: Lock timeout in seconds
        lock_manager: Optional LockManager instance (creates new if None)

    Yields:
        InMemoryLock instance

    Example:
        ```python
        manager = LockManager()  # Should be from DI container
        async with distributed_lock("resource:123", lock_manager=manager):
            await process_resource(123)
        ```
    """
    if lock_manager is None:
        lock_manager = LockManager()
    lock = lock_manager.acquire(key, timeout)
    if not await lock.acquire():
        # Yielding a lock that is not actually held would silently run
        # supposedly exclusive code — fail instead.
        raise TaskLockHeldError(
            f"Lock {key!r} is already held",
            details={"key": key, "timeout_seconds": timeout},
            hint="Wait for the holder to release the key, or use "
            "LockManager.acquire(...).acquire_wait() to block instead.",
        )
    try:
        yield lock
    finally:
        await lock.release()
