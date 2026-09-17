"""Domain errors for cache subsystem."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import DomainError


class CacheError(DomainError):
    """Base exception for all cache-domain errors.

    This is an expected, recoverable error that cache clients should
    handle gracefully (e.g., miss and regenerate, fallback to origin).
    """

    _code = "QK_ERR_CACHE_001"

    def __init__(self, message: str = "Cache error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class CacheKeyNotFoundError(CacheError):
    """Raised when cache key is not found."""

    _code = "QK_ERR_CACHE_002"

    def __init__(self, key: str, **kwargs: Any) -> None:
        self.key = key
        message = f"Cache key not found: {key}"
        super().__init__(message, **kwargs)


class CacheWriteError(CacheError):
    """Raised when cache write fails."""

    _code = "QK_ERR_CACHE_003"

    def __init__(self, key: str, reason: str, **kwargs: Any) -> None:
        self.key = key
        self.reason = reason
        message = f"Cache write failed for key {key}: {reason}"
        super().__init__(message, **kwargs)


__all__ = ["CacheError", "CacheKeyNotFoundError", "CacheWriteError"]
