"""Task result store for persisting and querying results."""

from __future__ import annotations

from quadkit.tasks.results.cache_backend import CacheBackendResultStore
from quadkit.tasks.results.core import (
    InMemoryResultStore,
    ResultStore,
)

__all__ = [
    "CacheBackendResultStore",
    "InMemoryResultStore",
    "ResultStore",
]
