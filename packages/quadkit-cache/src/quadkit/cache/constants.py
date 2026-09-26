"""Cache constants for quadkit-cache.

This module provides centralized constants for configuration defaults,
magic strings, and other values used throughout the caching system.
Following the framework's pattern of defining constants prominently.
"""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__ = importlib.metadata.version("quadkit-cache")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

# =============================================================================
# Configuration Environment Variable Prefixes
# =============================================================================

ENV_PREFIX: str = "QK_CACHE__"
"""Pydantic environment variable prefix for CacheConfig model."""

ENV_NESTED_DELIMITER: str = "__"
"""Delimiter for nested configuration in environment variables."""

ENV_VAR_QK_ENV: str = "QK_ENV"
"""Environment variable name for Quadkit environment detection."""


# =============================================================================
# Default Configuration Values
# =============================================================================

# CacheConfig defaults
DEFAULT_CACHE_NAME: str = "cache"
DEFAULT_CACHE_VERSION: str = "1.0.0"
DEFAULT_CACHE_ENABLED: bool = True
DEFAULT_CACHE_ENVIRONMENT: str = "development"
DEFAULT_CACHE_DEBUG: bool = False

# Service config defaults
DEFAULT_SERVICE_PROTECTION_ENABLED: bool = True
DEFAULT_SERVICE_METRICS_ENABLED: bool = True
DEFAULT_SERVICE_HEALTH_CHECKS_ENABLED: bool = True
DEFAULT_SERVICE_CIRCUIT_BREAKER_ENABLED: bool = False
DEFAULT_SERVICE_CIRCUIT_BREAKER_THRESHOLD: int = 5
DEFAULT_SERVICE_SERIALIZER: str = "json"

# Protection defaults (stampede protection)
DEFAULT_PROTECTION_LOCK_TTL: int = 30
DEFAULT_PROTECTION_MAX_WAIT: float = 10.0
DEFAULT_PROTECTION_RETRY_INTERVAL: float = 0.1


# =============================================================================
# Backend Default Values
# =============================================================================

# Memory backend defaults
DEFAULT_MEMORY_NAME: str = "memory"
DEFAULT_MEMORY_ENABLED: bool = True
DEFAULT_MEMORY_DEFAULT: bool = False
DEFAULT_MEMORY_CLEANUP_INTERVAL: int = 60

# Redis backend defaults
DEFAULT_REDIS_NAME: str = "redis"
DEFAULT_REDIS_HOST: str = "localhost"
DEFAULT_REDIS_PORT: int = 6379
DEFAULT_REDIS_DB: int = 0
DEFAULT_REDIS_ENABLED: bool = True
DEFAULT_REDIS_DEFAULT: bool = False
DEFAULT_REDIS_SSL: bool = False
DEFAULT_REDIS_CONNECTION_POOL_SIZE: int = 10
DEFAULT_REDIS_SOCKET_TIMEOUT: float = 5.0
DEFAULT_REDIS_RETRY_ON_TIMEOUT: bool = True

# Memcached backend defaults
DEFAULT_MEMCACHED_NAME: str = "memcached"
DEFAULT_MEMCACHED_HOST: str = "localhost"
DEFAULT_MEMCACHED_PORT: int = 11211
DEFAULT_MEMCACHED_ENABLED: bool = True
DEFAULT_MEMCACHED_DEFAULT: bool = False


# =============================================================================
# Lock Constants
# =============================================================================

LOCK_KEY_PREFIX: str = "lock:"
"""Prefix for distributed lock keys in Redis."""

DEFAULT_LOCK_TTL: int = 30
"""Default TTL for distributed locks in seconds."""

DEFAULT_LOCK_RENEWAL_INTERVAL_DIVISOR: int = 2
"""Divisor to calculate renewal interval from TTL (TTL // 2)."""


# =============================================================================
# Compression Constants
# =============================================================================

COMPRESSION_MARKER_UNCOMPRESSED: bytes = b"\x00"
"""Marker byte for uncompressed data in CompressingSerializer."""

COMPRESSION_MARKER_COMPRESSED: bytes = b"\x01"
"""Marker byte for compressed data in CompressingSerializer."""

DEFAULT_COMPRESSION_THRESHOLD: int = 1024  # 1KB
"""Default size threshold for compression (bytes)."""

DEFAULT_COMPRESSION_LEVEL: int = 6
"""Default zlib compression level (1-9, higher = more compression)."""


# =============================================================================
# Security Constants
# =============================================================================

INSECURE_PASSWORDS: tuple[str, ...] = (
    "change-me",
    "password",
    "123456",
    "secret",
    "admin",
    "default",
    "password123",
    "qwerty",
)
"""Known insecure passwords that should not be used in production."""


# =============================================================================
# Backend Type String Constants
# =============================================================================

BACKEND_TYPE_MEMORY: str = "memory"
BACKEND_TYPE_REDIS: str = "redis"
BACKEND_TYPE_MEMCACHED: str = "memcached"


# =============================================================================
# Cache Status String Constants
# =============================================================================

CACHE_STATUS_HIT: str = "hit"
CACHE_STATUS_MISS: str = "miss"
CACHE_STATUS_SET: str = "set"
CACHE_STATUS_DELETE: str = "delete"
CACHE_STATUS_ERROR: str = "error"
CACHE_STATUS_EXPIRED: str = "expired"
CACHE_STATUS_STALE: str = "stale"


