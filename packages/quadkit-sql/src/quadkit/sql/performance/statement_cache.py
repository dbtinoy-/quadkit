"""LRU statement cache for prepared SQL statements.

Caches frequently-used SQL strings to avoid repeated parsing/planning.

Example:
    cache = StatementCache(max_size=200)
    prepared = await cache.get_or_prepare(sql, provider)
    cache.invalidate(sql)
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

logger = get_logger(__name__)


@dataclass
class CachedStatement:
    """A cached prepared statement entry."""

    sql: str
    prepared: Any
    created_at: float
    hit_count: int = 0


class StatementCache:
    """LRU cache for prepared statements."""

    def __init__(
        self,
        max_size: int = 100,
    ) -> None:
        self._cache: OrderedDict[str, CachedStatement] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    async def get_or_prepare(
        self,
        sql: str,
        provider: Any,
    ) -> Any:
        """Get a cached prepared statement or prepare a new one.

        Args:
            sql: The SQL query to prepare.
            provider: Database provider with a prepare() method.

        Returns:
            The prepared statement object.
        """
        if sql in self._cache:
            entry = self._cache[sql]
            entry.hit_count += 1
            self._hits += 1
            self._cache.move_to_end(sql)
            return entry.prepared

        self._misses += 1

        # Prepare new statement
        prepared = None
        if hasattr(provider, "prepare"):
            prepared = await provider.prepare(sql)
        else:
            prepared = sql  # Fallback: return raw SQL

        # Evict LRU if at capacity
        if len(self._cache) >= self._max_size:
            evicted_key, evicted = self._cache.popitem(last=False)
            logger.debug(
                "Evicted statement from cache: %s (hits=%d)",
                evicted_key[:60],
                evicted.hit_count,
            )

        self._cache[sql] = CachedStatement(
            sql=sql,
            prepared=prepared,
            created_at=ambient_clock.monotonic(),
        )

        return prepared

    def invalidate(self, sql: str) -> None:
        """Remove a specific statement from the cache."""
        self._cache.pop(sql, None)

    def invalidate_all(self) -> None:
        """Clear every entry from the statement cache.

        Call this after schema changes or migrations to ensure no stale
        prepared statements referring to altered/dropped objects remain in
        the cache.  Queries will be re-prepared on next use.
        """
        count = len(self._cache)
        self._cache.clear()
        logger.debug("Statement cache fully invalidated (%d entries removed)", count)

    def clear(self) -> None:
        """Clear all cached statements."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
            "top_queries": [
                {"sql": e.sql[:80], "hits": e.hit_count}
                for e in sorted(
                    self._cache.values(),
                    key=lambda x: x.hit_count,
                    reverse=True,
                )[:10]
            ],
        }
