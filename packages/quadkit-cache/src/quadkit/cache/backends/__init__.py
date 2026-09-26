"""
Cache backends for Quadkit Framework.

This package contains backend implementations that wrap infrastructure
drivers, ensuring DRY compliance and consistency.

Note: Database-backed state, secret, and lock stores (previously
``DatabaseBridgeStateStore``, ``DatabaseBridgeSecretStore``, and
``DatabaseBridgeLockStore``) have been moved to ``quadkit-sql`` as
``DatabaseStateStore``, ``DatabaseSecretStore``, and ``DatabaseLockStore``.
Import them from ``quadkit.sql.stores`` instead.
"""

from __future__ import annotations

from quadkit.cache.backends.hash import _compute_hash
from quadkit.cache.backends.memcached.backend import MemcachedCacheBackend
from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.backends.redis.backend import RedisCacheBackend

__all__ = [
    "MemcachedCacheBackend",
    "MemoryCacheBackend",
    "RedisCacheBackend",
    "_compute_hash",
]
