"""Tests for connection pool warm() and validate_connections() implementation."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.sql.pool.connection import SimpleConnectionPool


@pytest.mark.asyncio
async def test_warm_creates_minimum_connections() -> None:
    """Test that warm() creates connections up to min_connections by default."""
    provider = MagicMock()
    pool = SimpleConnectionPool(provider=provider, min_connections=3, max_connections=5)

    # Mock the internal methods
    mock_conn_1 = MagicMock(name="conn1")
    mock_conn_2 = MagicMock(name="conn2")
    mock_conn_3 = MagicMock(name="conn3")
    pool._create_connection = AsyncMock(
        side_effect=[mock_conn_1, mock_conn_2, mock_conn_3]
    )

    # Initially empty pool
    assert pool._total_connections == 0
    assert len(pool._pool) == 0

    await pool.warm()

    # Should have created min_connections (3)
    assert pool._total_connections == 3
    assert len(pool._pool) == 3
    assert pool._create_connection.await_count == 3


@pytest.mark.asyncio
async def test_warm_creates_specified_count() -> None:
    """Test that warm(count=N) creates exactly N connections."""
    provider = MagicMock()
    pool = SimpleConnectionPool(
        provider=provider, min_connections=2, max_connections=10
    )

    mock_conns = [MagicMock(name=f"conn{i}") for i in range(5)]
    pool._create_connection = AsyncMock(side_effect=mock_conns)

    await pool.warm(count=5)

    assert pool._total_connections == 5
    assert len(pool._pool) == 5
    assert pool._create_connection.await_count == 5


@pytest.mark.asyncio
async def test_warm_respects_max_connections() -> None:
    """Test that warm() does not exceed max_connections."""
    provider = MagicMock()
    pool = SimpleConnectionPool(provider=provider, min_connections=3, max_connections=5)

    mock_conns = [MagicMock(name=f"conn{i}") for i in range(5)]
    pool._create_connection = AsyncMock(side_effect=mock_conns)

    # Request more than max_connections
    await pool.warm(count=10)

    # Should cap at max_connections (5)
    assert pool._total_connections == 5
    assert len(pool._pool) == 5
    assert pool._create_connection.await_count == 5


@pytest.mark.asyncio
async def test_warm_does_not_create_if_already_at_target() -> None:
    """Test that warm() does not create new connections if already at target."""
    provider = MagicMock()
    pool = SimpleConnectionPool(provider=provider, min_connections=2, max_connections=5)

    # Pre-populate pool
    now = time.monotonic()
    pool._pool.append((MagicMock(name="existing1"), now))
    pool._pool.append((MagicMock(name="existing2"), now))
    pool._total_connections = 2

    pool._create_connection = AsyncMock()

    await pool.warm()

    # Should not create any new connections
    assert pool._total_connections == 2
    assert len(pool._pool) == 2
    assert pool._create_connection.await_count == 0


@pytest.mark.asyncio
async def test_validate_connections_discards_invalid_idle_connections() -> None:
    """Test that validate_connections() discards invalid connections."""
    provider = MagicMock()
    pool = SimpleConnectionPool(provider=provider, min_connections=1, max_connections=3)

    bad = MagicMock(name="bad")
    good = MagicMock(name="good")
    now = time.monotonic()

    pool._pool.extend([(bad, now), (good, now)])
    pool._total_connections = 2
    pool._validate_connection = AsyncMock(side_effect=[False, True])
    pool._close_connection = AsyncMock()
    pool._create_connection = AsyncMock(return_value=MagicMock(name="replacement"))

    remaining = await pool.validate_connections()

    # Should have closed the bad connection
    pool._close_connection.assert_awaited_once_with(bad)
    # Should have at least 1 connection (the good one, plus potential refill)
    assert remaining >= 1
    # The bad connection should be removed
    assert pool._total_connections >= 1


@pytest.mark.asyncio
async def test_validate_connections_discards_expired_connections() -> None:
    """Test that validate_connections() discards expired connections."""
    provider = MagicMock()
    pool = SimpleConnectionPool(
        provider=provider,
        min_connections=1,
        max_connections=3,
        max_idle_time=10.0,
    )

    old_conn = MagicMock(name="old")
    fresh_conn = MagicMock(name="fresh")

    # Create an old connection (created 20 seconds ago)
    old_time = time.monotonic() - 20.0
    fresh_time = time.monotonic()

    pool._pool.extend([(old_conn, old_time), (fresh_conn, fresh_time)])
    pool._total_connections = 2
    pool._validate_connection = AsyncMock(return_value=True)
    pool._close_connection = AsyncMock()
    pool._create_connection = AsyncMock(return_value=MagicMock(name="replacement"))

    remaining = await pool.validate_connections()

    # Should have closed the old connection (expired)
    pool._close_connection.assert_awaited_once_with(old_conn)
    # Should have at least 1 connection remaining
    assert remaining >= 1


@pytest.mark.asyncio
async def test_validate_connections_refills_pool_after_eviction() -> None:
    """Test that validate_connections() refills the pool to min_connections."""
    provider = MagicMock()
    pool = SimpleConnectionPool(provider=provider, min_connections=2, max_connections=5)

    # Start with 3 bad connections
    bad1 = MagicMock(name="bad1")
    bad2 = MagicMock(name="bad2")
    bad3 = MagicMock(name="bad3")
    now = time.monotonic()

    pool._pool.extend([(bad1, now), (bad2, now), (bad3, now)])
    pool._total_connections = 3
    pool._validate_connection = AsyncMock(return_value=False)
    pool._close_connection = AsyncMock()

    # Mock warm() to refill
    replacement1 = MagicMock(name="replacement1")
    replacement2 = MagicMock(name="replacement2")
    pool._create_connection = AsyncMock(side_effect=[replacement1, replacement2])

    remaining = await pool.validate_connections()

    # All bad connections should be closed
    assert pool._close_connection.await_count == 3

    # Pool should be refilled to min_connections (2)
    assert remaining >= 2
    assert pool._create_connection.await_count == 2


@pytest.mark.asyncio
async def test_validate_connections_returns_count_of_valid_connections() -> None:
    """Test that validate_connections() returns the count of valid connections."""
    provider = MagicMock()
    pool = SimpleConnectionPool(provider=provider, min_connections=2, max_connections=5)

    good1 = MagicMock(name="good1")
    good2 = MagicMock(name="good2")
    good3 = MagicMock(name="good3")
    now = time.monotonic()

    pool._pool.extend([(good1, now), (good2, now), (good3, now)])
    pool._total_connections = 3
    pool._validate_connection = AsyncMock(return_value=True)
    pool._close_connection = AsyncMock()
    pool._create_connection = AsyncMock()

    remaining = await pool.validate_connections()

    # No connections should be closed
    pool._close_connection.assert_not_awaited()
    # Should return the count of valid connections (3)
    assert remaining == 3


@pytest.mark.asyncio
async def test_database_service_evict_dead_connections_delegates_to_pool() -> None:
    """Test that DatabaseService.evict_dead_connections() delegates to the pool."""
    from quadkit.sql.providers.database_service import DatabaseService

    service = DatabaseService("sqlite:///:memory:")
    service.connection_pool = MagicMock()
    service.connection_pool.validate_connections = AsyncMock(return_value=2)

    remaining = await service.evict_dead_connections()

    assert remaining == 2
    service.connection_pool.validate_connections.assert_awaited_once()


@pytest.mark.asyncio
async def test_database_service_evict_dead_connections_returns_zero_if_no_pool() -> (
    None
):
    """Test that evict_dead_connections() returns 0 if no pool exists."""
    from quadkit.sql.providers.database_service import DatabaseService

    service = DatabaseService("sqlite:///:memory:")
    service.connection_pool = None

    remaining = await service.evict_dead_connections()

    assert remaining == 0


@pytest.mark.asyncio
async def test_database_service_evict_dead_connections_returns_zero_if_no_validate() -> (
    None
):
    """Test that evict_dead_connections() returns 0 if pool lacks validate_connections."""
    from quadkit.sql.providers.database_service import DatabaseService

    service = DatabaseService("sqlite:///:memory:")
    # Create a pool mock without validate_connections method
    service.connection_pool = MagicMock(spec=[])

    remaining = await service.evict_dead_connections()

    assert remaining == 0