# =============================================================================
# Error Messages
# =============================================================================

ERROR_MSG_CACHE_TIMEOUT: str = "Cache operation timed out"
ERROR_MSG_CACHE_CONFIGURATION: str = "Cache configuration error"
ERROR_MSG_CACHE_STAMPEDE: str = "Cache stampede protection error"
ERROR_MSG_CACHE_INVALIDATION: str = "Cache invalidation failed"
ERROR_MSG_REDIS_INSTALL: str = (
    "Redis backend requires redis package. "
    "Install with: pip install quadkit-cache[redis]"
)
ERROR_MSG_MEMCACHED_INSTALL: str = (
    "Memcached backend requires pylibmc or python-memcached. "
    "Install with: pip install quadkit-cache[memcached]"
)
ERROR_MSG_PYYAML_INSTALL: str = "PyYAML is required for YAML configuration loading"
ERROR_MSG_INSECURE_PASSWORD: str = (
    "CRITICAL SECURITY ERROR: Insecure {backend} password detected in PRODUCTION "  # noqa: S105  # error message text, not a credential
    "for backend '{name}'.\n"
    "You MUST set a secure password via {env_var}."
)
ERROR_MSG_INSECURE_URL: str = (
    "CRITICAL SECURITY ERROR: Insecure {backend} URL detected in PRODUCTION "
    "for backend '{name}'.\n"
    "You MUST set a secure {backend} URL via {env_var}."
)


# =============================================================================
# File Loading Constants
# =============================================================================

DEFAULT_ENCODING: str = "utf-8"
"""Default file encoding for configuration files."""


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "BACKEND_TYPE_MEMCACHED",
    "BACKEND_TYPE_MEMORY",
    "BACKEND_TYPE_REDIS",
    "CACHE_STATUS_DELETE",
    "CACHE_STATUS_ERROR",
    "CACHE_STATUS_EXPIRED",
    "CACHE_STATUS_HIT",
    "CACHE_STATUS_MISS",
    "CACHE_STATUS_SET",
    "CACHE_STATUS_STALE",
    "COMPRESSION_MARKER_COMPRESSED",
    "COMPRESSION_MARKER_UNCOMPRESSED",
    "DEFAULT_CACHE_DEBUG",
    "DEFAULT_CACHE_ENABLED",
    "DEFAULT_CACHE_ENVIRONMENT",
    "DEFAULT_CACHE_NAME",
    "DEFAULT_CACHE_VERSION",
    "DEFAULT_COMPRESSION_LEVEL",
    "DEFAULT_COMPRESSION_THRESHOLD",
    "DEFAULT_ENCODING",
    "DEFAULT_LOCK_RENEWAL_INTERVAL_DIVISOR",
    "DEFAULT_LOCK_TTL",
    "DEFAULT_MEMCACHED_DEFAULT",
    "DEFAULT_MEMCACHED_ENABLED",
    "DEFAULT_MEMCACHED_HOST",
    "DEFAULT_MEMCACHED_NAME",
    "DEFAULT_MEMCACHED_PORT",
    "DEFAULT_MEMORY_CLEANUP_INTERVAL",
    "DEFAULT_MEMORY_DEFAULT",
    "DEFAULT_MEMORY_ENABLED",
    "DEFAULT_MEMORY_NAME",
    "DEFAULT_PROTECTION_LOCK_TTL",
    "DEFAULT_PROTECTION_MAX_WAIT",
    "DEFAULT_PROTECTION_RETRY_INTERVAL",
    "DEFAULT_REDIS_CONNECTION_POOL_SIZE",
    "DEFAULT_REDIS_DB",
    "DEFAULT_REDIS_DEFAULT",
    "DEFAULT_REDIS_ENABLED",
    "DEFAULT_REDIS_HOST",
    "DEFAULT_REDIS_NAME",
    "DEFAULT_REDIS_PORT",
    "DEFAULT_REDIS_RETRY_ON_TIMEOUT",
    "DEFAULT_REDIS_SOCKET_TIMEOUT",
    "DEFAULT_REDIS_SSL",
    "DEFAULT_SERVICE_CIRCUIT_BREAKER_ENABLED",
    "DEFAULT_SERVICE_CIRCUIT_BREAKER_THRESHOLD",
    "DEFAULT_SERVICE_HEALTH_CHECKS_ENABLED",
    "DEFAULT_SERVICE_METRICS_ENABLED",
    "DEFAULT_SERVICE_PROTECTION_ENABLED",
    "DEFAULT_SERVICE_SERIALIZER",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "ENV_VAR_QK_ENV",
    "ERROR_MSG_CACHE_CONFIGURATION",
    "ERROR_MSG_CACHE_INVALIDATION",
    "ERROR_MSG_CACHE_STAMPEDE",
    "ERROR_MSG_CACHE_TIMEOUT",
    "ERROR_MSG_INSECURE_PASSWORD",
    "ERROR_MSG_INSECURE_URL",
    "ERROR_MSG_MEMCACHED_INSTALL",
    "ERROR_MSG_PYYAML_INSTALL",
    "ERROR_MSG_REDIS_INSTALL",
    "INSECURE_PASSWORDS",
    "LOCK_KEY_PREFIX",
]
