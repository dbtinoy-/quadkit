"""
RepositoryProtocol pattern implementations for Quadkit Cache.

This package provides repository patterns that offer domain-specific
caching abstractions on top of the core cache service.
"""

from __future__ import annotations

from quadkit.cache.repository.base import (
    CacheRepository,
    EntityRepository,
    QueryRepository,
)
from quadkit.cache.repository.collections import (
    CollectionRepository,
    ConfigurationRepository,
)
from quadkit.cache.repository.mixin import (
    CachedRepositoryMixin,
    InvalidatingCacheMixin,
)

__all__ = [
    "CacheRepository",
    "CachedRepositoryMixin",
    "CollectionRepository",
    "ConfigurationRepository",
    "EntityRepository",
    "InvalidatingCacheMixin",
    "QueryRepository",
]
