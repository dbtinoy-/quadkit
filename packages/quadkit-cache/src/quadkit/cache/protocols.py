"""Cache protocols module.

This module defines the protocols for cache providers and backends.
These protocols are used for type checking and runtime validation
of cache implementations.

Protocols:
    CacheBackendProtocol: Re-export of CacheBackendProtocol from quadkit-contracts.
    CacheProviderProtocol: Interface for cache provider components.
    CacheHealthCheckProtocol: Interface for cache health checking.
    CacheKeyBuilderProtocol: Interface for cache key generation.
    CacheProtectionStrategyProtocol: Interface for stampede protection.
    CacheSerializerProtocol: Interface for value serialization (cache-specific).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.infra.cache import CacheBackendProtocol as CacheBackendProtocol


@runtime_checkable
class CacheProviderProtocol(Protocol):
    """Protocol for cache providers.

    Providers manage multiple named backends and handle cache
    configuration and lifecycle.

    Methods:
        get_backend: Retrieve a backend by name.
    """

    def get_backend(self, name: str | None = None) -> CacheBackendProtocol:
        """Get a cache backend by name.

        Args:
            name: The backend name, or None for the default backend.

        Returns:
            The requested cache backend.
        """
        ...


@runtime_checkable
class CacheHealthCheckProtocol(Protocol):
    """Protocol for cache health checkers.

    Health checkers verify that cache backends are operational
    and report their status.

    Methods:
        check_health: Perform a health check on the cache.
    """

    async def check_health(self) -> dict[str, Any]:
        """Check the health of the cache.

        Returns:
            A dictionary with health status information.
        """
        ...


@runtime_checkable
class CacheKeyBuilderProtocol(Protocol):
    """Protocol for cache key builders.

    Key builders generate consistent cache keys from various
    inputs like function arguments or query parameters.

    Methods:
        build_key: Generate a cache key from components.
    """

    def build_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """Build a cache key from components.

        Args:
            prefix: Key prefix (e.g., function name).
            *args: Positional arguments to include in the key.
            **kwargs: Keyword arguments to include in the key.

        Returns:
            A formatted cache key string.
        """
        ...


@runtime_checkable
class CacheProtectionStrategyProtocol(Protocol):
    """Protocol for cache protection strategies.

    Protection strategies prevent cache stampedes by controlling
    concurrent access to cache population.

    Methods:
        should_protect: Determine if a key should be protected.
    """

    async def should_protect(self, key: str) -> bool:
        """Check if stampede protection should be applied.

        Args:
            key: The cache key to check.

        Returns:
            True if protection should be applied to this key.
        """
        ...


@runtime_checkable
class CacheSerializerProtocol(Protocol):
    """Cache-specific protocol for value serializers.

    Serializers convert Python objects to and from byte/string representations
    suitable for storage in cache backends.

    Note:
        This protocol is cache-specific (returns bytes | str). For the
        canonical AsyncStringSerializerProtocol protocol, use quadkit.contracts.cache.AsyncStringSerializerProtocol.

    Methods:
        serialize: Convert a value to string representation.
        deserialize: Convert string back to Python object.
    """

    def serialize(self, value: Any) -> bytes | str:
        """Serialize a Python object.

        Args:
            value: The value to serialize.

        Returns:
            Serialized representation as bytes or string.
        """
        ...

    def deserialize(self, data: bytes | str) -> Any:
        """Deserialize data back to a Python object.

        Args:
            data: The serialized data.

        Returns:
            The reconstructed Python object.
        """
        ...


__all__ = [
    "CacheBackendProtocol",
    "CacheHealthCheckProtocol",
    "CacheKeyBuilderProtocol",
    "CacheProtectionStrategyProtocol",
    "CacheProviderProtocol",
    "CacheSerializerProtocol",
]
