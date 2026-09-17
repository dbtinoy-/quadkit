"""Cache protocols."""

from __future__ import annotations

from quadkit.contracts.core.serialization import AsyncStringSerializerProtocol
from quadkit.contracts.infra.cache.exceptions import (
    CacheError,
    CacheKeyNotFoundError,
    CacheWriteError,
)
from quadkit.contracts.infra.cache.protocols import (
    CacheBackendProtocol,
    CacheHealthCheckerProtocol,
    CacheKeyBuilderProtocol,
    CacheProtectionStrategyProtocol,
    CacheProviderProtocol,
)

__all__ = [
    "AsyncStringSerializerProtocol",
    "CacheBackendProtocol",
    "CacheError",
    "CacheHealthCheckerProtocol",
    "CacheKeyBuilderProtocol",
    "CacheKeyNotFoundError",
    "CacheProtectionStrategyProtocol",
    "CacheProviderProtocol",
    "CacheWriteError",
]
