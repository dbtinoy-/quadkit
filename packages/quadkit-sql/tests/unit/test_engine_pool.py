"""``AsyncEnginePool`` presents a raw SQLAlchemy engine as a framework pool.

The adapter exists because applications create their engine directly rather
than through the framework provider; without it every framework-side pool
consumer (admin pool/query widgets, pool health, anything resolving
``ConnectionPoolProtocol``) reports "Unavailable" for a healthy database.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from quadkit.contracts.core.health import HealthStatus
from quadkit.sql.pool.engine import AsyncEnginePool


@pytest.fixture
async def engine(tmp_path):
    """A file-backed SQLite engine (WAL-capable, real pool object)."""
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pool.db'}")
    try:
        yield eng
    finally:
        await eng.dispose()


async def test_stats_report_occupancy_and_ceiling(engine) -> None:
    """Stats expose the keys the admin widgets render."""
    pool = AsyncEnginePool(engine, name="primary")

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
        during = await pool.get_pool_stats()
        # Checked out while the connection is held open.
        assert during["active_connections"] == 1

    after = await pool.get_pool_stats()
    assert after["active_connections"] == 0
    assert after["released_connections"] == 1
    assert after["acquired_connections"] == 1
    assert after["max_connections"] > 0
    assert after["utilization_rate"] == 0.0
    assert after["name"] == "primary"
    assert after["dialect"] == "sqlite"


async def test_acquire_release_counters_are_cumulative(engine) -> None:
    """SQLAlchemy tracks occupancy only; the adapter counts checkouts itself."""
    pool = AsyncEnginePool(engine)

    for _ in range(3):
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    stats = await pool.get_pool_stats()
    assert stats["acquired_connections"] == 3
    assert stats["released_connections"] == 3


async def test_stats_never_raise_for_pools_without_occupancy(engine, tmp_path) -> None:
    """A ``NullPool`` has no ``checkedout``-style API; stats stay coherent."""
    null_engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'null.db'}", poolclass=NullPool
    )
    try:
        pool = AsyncEnginePool(null_engine)
        stats = await pool.get_pool_stats()
        assert stats["active_connections"] == 0
        assert stats["max_connections"] == 0
        assert stats["utilization_rate"] == 0.0
        assert stats["pool_class"] == "NullPool"
    finally:
        await null_engine.dispose()


async def test_health_check_reports_healthy_for_live_engine(engine) -> None:
    """A live engine reports healthy against its own name."""
    pool = AsyncEnginePool(engine, name="primary")

    healthy = await pool.health_check()
    assert healthy.status is HealthStatus.HEALTHY
    assert healthy.component == "pool:primary"


async def test_health_check_reports_unhealthy_without_raising(tmp_path) -> None:
    """An unreachable database yields UNHEALTHY, never an exception.

    Probes run inside health endpoints: an exception here would turn a
    reporting route into a 500.
    """
    broken = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'missing-dir' / 'pool.db'}"
    )
    try:
        pool = AsyncEnginePool(broken, name="broken")
        unhealthy = await pool.health_check()
        assert unhealthy.status is HealthStatus.UNHEALTHY
        assert unhealthy.component == "pool:broken"
    finally:
        await broken.dispose()


async def test_query_stats_and_warm(engine) -> None:
    """``get_query_stats`` reports the tracked counters; ``warm`` opens and closes."""
    pool = AsyncEnginePool(engine)

    await pool.warm(2)
    stats = await pool.get_query_stats(time_range_seconds=60)
    assert stats["acquired_connections"] == 2
    assert stats["released_connections"] == 2
    assert stats["time_range_seconds"] == 60

    # Connections opened by warm() are closed, so nothing is stuck checked out.
    assert (await pool.get_pool_stats())["active_connections"] == 0


async def test_validate_connections_reports_without_raising(engine, tmp_path) -> None:
    """Validation answers 1 for a live pool and 0 for an unreachable one."""
    assert await AsyncEnginePool(engine).validate_connections() == 1

    broken = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'missing' / 'pool.db'}"
    )
    try:
        assert await AsyncEnginePool(broken).validate_connections() == 0
    finally:
        await broken.dispose()


async def test_get_connection_yields_usable_connection(engine) -> None:
    """The ``ConnectionPoolProtocol`` context manager hands out real connections."""
    pool = AsyncEnginePool(engine)

    async with pool.get_connection() as connection:
        result = await connection.execute(text("SELECT 42"))
        assert result.scalar_one() == 42


async def test_identity_and_properties(engine) -> None:
    """Adapter identity is reported for multi-backend setups."""
    pool = AsyncEnginePool(engine, name="analytics", primary=False)
    assert pool.name == "analytics"
    assert pool.is_primary is False
    assert pool.engine is engine
    assert pool.connection_timeout > 0
