"""Contract compliance suite for ``ConnectionPoolProtocol`` implementations.

Subclass :class:`ConnectionPoolCompliance` and implement
:meth:`create_pool` to verify any connection pool satisfies the
``ConnectionPoolProtocol`` contract::

    from quadkit.testing.compliance import ConnectionPoolCompliance

    class TestMyPool(ConnectionPoolCompliance):
        async def create_pool(self):
            return await MyProvider().get_primary_pool()

The suite owns shutdown: a pool that is never disposed keeps its engine's
threads alive past the event loop, so the final test in the class closes the
pool it built and the earlier ones close theirs as they go.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pytest

__all__ = ["ConnectionPoolCompliance"]


class ConnectionPoolCompliance:
    """Reusable test suite for any ``ConnectionPoolProtocol`` implementation."""

    @abstractmethod
    async def create_pool(self) -> Any:
        """Return a ready-to-use pool instance under test."""
        ...

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_initialize_is_idempotent(self) -> None:
        """initialize() can be called twice without raising."""
        pool = await self.create_pool()
        try:
            await pool.initialize()
            await pool.initialize()
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self) -> None:
        """shutdown() can be called twice — a restart must not crash on it."""
        pool = await self.create_pool()
        await pool.initialize()
        await pool.shutdown()
        await pool.shutdown()

    @pytest.mark.asyncio
    async def test_pool_is_usable_after_shutdown(self) -> None:
        """The pool re-opens connections after shutdown().

        ``shutdown()`` closes holders, not the engine: a process that restarts
        its pool (a worker recycling between jobs, a graceful reload) must be
        able to use it again. A pool that only works once would turn a routine
        restart into an outage.
        """
        pool = await self.create_pool()
        await pool.initialize()
        await pool.shutdown()
        await pool.initialize()
        async with pool.get_connection() as connection:
            assert connection is not None
        await pool.shutdown()

    # ------------------------------------------------------------------
    # Properties and statistics
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_capacity_properties_are_sane(self) -> None:
        """Capacity properties are non-negative.

        ``max_connections`` reports ``0`` for a pool with no ceiling — the
        framework's own ``AsyncEnginePool`` defines it that way, and the
        SQLite-backed default has exactly that shape. The suite therefore
        checks the type and sign, not that a bound exists: a bounded-pool
        assertion here would fail every unbounded deployment, which is a
        configuration, not a defect.
        """
        pool = await self.create_pool()
        try:
            assert isinstance(pool.max_connections, int)
            assert pool.max_connections >= 0
            assert pool.connection_timeout >= 0
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_pool_stats_returns_dict(self) -> None:
        """get_pool_stats() returns a mapping of counters."""
        pool = await self.create_pool()
        try:
            await pool.initialize()
            stats = await pool.get_pool_stats()
            assert isinstance(stats, dict)
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_query_stats_returns_dict(self) -> None:
        """get_query_stats() returns a mapping for the requested window."""
        pool = await self.create_pool()
        try:
            await pool.initialize()
            stats = await pool.get_query_stats(time_range_seconds=60)
            assert isinstance(stats, dict)
        finally:
            await pool.shutdown()

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_connection_yields_usable_connection(self) -> None:
        """get_connection() is an async context manager yielding a connection."""
        pool = await self.create_pool()
        try:
            await pool.initialize()
            async with pool.get_connection() as connection:
                assert connection is not None
                # The contract's pool hands out SQLAlchemy-style connections
                # (``execute``), which is what framework pool consumers drive.
                await connection.execute(__import__("sqlalchemy").text("SELECT 1"))
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_warm_and_validate(self) -> None:
        """warm() pre-creates connections and validate_connections() proves one works."""
        pool = await self.create_pool()
        try:
            await pool.initialize()
            await pool.warm(count=1)
            assert await pool.validate_connections() == 1
        finally:
            await pool.shutdown()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_health_check_is_healthy_when_reachable(self) -> None:
        """health_check() reports a result carrying a status and component."""
        from quadkit.contracts.core.health import HealthStatus

        pool = await self.create_pool()
        try:
            await pool.initialize()
            result = await pool.health_check(timeout=5.0)
            assert result.status is HealthStatus.HEALTHY
            assert result.component
        finally:
            await pool.shutdown()
