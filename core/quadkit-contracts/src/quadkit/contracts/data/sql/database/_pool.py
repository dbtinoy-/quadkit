"""Connection pool protocol."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.core import HealthCheckResult


@runtime_checkable
class ConnectionPoolProtocol(Protocol):
    """Protocol for connection pools."""

    @property
    def max_connections(self) -> int: ...

    @property
    def connection_timeout(self) -> float: ...

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        ...

    async def shutdown(self) -> None:
        """Shutdown the connection pool."""
        ...

    def get_connection(self) -> AbstractAsyncContextManager[Any]:
        """Get a connection from the pool."""
        ...

    async def get_pool_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check pool health."""
        ...

    async def get_query_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Get query statistics."""
        ...

    async def warm(self, count: int | None = None) -> None:
        """Pre-create *count* connections to avoid cold-start latency.

        Args:
            count: Number of connections to open. Defaults to ``min_connections``
                   (or the pool minimum) if not specified.
        """
        ...

    async def validate_connections(self) -> int:
        """Validate all idle connections in the pool, evicting dead ones.

        Returns:
            Number of valid connections remaining after validation.
        """
        ...
