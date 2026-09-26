"""Root hook payload surface for quadkit-cache.

Defines canonical payload dataclasses for cache-lifecycle hook points. Actual
hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "CacheConnectedHook",
    "CacheDisconnectedHook",
    "CacheEntryEvictedHook",
    "CacheHitHook",
    "CacheMissHook",
]


@dataclass(frozen=True, kw_only=True)
class CacheConnectedHook:
    """Payload fired when the cache backend establishes its connection.

    Attributes:
        backend: Identifier of the backend that connected (e.g. ``"redis"``).
    """

    backend: str


@dataclass(frozen=True, kw_only=True)
class CacheDisconnectedHook:
    """Payload fired when the cache backend disconnects or is shut down.

    Attributes:
        backend: Identifier of the backend that disconnected.
    """

    backend: str


@dataclass(frozen=True, kw_only=True)
class CacheHitHook:
    """Payload fired when a cache lookup returns a stored value.

    Attributes:
        key: The logical cache key that produced a hit.
        backend: Identifier of the backend that served the hit.
    """

    key: str
    backend: str


@dataclass(frozen=True, kw_only=True)
class CacheMissHook:
    """Payload fired when a cache lookup does not find a stored value.

    Attributes:
        key: The logical cache key that missed.
        backend: Identifier of the backend that served the miss.
    """

    key: str
    backend: str


@dataclass(frozen=True, kw_only=True)
class CacheEntryEvictedHook:
    """Payload fired when a cache entry is evicted (TTL expiry or explicit removal).

    Attributes:
        key: The cache key that was evicted.
        backend: Identifier of the backend that performed the eviction.
    """

    key: str
    backend: str
