"""Cache exceptions module.

This module defines the exception hierarchy for cache-related errors.
All exceptions inherit from CacheError which extends QuadkitError,
providing consistent error handling across the caching system.

Exception Hierarchy:
    QuadkitError (from quadkit.exceptions)
    └── CacheError
        ├── CacheBackendError
        │   └── CacheConnectionError
        ├── CacheTimeoutError
        ├── CacheKeyError
        ├── CacheConfigurationError
        ├── CacheStampedeError
        ├── CacheInvalidationError
        ├── LockAcquisitionError
        ├── CacheSerializationError (also inherits from SerializationError)
        └── CacheCapacityError

Example:
    ```python
    try:
        await cache.get("key")
    except CacheTimeoutError as e:
        logger.warning("Cache timeout", timeout=e.timeout_seconds)
    except CacheError as e:
        logger.error("Cache operation failed", error=str(e))
    ```
"""

from __future__ import annotations

from typing import Any

from quadkit.cache import constants as const
from quadkit.contracts.exceptions import QuadkitError, SerializationError


class CacheError(QuadkitError):
    """Base exception for cache errors."""

    _code: str = "QK_ERR_CACHE_004"


class CacheBackendError(CacheError):
    """Raised when the cache backend (Redis/Memcached) fails."""

    _code: str = "QK_ERR_CACHE_005"


class CacheConnectionError(CacheBackendError):
    """Raised when the cache connection fails."""

    _code: str = "QK_ERR_CACHE_006"


class CacheTimeoutError(CacheError):
    """Raised when a cache operation times out."""

    _code: str = "QK_ERR_CACHE_007"

    def __init__(
        self,
        message: str = const.ERROR_MSG_CACHE_TIMEOUT,
        key: str | None = None,
        backend: str | None = None,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ):
        details = kwargs.get("details", {})
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds
        super().__init__(message, key=key, backend=backend, details=details, **kwargs)
        self.timeout_seconds = timeout_seconds


class CacheKeyError(CacheError):
    """Raised when a cache key is invalid or for key-specific errors."""

    _code: str = "QK_ERR_CACHE_008"


class CacheConfigurationError(CacheError):
    """Raised when cache configuration is invalid."""

    _code: str = "QK_ERR_CACHE_009"

    def __init__(
        self,
        message: str = const.ERROR_MSG_CACHE_CONFIGURATION,
        setting: str | None = None,
        value: Any | None = None,
        **kwargs: Any,
    ):
        details = kwargs.get("details", {})
        if setting is not None:
            details["setting"] = setting
        if value is not None:
            details["value"] = str(value)
        super().__init__(message, details=details, **kwargs)
        self.setting = setting
        self.value = value


class CacheStampedeError(CacheError):
    """Raised when cache stampede protection fails."""

    _code: str = "QK_ERR_CACHE_010"

    def __init__(
        self,
        message: str = const.ERROR_MSG_CACHE_STAMPEDE,
        lock_holder: str | None = None,
        **kwargs: Any,
    ):
        details = kwargs.get("details", {})
        if lock_holder is not None:
            details["lock_holder"] = lock_holder
        super().__init__(message, details=details, **kwargs)
        self.lock_holder = lock_holder


class CacheInvalidationError(CacheError):
    """Raised when cache invalidation fails."""

    _code: str = "QK_ERR_CACHE_011"

    def __init__(
        self,
        message: str = const.ERROR_MSG_CACHE_INVALIDATION,
        keys: list[str] | None = None,
        tag: str | None = None,
        pattern: str | None = None,
        **kwargs: Any,
    ):
        details = kwargs.get("details", {})
        if keys is not None:
            details["keys"] = keys[:10]
            details["keys_count"] = len(keys)
        if tag is not None:
            details["tag"] = tag
        if pattern is not None:
            details["pattern"] = pattern
        super().__init__(message, details=details, **kwargs)
        self.keys = keys
        self.tag = tag
        self.pattern = pattern


class LockAcquisitionError(CacheError):
    """Raised when a distributed lock cannot be acquired."""

    _code: str = "QK_ERR_CACHE_012"


class CacheSerializationError(SerializationError, CacheError):
    """Raised when serialization/deserialization fails."""

    _code: str = "QK_ERR_CACHE_013"


class CacheCapacityError(CacheError):
    """Raised when the cache is at capacity."""

    _code: str = "QK_ERR_CACHE_014"


__all__ = [
    "CacheBackendError",
    "CacheCapacityError",
    "CacheConfigurationError",
    "CacheConnectionError",
    "CacheError",
    "CacheInvalidationError",
    "CacheKeyError",
    "CacheSerializationError",
    "CacheStampedeError",
    "CacheTimeoutError",
    "LockAcquisitionError",
]
