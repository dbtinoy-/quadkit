"""Cached repository wrapper with transparent result caching.

Wraps any RepositoryProtocol with a read-through cache that automatically
invalidates on write operations.

Example:
    from quadkit.sql.repositories.cached import CachedRepository

    cached_repo = CachedRepository(
        inner=user_repo,
        cache=redis_backend,  # Implements quadkit.contracts.cache.protocols.CacheBackendProtocol
        ttl=300,
    )
    user = await cached_repo.find_by_id(user_id)  # cache miss → DB
    user = await cached_repo.find_by_id(user_id)  # cache hit
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, cast

from quadkit import serialization as json
from quadkit.logging import get_logger
from quadkit.security.hashing import ambient as hashing

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
    from quadkit.contracts.security import HasherProtocol

logger = get_logger(__name__)

T = TypeVar("T")
K = TypeVar("K")


class CachedRepository:
    """RepositoryProtocol wrapper with transparent read-through caching.

    Intercepts read operations to serve from cache when possible,
    and automatically invalidates cache on write operations.
    """

    def __init__(
        self,
        inner: Any,
        cache: CacheBackendProtocol,
        *,
        ttl: int = 300,
        prefix: str | None = None,
        hasher: HasherProtocol | None = None,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl
        self._prefix = prefix or getattr(
            inner,
            "_table",
            "entity",
        )
        self._hasher = hasher

    async def _get_version(self) -> int:
        version_key = f"{self._prefix}:__version__"
        result = await self._cache.get(version_key)
        version = result.unwrap_or(None)
        if version is None:
            version = 1
            await self._cache.set(version_key, version, ttl=86400 * 30)
        return version

    async def _increment_version(self) -> None:
        version_key = f"{self._prefix}:__version__"
        result = await self._cache.get(version_key)
        version = result.unwrap_or(None)
        if version is None:
            version = 0
        await self._cache.set(version_key, version + 1, ttl=86400 * 30)

    async def _cache_key(self, suffix: str) -> str:
        version = await self._get_version()
        return f"{self._prefix}:v{version}:{suffix}"

    async def find_by_id(self, key: Any) -> Any | None:
        """Find by ID with cache."""
        cache_key = await self._cache_key(f"id:{key}")
        get_result = await self._cache.get(cache_key)
        cached = get_result.unwrap_or(None)
        if cached is not None:
            return cached

        result = await self._inner.find_by_id(key)
        if result is not None:
            await self._cache.set(cache_key, result, ttl=self._ttl)
        return result

    async def find_many(self, **kwargs: Any) -> list[Any]:
        """Find many with cache (query-level caching)."""
        cache_key = await self._cache_key(
            f"many:{_hash_kwargs(kwargs)}",
        )
        get_result = await self._cache.get(cache_key)
        cached = get_result.unwrap_or(None)
        if cached is not None:
            return cast("list[Any]", cached)

        results = await self._inner.find_many(**kwargs)
        await self._cache.set(cache_key, results, ttl=self._ttl)
        return cast("list[Any]", results)

    async def count(self, **kwargs: Any) -> int:
        """Count with cache."""
        cache_key = await self._cache_key(
            f"count:{_hash_kwargs(kwargs)}",
        )
        get_result = await self._cache.get(cache_key)
        cached = get_result.unwrap_or(None)
        if cached is not None:
            return cast("int", cached)

        result = await self._inner.count(**kwargs)
        await self._cache.set(cache_key, result, ttl=self._ttl)
        return cast("int", result)

    # Write-through operations (invalidate cache)

    async def create(self, entity: Any) -> Any:
        result = await self._inner.create(entity)
        await self._invalidate_all()
        return result

    async def update(self, entity: Any) -> Any:
        result = await self._inner.update(entity)
        key = self._get_entity_key(entity)
        if key:
            cache_key = await self._cache_key(f"id:{key}")
            await self._cache.delete(cache_key)
        await self._invalidate_all()
        return result

    async def delete_by_id(self, key: Any) -> bool:
        result = await self._inner.delete_by_id(key)
        cache_key = await self._cache_key(f"id:{key}")
        await self._cache.delete(cache_key)
        await self._invalidate_all()
        return cast("bool", result)

    async def _invalidate_all(self) -> None:
        """Invalidate all cached queries for this entity."""
        await self._increment_version()

    def _get_entity_key(self, entity: Any) -> Any | None:
        if hasattr(entity, "id"):
            return entity.id
        if isinstance(entity, dict):
            return entity.get("id")
        return None

    def __getattr__(self, name: str) -> Any:
        """Proxy all other methods to the inner repository."""
        return getattr(self._inner, name)


def _hash_kwargs(kwargs: dict[str, Any], hasher: HasherProtocol | None = None) -> str:
    """Hash kwargs deterministically for cache key."""
    serialized = json.dumps(kwargs, sort_keys=True, default=str)
    if hasher is not None:
        return hasher.digest(serialized)[:12]
    return hashing.hash_hex(serialized)[:12]
