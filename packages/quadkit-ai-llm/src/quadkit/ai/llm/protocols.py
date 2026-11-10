"""LLM-specific protocols owned by quadkit-ai-llm."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMCacheProtocol(Protocol):
    """Protocol for LLM cache implementations."""

    async def get(self, key: str | dict[str, Any]) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key (string or structured dict).

        Returns:
            Cached value, or ``None`` if not present.
        """
        ...

    async def set(
        self,
        key: str | dict[str, Any],
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key (string or structured dict).
            value: Value to store.
            ttl: Optional time-to-live in seconds.
        """
        ...

    async def delete(self, key: str | dict[str, Any]) -> bool:
        """Delete entry from cache.

        Args:
            key: Cache key to remove.

        Returns:
            ``True`` if the key existed and was removed, ``False`` otherwise.
        """
        ...

    async def clear(self) -> None:
        """Clear all entries."""
        ...

    def get_stats(self) -> dict[str, Any]:
        """Return cache statistics.

        Returns:
            Mapping of statistic name to value.
        """
        ...


__all__ = ["LLMCacheProtocol"]
