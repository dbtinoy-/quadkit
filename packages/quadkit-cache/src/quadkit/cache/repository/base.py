"""
RepositoryProtocol pattern implementations for Quadkit Cache.

This module provides repository patterns that offer domain-specific
caching abstractions on top of the core cache service.
"""

from __future__ import annotations

from abc import ABC
import hashlib
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from quadkit import serialization as json
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.cache.service.core import CacheService
    from quadkit.contracts.data.repository import (
        RepositoryProtocol as AbstractRepository,
    )

logger = get_logger(__name__)

T = TypeVar("T")
K = TypeVar("K")


class CacheRepository(ABC, Generic[T, K]):
    """
    Base class for cache repositories.

    Provides common caching patterns and utilities for domain-specific
    repositories. Follows the RepositoryProtocol pattern for data access abstraction.
    """

    def __init__(
        self,
        cache_service: CacheService,
        namespace: str,
        default_ttl: int | None = None,
    ):
        """
        Initialize the repository.

        Args:
            cache_service: Cache service instance
            namespace: Namespace for cache keys
            default_ttl: Default TTL for cached items
        """
        self.cache_service = cache_service
        self.namespace = namespace
        self.default_ttl = default_ttl

    def _make_key(self, key: K) -> str:
        """Create a namespaced cache key."""
        if isinstance(key, float | int | str):
            return f"{self.namespace}:{key}"
        # For complex keys, create a hash
        key_data = json.dumps(key, sort_keys=True, default=str)
        key_str = key_data.decode("utf-8") if isinstance(key_data, bytes) else key_data
        key_hash = hashlib.blake2b(key_str.encode("utf-8"), digest_size=16).hexdigest()
        return f"{self.namespace}:{key_hash}"

    async def get(self, key: K) -> T | None:
        """
        Get an item from cache.

        Args:
            key: Cache key

        Returns:
            Cached item or None if not found
        """
        cache_key = self._make_key(key)
        return cast("T | None", await self.cache_service.get(cache_key))

    async def set(self, key: K, value: T, ttl: int | None = None) -> bool:
        """
        Set an item in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live (uses default if None)

        Returns:
            True if successful
        """
        cache_key = self._make_key(key)
        effective_ttl = ttl or self.default_ttl
        return await self.cache_service.set(cache_key, value, effective_ttl)

    async def delete(self, key: K) -> bool:
        """
        Delete an item from cache.

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        cache_key = self._make_key(key)
        return await self.cache_service.delete(cache_key)

    async def exists(self, key: K) -> bool:
        """
        Check if an item exists in cache.

        Args:
            key: Cache key

        Returns:
            True if exists
        """
        cache_key = self._make_key(key)
        return await self.cache_service.exists(cache_key)

    async def get_or_set(
        self,
        key: K,
        default_func: Callable[[], T],
        ttl: int | None = None,
    ) -> T:
        """
        Get an item or compute and cache it.

        Args:
            key: Cache key
            default_func: Function to compute value
            ttl: Time-to-live

        Returns:
            Cached or computed value
        """
        cache_key = self._make_key(key)
        effective_ttl = ttl or self.default_ttl
        return cast(
            "T",
            await self.cache_service.get_or_set(
                cache_key,
                default_func,
                effective_ttl,
            ),
        )

    async def invalidate_pattern(self, pattern: str) -> None:
        """
        Invalidate all keys matching a pattern.

        Note: This is a best-effort operation. Not all backends
        support pattern-based invalidation.

        Args:
            pattern: Pattern to match (simple string matching)
        """
        # This would require backend-specific implementation
        # For now, log that pattern invalidation is not supported
        logger.warning(
            "Pattern invalidation not implemented for repository: %s",
            self.namespace,
        )


class EntityRepository(CacheRepository[T, K]):
    """
    RepositoryProtocol for caching domain entities.

    Provides CRUD operations with automatic key generation
    and entity-specific caching patterns.
    """

    def __init__(
        self,
        cache_service: CacheService,
        entity_type: str,
        default_ttl: int | None = None,
        key_field: str = "id",
    ):
        """
        Initialize entity repository.

        Args:
            cache_service: Cache service instance
            entity_type: Type/name of entity (e.g., "user", "product")
            default_ttl: Default TTL for entities
            key_field: Field name to use as cache key
        """
        super().__init__(cache_service, f"entity:{entity_type}", default_ttl)
        self.entity_type = entity_type
        self.key_field = key_field
        self._observed_repository_ids: set[int] = set()

    def _make_entity_key(self, entity: dict[str, Any] | object) -> str:
        """Create cache key from entity."""
        if isinstance(entity, dict):
            key_value = entity.get(self.key_field)
        elif hasattr(entity, self.key_field):
            key_value = getattr(entity, self.key_field)
        else:
            raise ValueError(f"Entity missing key field: {self.key_field}")

        if key_value is None:
            raise ValueError(f"Entity key field {self.key_field} is None")

        return str(key_value)

    async def get_by_id(self, entity_id: K) -> T | None:
        """Get entity by ID."""
        return await self.get(entity_id)

    async def save(self, entity: T, ttl: int | None = None) -> bool:
        """
        Save entity to cache.

        Args:
            entity: Entity to cache
            ttl: Time-to-live

        Returns:
            True if successful
        """
        entity_key = self._make_entity_key(entity)
        return await self.set(entity_key, entity, ttl)  # type: ignore[arg-type]

    async def delete_by_id(self, entity_id: K) -> bool:
        """Delete entity by ID."""
        return await self.delete(entity_id)

    async def invalidate(self, entity_id: K) -> bool:
        """Invalidate the cached entity by ID.

        Removes the entity from the cache, forcing the next read to
        fetch it from the source.  This method is intended to be called
        from ``AbstractRepository.save()`` post-save hooks or event handlers
        to keep the cache in sync with the underlying store.

        Args:
            entity_id: The entity ID whose cached entry to invalidate.

        Returns:
            ``True`` if the entry was removed, ``False`` if it was not cached.
        """
        return await self.delete(entity_id)

    async def invalidate_by_entity(self, entity: T) -> bool:
        """Invalidate the cache entry for *entity* by extracting its key.

        Intended to be registered as a post-save hook on an
        ``AbstractRepository`` so that any persisted entity is automatically
        evicted from this cache layer::

            sql_repo.register_post_save_hook(entity_cache.invalidate_by_entity)

        Args:
            entity: The saved entity whose cache entry should be invalidated.

        Returns:
            ``True`` if the entry was removed, ``False`` if it was not cached.
        """
        entity_id = (
            entity.get(self.key_field)
            if isinstance(entity, dict)
            else getattr(entity, self.key_field, None)
        )
        if entity_id is None:
            return False
        return await self.invalidate(entity_id)

    def observe(self, repository: AbstractRepository) -> None:
        """Wire automatic cache invalidation hooks into a repository.

        MUST be called in ``Provider.boot()`` for every repository that this
        cache repo wraps. Without this call, cache entries will become stale
        after saves and deletes.

        Example usage in a Provider::

            async def boot(self, container: ContainerResolverProtocol) -> None:
                sql_repo = await container.resolve(UserRepositoryProtocol)
                cache_repo = await container.resolve(CachedUserRepository)
                cache_repo.observe(sql_repo)  # Required wiring

        Args:
            repository: The underlying repository whose mutations should
                invalidate this cache's entries.
        """
        repository_id = id(repository)
        if repository_id in self._observed_repository_ids:
            return
        repository.register_post_save_hook(self.invalidate_by_entity)  # type: ignore[attr-defined]
        repository.register_post_delete_hook(self.invalidate)  # type: ignore[attr-defined]
        self._observed_repository_ids.add(repository_id)

    async def get_multiple(self, entity_ids: list[K]) -> dict[K, T]:
        """
        Get multiple entities by IDs.

        Args:
            entity_ids: List of entity IDs

        Returns:
            Dictionary mapping IDs to entities
        """
        # Create cache keys
        cache_keys = [self._make_key(entity_id) for entity_id in entity_ids]

        # Get from cache
        cached_results = await self.cache_service.get_many(cache_keys)

        # Map back to entity IDs
        results = {}
        for entity_id, cache_key in zip(entity_ids, cache_keys, strict=True):
            if cache_key in cached_results:
                results[entity_id] = cached_results[cache_key]

        return results

    async def save_multiple(self, entities: list[T], ttl: int | None = None) -> bool:
        """
        Save multiple entities to cache.

        Args:
            entities: List of entities to cache
            ttl: Time-to-live

        Returns:
            True if all saved successfully
        """
        items = {}
        for entity in entities:
            entity_key = self._make_entity_key(entity)
            cache_key = self._make_key(entity_key)  # type: ignore[arg-type]
            items[cache_key] = entity

        effective_ttl = ttl or self.default_ttl
        return await self.cache_service.set_many(items, effective_ttl)


class QueryRepository(CacheRepository[T, str]):
    """
    RepositoryProtocol for caching query results.

    Provides caching for database queries, API responses,
    and other expensive computations.
    """

    def __init__(
        self,
        cache_service: CacheService,
        query_type: str,
        default_ttl: int | None = None,
    ):
        """
        Initialize query repository.

        Args:
            cache_service: Cache service instance
            query_type: Type of query (e.g., "user_search", "product_list")
            default_ttl: Default TTL for query results
        """
        super().__init__(cache_service, f"query:{query_type}", default_ttl)
        self.query_type = query_type

    def _make_query_key(self, query_params: dict[str, Any]) -> str:
        """Create cache key from query parameters."""
        # Sort parameters for consistent key generation
        sorted_params = sorted(query_params.items())
        # quadkit.serialization.dumps returns bytes (orjson path); blake2b also
        # expects bytes — no intermediate .encode() step required.
        params_bytes = json.dumps(sorted_params, sort_keys=True, default=str)
        query_hash = hashlib.blake2b(params_bytes, digest_size=16).hexdigest()
        return f"{self.query_type}:{query_hash}"

    async def get_query_result(
        self,
        query_params: dict[str, Any],
        default_func: Callable[[], T],
        ttl: int | None = None,
    ) -> T:
        """
        Get query result from cache or execute query.

        Args:
            query_params: Query parameters
            default_func: Function to execute query
            ttl: Time-to-live

        Returns:
            Query result
        """
        query_key = self._make_query_key(query_params)
        effective_ttl = ttl or self.default_ttl

        return cast(
            "T",
            await self.cache_service.get_or_set(
                query_key,
                default_func,
                effective_ttl,
            ),
        )

    async def invalidate_query(self, query_params: dict[str, Any]) -> bool:
        """Invalidate a specific query result."""
        query_key = self._make_query_key(query_params)
        return await self.cache_service.delete(query_key)
