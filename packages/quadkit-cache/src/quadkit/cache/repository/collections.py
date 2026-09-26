"""Collection and configuration cache repositories.

Extracted from ``base.py`` to keep that module under the 500-LOC limit.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, TypeVar, cast

from quadkit import serialization as json
from quadkit.cache.repository.base import CacheRepository
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.cache.service.core import CacheService

logger = get_logger(__name__)

T = TypeVar("T")


class CollectionRepository(CacheRepository[list[T], str]):
    """RepositoryProtocol for caching collections/lists.

    Provides caching for paginated results, category listings,
    and other collection-based data.
    """

    def __init__(
        self,
        cache_service: CacheService,
        collection_type: str,
        default_ttl: int | None = None,
    ):
        """Initialize collection repository.

        Args:
            cache_service: Cache service instance
            collection_type: Type of collection (e.g., "products", "users")
            default_ttl: Default TTL for collections
        """
        super().__init__(cache_service, f"collection:{collection_type}", default_ttl)
        self.collection_type = collection_type

    def _make_collection_key(
        self,
        filters: dict[str, Any] | None = None,
        pagination: dict[str, Any] | None = None,
        sort: dict[str, Any] | None = None,
    ) -> str:
        """Create cache key from collection parameters."""
        key_parts = [self.collection_type]

        if filters:
            sorted_filters = sorted(filters.items())
            key_parts.append(f"filters:{json.dumps(sorted_filters, sort_keys=True)!s}")

        if pagination:
            sorted_pagination = sorted(pagination.items())
            key_parts.append(f"page:{json.dumps(sorted_pagination, sort_keys=True)!s}")

        if sort:
            sorted_sort = sorted(sort.items())
            key_parts.append(f"sort:{json.dumps(sorted_sort, sort_keys=True)!s}")

        key_str = ":".join(key_parts)
        return hashlib.blake2b(key_str.encode(), digest_size=16).hexdigest()

    async def get_collection(
        self,
        filters: dict[str, Any] | None = None,
        pagination: dict[str, Any] | None = None,
        sort: dict[str, Any] | None = None,
        default_func: Callable[[], list[T]] | None = None,
        ttl: int | None = None,
    ) -> list[T] | None:
        """Get collection from cache.

        Args:
            filters: Collection filters
            pagination: Pagination parameters
            sort: Sort parameters
            default_func: Function to fetch collection if not cached
            ttl: Time-to-live

        Returns:
            Collection or None if not found and no default_func provided
        """
        collection_key = self._make_collection_key(filters, pagination, sort)

        if default_func:
            effective_ttl = ttl or self.default_ttl
            return cast(
                "list[T] | None",
                await self.cache_service.get_or_set(
                    collection_key,
                    default_func,
                    effective_ttl,
                ),
            )
        return cast("list[T] | None", await self.cache_service.get(collection_key))

    async def save_collection(
        self,
        collection: list[T],
        filters: dict[str, Any] | None = None,
        pagination: dict[str, Any] | None = None,
        sort: dict[str, Any] | None = None,
        ttl: int | None = None,
    ) -> bool:
        """Save collection to cache."""
        collection_key = self._make_collection_key(filters, pagination, sort)
        effective_ttl = ttl or self.default_ttl
        return await self.cache_service.set(collection_key, collection, effective_ttl)

    async def invalidate_collections(
        self,
        filters: dict[str, Any] | None = None,
    ) -> None:
        """Invalidate collections matching filters.

        Note: This is a simplified implementation. In practice,
        you might want more sophisticated invalidation strategies.
        """
        # For now, just log that collection invalidation needs implementation
        logger.warning(
            "Collection invalidation not fully implemented for type: %s",
            self.collection_type,
        )


class ConfigurationRepository(CacheRepository[dict[str, Any], str]):
    """RepositoryProtocol for caching configuration data.

    Provides centralized configuration management with
    hierarchical overrides and environment-specific configs.
    """

    def __init__(
        self,
        cache_service: CacheService,
        config_type: str = "app",
        default_ttl: int = 3600,  # 1 hour
    ):
        """Initialize configuration repository.

        Args:
            cache_service: Cache service instance
            config_type: Type of configuration (e.g., "app", "feature_flags")
            default_ttl: Default TTL for config (longer for configs)
        """
        super().__init__(cache_service, f"config:{config_type}", default_ttl)
        self.config_type = config_type

    async def get_config(
        self,
        config_key: str,
        environment: str | None = None,
        default_func: Callable[[], dict[str, Any]] | None = None,
        ttl: int | None = None,
    ) -> dict[str, Any] | None:
        """Get configuration by key.

        Args:
            config_key: Configuration key
            environment: Environment override
            default_func: Function to load config if not cached
            ttl: Time-to-live

        Returns:
            Configuration dictionary
        """
        cache_key_parts = [config_key]
        if environment:
            cache_key_parts.append(environment)

        cache_key = ":".join(cache_key_parts)

        if default_func:
            effective_ttl = ttl or self.default_ttl
            return cast(
                "dict[str, Any] | None",
                await self.cache_service.get_or_set(
                    cache_key,
                    default_func,
                    effective_ttl,
                ),
            )
        return cast("dict[str, Any] | None", await self.cache_service.get(cache_key))

    async def set_config(
        self,
        config_key: str,
        config_data: dict[str, Any],
        environment: str | None = None,
        ttl: int | None = None,
    ) -> bool:
        """Set configuration data."""
        cache_key_parts = [config_key]
        if environment:
            cache_key_parts.append(environment)

        cache_key = ":".join(cache_key_parts)
        effective_ttl = ttl or self.default_ttl
        return await self.cache_service.set(cache_key, config_data, effective_ttl)

    async def get_config_value(
        self,
        config_key: str,
        value_key: str,
        environment: str | None = None,
        default: Any = None,
    ) -> Any:
        """Get a specific configuration value.

        Args:
            config_key: Configuration key
            value_key: Value key within config
            environment: Environment override
            default: Default value if not found

        Returns:
            Configuration value
        """
        config = await self.get_config(config_key, environment)
        if config and isinstance(config, dict):
            return config.get(value_key, default)
        return default

    async def invalidate_config(
        self,
        config_key: str,
        environment: str | None = None,
    ) -> bool:
        """Invalidate configuration cache."""
        cache_key_parts = [config_key]
        if environment:
            cache_key_parts.append(environment)

        cache_key = ":".join(cache_key_parts)
        return await self.cache_service.delete(cache_key)
