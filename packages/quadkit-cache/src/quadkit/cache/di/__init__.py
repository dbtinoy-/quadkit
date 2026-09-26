"""
Quadkit Cache integration module.

This module provides the integration layer for the cache system,
including the provider implementation and factory functions.
"""

from __future__ import annotations

from quadkit.cache.config import (
    CacheBackendConfig,
    CacheConfig,
    CacheOperationConfig,
    CacheServiceConfig,
    EnvironmentConfigLoader,
)
from quadkit.cache.di.provider import CacheProvider
from quadkit.cache.types import BackendType

__all__ = [
    "BackendType",
    "CacheBackendConfig",
    "CacheConfig",
    "CacheOperationConfig",
    "CacheProvider",
    "CacheServiceConfig",
    "EnvironmentConfigLoader",
]
