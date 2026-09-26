"""Cache backend configuration models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from quadkit.cache import constants as const
from quadkit.cache.types import BackendType
from quadkit.domain import DomainModel
from quadkit.validation import Field, model_validator


@dataclass(init=False)
class MemoryBackendConfig(DomainModel):
    """Configuration for in-memory cache backend.

    Attributes:
        name: Backend name.
        default: Whether this is the default backend.
        enabled: Whether this backend is enabled.
        default_ttl: Default TTL in seconds.
        max_size: Maximum number of entries.
        cleanup_interval: Cleanup interval in seconds.
        key_prefix: Key prefix for namespace isolation.
    """

    name: str = Field(const.DEFAULT_MEMORY_NAME, description="Backend name")
    default: bool = Field(
        const.DEFAULT_MEMORY_DEFAULT, description="Is default backend"
    )
    enabled: bool = Field(const.DEFAULT_MEMORY_ENABLED, description="Is enabled")
    default_ttl: int | None = Field(None, description="Default TTL")
    max_size: int | None = Field(None, description="Max entries")
    cleanup_interval: int = Field(
        const.DEFAULT_MEMORY_CLEANUP_INTERVAL,
        description="Cleanup interval seconds",
    )
    key_prefix: str = Field("", description="Key prefix")

    @property
    def backend_type(self) -> BackendType:
        """Get the backend type."""
        return BackendType.MEMORY


@dataclass(init=False)
class RedisBackendConfig(DomainModel):
    """Configuration for Redis cache backend.

    Attributes:
        name: Backend name.
        default: Whether this is the default backend.
        enabled: Whether this backend is enabled.
        host: Redis host.
        port: Redis port.
        db: Redis database number.
        password: Redis password (optional).
        url: Full Redis URL (overrides host/port/db).
        default_ttl: Default TTL in seconds.
        key_prefix: Key prefix for namespace isolation.
        ssl: Whether to use SSL/TLS.
        connection_pool_size: Connection pool size.
        socket_timeout: Socket timeout in seconds.
        retry_on_timeout: Whether to retry on timeout.
    """

    name: str = Field(const.DEFAULT_REDIS_NAME, description="Backend name")
    default: bool = Field(const.DEFAULT_REDIS_DEFAULT, description="Is default backend")
    enabled: bool = Field(const.DEFAULT_REDIS_ENABLED, description="Is enabled")
    host: str = Field(const.DEFAULT_REDIS_HOST, description="Redis host")
    port: int = Field(const.DEFAULT_REDIS_PORT, description="Redis port")
    db: int = Field(const.DEFAULT_REDIS_DB, description="Redis database")
    password: str | None = Field(None, description="Redis password")
    url: str | None = Field(None, description="Redis URL")
    default_ttl: int | None = Field(None, description="Default TTL")
    key_prefix: str = Field("", description="Key prefix")
    ssl: bool = Field(const.DEFAULT_REDIS_SSL, description="Use SSL/TLS")
    connection_pool_size: int = Field(
        const.DEFAULT_REDIS_CONNECTION_POOL_SIZE,
        description="Connection pool size",
    )
    socket_timeout: float = Field(
        const.DEFAULT_REDIS_SOCKET_TIMEOUT,
        description="Socket timeout seconds",
    )
    retry_on_timeout: bool = Field(
        const.DEFAULT_REDIS_RETRY_ON_TIMEOUT,
        description="Retry on timeout",
    )

    @property
    def backend_type(self) -> BackendType:
        """Get the backend type."""
        return BackendType.REDIS

    @property
    def redis_url(self) -> str:
        """Get the full Redis URL."""
        if self.url:
            return self.url

        url = "rediss://" if self.ssl else "redis://"
        if self.password:
            url += f":{self.password}@"
        url += f"{self.host}:{self.port}/{self.db}"
        return url


@dataclass(init=False)
class MemcachedBackendConfig(DomainModel):
    """Configuration for Memcached cache backend.

    Attributes:
        name: Backend name.
        default: Whether this is the default backend.
        enabled: Whether this backend is enabled.
        host: Memcached host.
        port: Memcached port.
        servers: List of server addresses (host:port).
        default_ttl: Default TTL in seconds.
        key_prefix: Key prefix for namespace isolation.
        connect_timeout: Connection timeout in seconds.
        timeout: Operation timeout in seconds.
        max_pool_size: Maximum connection pool size.
    """

    name: str = Field(const.DEFAULT_MEMCACHED_NAME, description="Backend name")
    default: bool = Field(
        const.DEFAULT_MEMCACHED_DEFAULT, description="Is default backend"
    )
    enabled: bool = Field(const.DEFAULT_MEMCACHED_ENABLED, description="Is enabled")
    host: str = Field(const.DEFAULT_MEMCACHED_HOST, description="Memcached host")
    port: int = Field(const.DEFAULT_MEMCACHED_PORT, description="Memcached port")
    servers: list[str] | None = Field(None, description="Server list")
    default_ttl: int | None = Field(None, description="Default TTL")
    key_prefix: str = Field("", description="Key prefix")
    connect_timeout: float = Field(
        const.DEFAULT_REDIS_SOCKET_TIMEOUT,
        description="Connect timeout",
    )
    timeout: float = Field(
        const.DEFAULT_REDIS_SOCKET_TIMEOUT,
        description="Operation timeout",
    )
    max_pool_size: int = Field(
        const.DEFAULT_REDIS_CONNECTION_POOL_SIZE,
        description="Max pool size",
    )

    @property
    def backend_type(self) -> BackendType:
        """Get the backend type."""
        return BackendType.MEMCACHED

    @property
    def server_list(self) -> list[str]:
        """Get the server list."""
        if self.servers:
            return self.servers
        return [f"{self.host}:{self.port}"]


@dataclass(init=False)
class CacheBackendConfig(DomainModel):
    """Unified (flattened-union) configuration for any single cache backend.

    This class uses the **flattened-union pattern**: all backend-specific
    fields live in one dataclass and are partitioned by the ``type`` field.
    Fields that do not belong to the active backend type are silently
    ignored by the respective backend implementation.

    When to use
    -----------
    Prefer this class when loading backend configuration from environment
    variables or a flat config file (e.g. TOML/YAML with no nested sections),
    where per-backend types cannot be selected at parse time.

    For strongly-typed, up-front configuration prefer the dedicated classes:
    :class:`MemoryBackendConfig`, :class:`RedisBackendConfig`, or
    :class:`MemcachedBackendConfig`.

    Field partitioning
    ------------------
    +-------------------------+----------+----------+-----------+
    | Field                   | memory   | redis    | memcached |
    +=========================+==========+==========+===========+
    | name, type, default,    | ✓        | ✓        | ✓         |
    | enabled, default_ttl,   |          |          |           |
    | key_prefix,             |          |          |           |
    | enable_metrics,         |          |          |           |
    | health_check_interval   |          |          |           |
    +-------------------------+----------+----------+-----------+
    | max_size,               | ✓        |          |           |
    | cleanup_interval        |          |          |           |
    +-------------------------+----------+----------+-----------+
    | redis_host/port/db/     |          | ✓        |           |
    | password/url/ssl/       |          |          |           |
    | pool_size               |          |          |           |
    +-------------------------+----------+----------+-----------+
    | memcached_host/port/    |          |          | ✓         |
    | servers                 |          |          |           |
    +-------------------------+----------+----------+-----------+

    Attributes:
        name: Unique name for this backend.
        type: Backend type (memory, redis, memcached).
        default: Whether this is the default backend.
        enabled: Whether this backend is enabled.
        default_ttl: Default TTL in seconds.
        key_prefix: Key prefix for namespace isolation.
        enable_metrics: Enable metrics collection.
        health_check_interval: Health check interval in seconds.
    """

    # Common configuration
    name: str = Field(..., description="Unique backend name")
    type: BackendType = Field(..., description="Backend type")
    default: bool = Field(
        const.DEFAULT_MEMORY_DEFAULT, description="Is default backend"
    )
    enabled: bool = Field(const.DEFAULT_MEMORY_ENABLED, description="Is enabled")
    default_ttl: int | None = Field(None, description="Default TTL")
    key_prefix: str = Field("", description="Key prefix")
    enable_metrics: bool = Field(True, description="Enable metrics")
    health_check_interval: int = Field(
        const.DEFAULT_PROTECTION_LOCK_TTL,
        description="Health check interval",
    )

    # Memory-specific
    max_size: int | None = Field(None, description="Max entries (memory)")
    cleanup_interval: int = Field(
        const.DEFAULT_MEMORY_CLEANUP_INTERVAL,
        description="Cleanup interval (memory)",
    )

    # Redis-specific
    redis_host: str = Field(const.DEFAULT_REDIS_HOST, description="Redis host")
    redis_port: int = Field(const.DEFAULT_REDIS_PORT, description="Redis port")
    redis_db: int = Field(const.DEFAULT_REDIS_DB, description="Redis database")
    redis_password: str | None = Field(None, description="Redis password")
    redis_url: str | None = Field(None, description="Redis URL")
    redis_ssl: bool = Field(const.DEFAULT_REDIS_SSL, description="Redis SSL")
    redis_pool_size: int = Field(
        const.DEFAULT_REDIS_CONNECTION_POOL_SIZE,
        description="Redis pool size",
    )

    # Memcached-specific
    memcached_host: str = Field(
        const.DEFAULT_MEMCACHED_HOST, description="Memcached host"
    )
    memcached_port: int = Field(
        const.DEFAULT_MEMCACHED_PORT, description="Memcached port"
    )
    memcached_servers: list[str] | None = Field(None, description="Memcached servers")

    @model_validator(mode="after")
    def build_redis_url(self) -> CacheBackendConfig:
        """Build Redis URL from components if not provided."""
        if self.type == BackendType.REDIS and not self.redis_url:
            url = "rediss://" if self.redis_ssl else "redis://"
            if self.redis_password:
                url += f":{self.redis_password}@"
            url += f"{self.redis_host}:{self.redis_port}/{self.redis_db}"
            self.redis_url = url
        return self

    @model_validator(mode="after")
    def build_memcached_servers(self) -> CacheBackendConfig:
        """Build Memcached server list if not provided."""
        if self.type == BackendType.MEMCACHED and not self.memcached_servers:
            self.memcached_servers = [f"{self.memcached_host}:{self.memcached_port}"]
        return self


BACKEND_TYPE_MAP: dict[str, BackendType] = {
    "memory": BackendType.MEMORY,
    "redis": BackendType.REDIS,
    "memcached": BackendType.MEMCACHED,
}


def get_backend_type_from_string(type_str: str) -> BackendType:
    """Convert string to BackendType using registry lookup.

    Args:
        type_str: Backend type string (e.g., "memory", "redis").

    Returns:
        BackendType enum value, defaults to MEMORY if unknown.
    """
    return BACKEND_TYPE_MAP.get(type_str.lower(), BackendType.MEMORY)


def resolve_backend_type(config: CacheBackendConfig) -> BackendType:
    """Return the backend type from a backend configuration.

    The flattened :class:`CacheBackendConfig` stores the type in the
    ``type`` field while the strongly-typed classes
    (:class:`MemoryBackendConfig`, :class:`RedisBackendConfig`,
    :class:`MemcachedBackendConfig`) expose it via the ``backend_type``
    property. This helper normalizes both shapes.

    Args:
        config: Backend configuration, either shape.

    Returns:
        The resolved :class:`BackendType`.
    """
    backend_type = getattr(config, "backend_type", None)
    if backend_type is not None:
        return cast("BackendType", backend_type)
    return config.type


__all__ = [
    "BACKEND_TYPE_MAP",
    "CacheBackendConfig",
    "MemcachedBackendConfig",
    "MemoryBackendConfig",
    "RedisBackendConfig",
    "get_backend_type_from_string",
    "resolve_backend_type",
]
