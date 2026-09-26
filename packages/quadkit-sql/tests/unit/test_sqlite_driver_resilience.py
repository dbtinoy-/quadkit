"""SQLite monitoring, retry, circuit-breaker, and factory tests."""

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
    @pytest.fixture
    def mock_monitor(self):
        """Create a mock monitor"""
        monitor = Mock()
        query_monitor = Mock()

        # Create a mock for monitor_query that can track calls
        monitor_query_mock = Mock()

        @asynccontextmanager
        async def monitor_query(*args, **kwargs):
            yield Mock()

        monitor_query_mock.side_effect = monitor_query
        query_monitor.monitor_query = monitor_query_mock
        monitor.get_query_monitor.return_value = query_monitor
        monitor.start_pool_monitoring = AsyncMock()
        monitor.stop_pool_monitoring = AsyncMock()
        monitor.get_stats = AsyncMock(return_value={})
        return monitor


    async def test_sqlite_pool_get_stats(self):
        """Test SQLite pool statistics"""
        pool = SQLiteConnectionPool("test.db", min_size=5, max_size=25)

        stats = await pool.get_pool_stats()

        assert stats["database"] == "test.db"
        assert stats["is_initialized"] is False
        assert stats["is_healthy"] is False
        assert stats["total_connections_created"] == 0
        assert stats["active_connection_count"] == 0
        assert stats["error_count"] == 0
        assert "circuit_breaker_state" in stats
        assert "last_health_check" in stats

    @pytest.mark.asyncio
    async def test_sqlite_pool_with_monitoring(self, mock_monitor):
        """Test SQLite pool with monitoring enabled"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

            pool = SQLiteConnectionPool("test.db", monitor=mock_monitor)
            await pool.initialize()

            assert pool.monitor == mock_monitor
            mock_monitor.start_pool_monitoring.assert_called_once()

            await pool.shutdown()
            mock_monitor.stop_pool_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlite_pool_retry_logic(self):
        """Test SQLite pool retry logic on initialization failures"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite"):
            # Mock retry_call to track calls
            with patch(
                "quadkit.sql.backends.sqlite._pool.retry_call", new_callable=AsyncMock
            ) as mock_retry:
                mock_conn = AsyncMock()
                mock_retry.return_value = mock_conn

                pool = SQLiteConnectionPool("test.db")
                await pool.initialize()

                # Verify retry_call was called with correct parameters
                mock_retry.assert_called_once()
                call_args = mock_retry.call_args
                assert call_args[0][0] == pool._create_connection  # Function to retry
                assert call_args.kwargs["config"] == pool.retry_config  # Retry config

    @pytest.mark.asyncio
    async def test_sqlite_pool_circuit_breaker(self):
        """Test SQLite pool circuit breaker integration"""
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

            async with pool.get_connection():
                pass

            # Verify circuit breaker was used
            mock_circuit_breaker.protect.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlite_connection_with_custom_monitor(self, mock_monitor):
        """Test SQLite connection with custom monitor"""
        mock_conn = AsyncMock()
        conn = SQLiteConnection(mock_conn, mock_monitor)

        assert conn.monitor == mock_monitor
        assert conn.connection_id.startswith("sqlite_")


    def test_sqlite_import_error_when_unavailable(self):
        """Test SQLite import error when aiosqlite not available"""
        with patch("quadkit.sql.backends.sqlite._pool.HAS_SQLITE", False):
            with pytest.raises(
                ImportError,
                match="aiosqlite is required for SQLite support",
            ):
                SQLiteConnectionPool("test.db")

    @pytest.mark.asyncio
    async def test_sqlite_factory_function(self):
        """Test create_sqlite_pool factory function"""
        mock_monitor = Mock()
        mock_monitor.start_pool_monitoring = AsyncMock()

        pool = create_sqlite_pool(database="production.db", monitor=mock_monitor)

        assert isinstance(pool, SQLiteConnectionPool)
        assert pool.database == "production.db"
        assert pool.monitor == mock_monitor

    @pytest.mark.asyncio
    async def test_sqlite_connection_error_details(self):
        """Test SQLite connection error includes query details"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=aiosqlite.Error("Network timeout"))

        conn = SQLiteConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.execute("SELECT * FROM large_table", (1, 2, 3))

        error = exc_info.value
        assert "Query execution failed" in str(error)
        assert error.details["query"] == "SELECT * FROM large_table"
        assert "Network timeout" in error.details["error"]

    @pytest.mark.asyncio
    async def test_sqlite_fetch_error_details(self):
        """Test SQLite fetch error includes query details"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(
            side_effect=aiosqlite.Error("Table doesn't exist")
        )

        conn = SQLiteConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.fetch_one("SELECT * FROM nonexistent_table", (1,))

        error = exc_info.value
        assert "Query fetch failed" in str(error)
        assert error.details["query"] == "SELECT * FROM nonexistent_table"
        assert "Table doesn't exist" in error.details["error"]

    @pytest.mark.asyncio
    async def test_sqlite_execute_many_error_details(self):
        """Test SQLite execute_many error includes query details"""
        mock_conn = AsyncMock()
        mock_conn.executemany = AsyncMock(side_effect=aiosqlite.Error("Duplicate key"))

        conn = SQLiteConnection(mock_conn)

        params_list = [("value1",), ("value2",)]
        with pytest.raises(QueryError) as exc_info:
            await conn.execute_many("INSERT INTO unique_table VALUES (?)", params_list)

        error = exc_info.value
        assert "Batch execution failed" in str(error)
        assert error.details["query"] == "INSERT INTO unique_table VALUES (?)"
        assert "Duplicate key" in error.details["error"]
