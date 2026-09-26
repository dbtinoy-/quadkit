"""SQLite pool health-check tests."""

from __future__ import annotations

"""Tests for SQLite database driver"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    import aiosqlite

    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False
    aiosqlite = None  # type: ignore[assignment]

from quadkit.contracts import HealthStatus
from quadkit.sql.backends.sqlite import (
    HAS_SQLITE,
    SQLiteConnection,
    SQLiteConnectionPool,
    create_sqlite_pool,
)
from quadkit.sql.exceptions import DatabaseConnectionError, QueryError



@pytest.mark.skipif(not HAS_SQLITE, reason="aiosqlite not available")
class TestSQLiteDriver:
    """Test SQLite driver functionality"""

    @pytest.mark.asyncio
    async def test_sqlite_pool_health_check_healthy(self):
        """Test SQLite pool health check when healthy"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute = AsyncMock(return_value=mock_cursor)
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

            pool = SQLiteConnectionPool("test.db")
            await pool.initialize()

            # Mock circuit breaker as async context manager
            mock_circuit_breaker = Mock()

            @asynccontextmanager
            async def mock_protect():
                yield

            mock_circuit_breaker.protect = Mock(side_effect=mock_protect)
            pool.circuit_breaker = mock_circuit_breaker

            health = await pool.health_check()

            assert health.status == HealthStatus.HEALTHY
            assert health.details.get("database") == "test.db"
            assert health.details.get("connections_created") == 1
            assert "active_connections" in health.details
            assert "error_count" in health.details

    @pytest.mark.asyncio
    async def test_sqlite_pool_health_check_unhealthy_no_connection(self):
        """Test SQLite pool health check when connection not initialized"""
        pool = SQLiteConnectionPool("test.db")

        health = await pool.health_check()

        assert health.status == HealthStatus.UNHEALTHY
        assert health.message == "Connection not initialized"

    @pytest.mark.asyncio
    async def test_sqlite_pool_health_check_unhealthy_query_failed(self):
        """Test SQLite pool health check when query fails"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

            pool = SQLiteConnectionPool("test.db")
            await pool.initialize()

            # Mock circuit breaker
            mock_circuit_breaker = Mock()

            @asynccontextmanager
            async def mock_protect():
                yield

            mock_circuit_breaker.protect = Mock(side_effect=mock_protect)
            pool.circuit_breaker = mock_circuit_breaker

            # Make execute fail
            pool._conn.execute = AsyncMock(side_effect=OSError("Connection failed"))

            health = await pool.health_check()

            assert health.status == HealthStatus.UNHEALTHY
            assert health.message is not None
            assert health.details.get("error_count") == 1  # Health check error

    @pytest.mark.asyncio
    async def test_sqlite_pool_health_check_caching(self):
        """Test SQLite pool health check caching"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute = AsyncMock(return_value=mock_cursor)
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

            pool = SQLiteConnectionPool("test.db")
            await pool.initialize()

            # Mock circuit breaker as async context manager
            mock_circuit_breaker = Mock()

            @asynccontextmanager
            async def mock_protect():
                yield

            mock_circuit_breaker.protect = Mock(side_effect=mock_protect)
            pool.circuit_breaker = mock_circuit_breaker

            # First health check
            health1 = await pool.health_check()
            assert health1.status == HealthStatus.HEALTHY

            # Second health check (should be cached if within 30 seconds)
            await asyncio.sleep(0.01)  # Small delay
            health2 = await pool.health_check()

            # Should be the same result (cached)
            assert health2.status == HealthStatus.HEALTHY
            assert health2.details.get("cached") is True

