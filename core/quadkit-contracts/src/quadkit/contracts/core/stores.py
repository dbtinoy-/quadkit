"""Persistent distributed lock store protocol.

Provides advisory, TTL-based distributed locks backed by a persistent store
(SQL advisory locks, a SQL ``locks`` table, Redis, etc.), allowing multiple
services to coordinate exclusive access to shared resources.

Implementations ship in ``the optional provider`` (``the optional provider module``) so they can
share the application's database connection pool without creating a lateral
cross-extension dependency.

Example::

    from quadkit.contracts.core.stores import LockStoreProtocol

    store = await container.resolve(LockStoreProtocol)
    acquired = await store.acquire("billing_job", owner=instance_id, ttl=60)
    if acquired:
        try:
            ...
        finally:
            await store.release("billing_job", owner=instance_id)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LockStoreProtocol(Protocol):
    """Persistent distributed lock store.

    Individual lock handles are *not* returned; all operations are done via
    the lock name and owner identifier.
    """

    async def acquire(self, lock_name: str, owner: str, ttl: int) -> bool:
        """Attempt to acquire the named lock.

        Args:
            lock_name: Globally unique lock identifier.
            owner: Identifier of the requesting owner (e.g. host + PID).
            ttl: Lock time-to-live in seconds.  The lock is automatically
                released after this duration to prevent deadlocks.

        Returns:
            ``True`` if the lock was acquired; ``False`` if it is already held.
        """
        ...

    async def release(self, lock_name: str, owner: str) -> bool:
        """Release the named lock *only if* it is held by *owner*.

        Args:
            lock_name: Globally unique lock identifier.
            owner: Must match the owner that acquired the lock.

        Returns:
            ``True`` if the lock was released; ``False`` if it was not held
            by *owner* or did not exist.
        """
        ...

    async def extend(self, lock_name: str, owner: str, ttl: int) -> bool:
        """Extend the TTL of a currently-held lock.

        Args:
            lock_name: Globally unique lock identifier.
            owner: Must match the owner that currently holds the lock.
            ttl: New time-to-live in seconds from now.

        Returns:
            ``True`` if the extension was applied; ``False`` if the lock was
            not held by *owner*.
        """
        ...


__all__ = ["LockStoreProtocol"]
