"""Resource-related protocols for cross-package boundaries.

This module defines interfaces for resource managers (e.g. connection pools)
that other packages may interact with without depending on concrete
implementations from quadkit or quadkit-admin.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PoolStatsProtocol(Protocol):
    """Snapshot of pool statistics."""

    pool_utilization: float
    last_health_check: Any
    total_connections: int
    active_connections: int
    idle_connections: int
    created_connections: int
    destroyed_connections: int


@runtime_checkable
class PoolProtocol(Protocol):
    """Protocol for an individual connection pool."""

    def get_stats(self) -> PoolStatsProtocol: ...

    async def close(self) -> None: ...


@runtime_checkable
class PoolManagerProtocol(Protocol):
    """Manager that tracks pools by name."""

    def get_stats(self) -> dict[str, PoolStatsProtocol]: ...

    async def get_pool(self, name: str) -> PoolProtocol: ...


__all__ = ["PoolManagerProtocol", "PoolProtocol", "PoolStatsProtocol"]
