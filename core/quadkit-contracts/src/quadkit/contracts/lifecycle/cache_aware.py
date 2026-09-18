from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheAwareProtocol(Protocol):
    """Protocol for cache-aware operations."""

    async def invalidate_cache(
        self,
        keys: list[str] | None = None,
        patterns: list[str] | None = None,
    ) -> None: ...

    async def get_cache_info(self) -> dict[str, Any]: ...


__all__ = ["CacheAwareProtocol"]
