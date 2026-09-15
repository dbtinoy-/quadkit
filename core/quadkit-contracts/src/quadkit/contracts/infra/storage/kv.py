"""Key-Value Storage protocols.

This module defines the protocols for Key-Value storage backends.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core import HealthCheckResult


class StorageType(StrEnum):
    """Types of storage backends."""

    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"
    DATABASE = "database"
    S3 = "s3"
    OTHER = "other"


@runtime_checkable
class StorageBackendProtocol(Protocol):
    """Protocol for Key-Value storage backends.

    Defines the interface for simple KV storage operations with
    support for namespacing and TTL.
    """

    @property
    def storage_type(self) -> StorageType:
        """Get the type of storage backend."""
        ...

    async def connect(self) -> None:
        """Initialize connection to storage backend."""
        ...

    async def disconnect(self) -> None:
        """Close connection to storage backend."""
        ...

    async def get(self, key: str, namespace: str | None = None) -> Any | None:
        """Get value by key.

        Args:
            key: Storage key.
            namespace: Optional namespace.

        Returns:
            Stored value or None if not found.
        """
        ...

    async def set(
        self,
        key: str,
        value: Any,
        namespace: str | None = None,
        ttl: int | None = None,
    ) -> bool:
        """Set value by key.

        Args:
            key: Storage key.
            value: Value to store (must be serializable).
            namespace: Optional namespace.
            ttl: Time-to-live in seconds.

        Returns:
            True if successful.
        """
        ...

    async def delete(self, key: str, namespace: str | None = None) -> bool:
        """Delete value by key.

        Args:
            key: Storage key.
            namespace: Optional namespace.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def exists(self, key: str, namespace: str | None = None) -> bool:
        """Check if key exists.

        Args:
            key: Storage key.
            namespace: Optional namespace.

        Returns:
            True if exists.
        """
        ...

    async def list_keys(
        self,
        pattern: str | None = None,
        namespace: str | None = None,
    ) -> list[str]:
        """List keys matching pattern.

        Args:
            pattern: Glob-style pattern (e.g., "user:*").
            namespace: Optional namespace.

        Returns:
            List of matching keys.
        """
        ...

    async def clear(self, namespace: str | None = None) -> bool:
        """Clear all keys in namespace.

        Args:
            namespace: Optional namespace.

        Returns:
            True if successful.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check storage health.

        Returns:
            Health check result.
        """
        ...


__all__ = ["StorageBackendProtocol", "StorageType"]
