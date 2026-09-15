"""State storage protocols for Quadkit Framework."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StateStoreProtocol(Protocol):
    """Persistent key-value store for arbitrary application state.

    Supports bulk read/write operations on top of the basic get/set/delete
    primitives. Implementations may use any persistent backend (SQL, Redis,
    blob storage) that satisfies the interface.

    Typical usage::

        state = await container.resolve(StateStoreProtocol)
        await state.set("session:abc123", {"user_id": "u-1"}, ttl=3600)
        data = await state.get("session:abc123")
    """

    async def get(self, key: str) -> Any | None:
        """Get a value by key.

        Args:
            key: The key to retrieve.

        Returns:
            The value if found, None otherwise.
        """
        ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value with optional TTL.

        Args:
            key: The key to set.
            value: The value to store.
            ttl: Optional time-to-live in seconds.
        """
        ...

    async def delete(self, key: str) -> bool:
        """Delete a key.

        Args:
            key: The key to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def exists(self, key: str) -> bool:
        """Check if a key exists.

        Args:
            key: The key to check.

        Returns:
            True if exists, False otherwise.
        """
        ...

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on a key.

        Args:
            key: The key to expire.
            ttl: Time-to-live in seconds.

        Returns:
            True if timeout was set, False if key doesn't exist.
        """
        ...

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for a key.

        Args:
            key: The key to check.

        Returns:
            TTL in seconds, -1 if no expiry, -2 if key doesn't exist.
        """
        ...

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Return a mapping of *keys* → values for all keys that exist.

        Args:
            keys: List of storage keys to fetch.

        Returns:
            Dict containing only keys that were found; absent keys are omitted.
        """
        ...

    async def set_many(self, items: dict[str, Any], ttl: int | None = None) -> None:
        """Persist multiple key-value pairs in a single operation.

        Args:
            items: Mapping of storage keys to JSON-serializable values.
            ttl: Optional time-to-live in seconds applied to all entries.
        """
        ...


__all__ = ["StateStoreProtocol"]
