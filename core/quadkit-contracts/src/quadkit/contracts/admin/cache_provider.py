"""CacheProviderProtocol — admin-side cache facade."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheProviderProtocol(Protocol):
    """Protocol for admin data-layer cache providers.

    Provides basic get/set/delete/invalidate operations with TTL and tag
    support.  Tags are used for grouped invalidation.

    This is the admin-internal cache abstraction, distinct from
    ``quadkit.contracts.cache.CacheBackend`` which is the framework-wide
    Redis/memory cache contract.
    """

    async def get(self, key: str) -> Any | None: ...

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
        tags: list[str] | None = None,
    ) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def invalidate_tags(self, tags: list[str]) -> None: ...


__all__ = ["CacheProviderProtocol"]
