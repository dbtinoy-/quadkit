"""Cache operation configuration."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.cache import constants as const
from quadkit.domain import DomainModel
from quadkit.validation import Field


@dataclass(init=False)
class CacheOperationConfig(DomainModel):
    """Internal configuration for cache operations. Shared across backends.

    Attributes:
        default_ttl: Default time-to-live in seconds.
        max_memory: Maximum memory usage in bytes.
        key_prefix: Prefix for all cache keys.
        enable_metrics: Whether to enable metrics collection.
        serializer_type: Type of serializer to use (json, msgpack).
    """

    default_ttl: int | None = Field(None, description="Default TTL in seconds")
    max_memory: int | None = Field(None, description="Maximum memory in bytes")
    key_prefix: str = Field("", description="Prefix for all cache keys")
    enable_metrics: bool = Field(True, description="Enable metrics collection")
    serializer_type: str = Field(
        const.DEFAULT_SERVICE_SERIALIZER,
        description="AsyncStringSerializerProtocol type",
    )

    def make_key(self, key: str) -> str:
        """Create a prefixed cache key.

        Args:
            key: The raw cache key.

        Returns:
            Key with the configured prefix applied, or the original key if no
            prefix is set.
        """
        if self.key_prefix:
            return f"{self.key_prefix}:{key}"
        return key

    def strip_prefix(self, prefixed_key: str) -> str:
        """Remove prefix from a cache key.

        Args:
            prefixed_key: A key that may carry the configured prefix.

        Returns:
            The key with the prefix removed, or the original key unchanged.
        """
        if self.key_prefix and prefixed_key.startswith(f"{self.key_prefix}:"):
            return prefixed_key[len(self.key_prefix) + 1 :]
        return prefixed_key


def default_cache_config() -> CacheOperationConfig:
    """Factory for default cache operation configuration.

    Returns:
        Default :class:`CacheOperationConfig` instance.
    """
    return CacheOperationConfig(
        default_ttl=None,
        max_memory=None,
        key_prefix="",
        enable_metrics=True,
        serializer_type="json",
    )


__all__ = [
    "CacheOperationConfig",
    "default_cache_config",
]
