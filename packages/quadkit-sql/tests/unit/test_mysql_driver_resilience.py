"""MySQL driver resilience, monitoring, and factory tests."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from quadkit.contracts.core import HealthStatus

try:
    import aiomysql

    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False
    aiomysql = None  # type: ignore[assignment]

from quadkit.sql.backends.mysql import (
    HAS_MYSQL,
    MySQLConnection,
    MySQLConnectionPool,
    create_mysql_pool,
)
from quadkit.sql.exceptions import DatabaseConnectionError, QueryError



@pytest.mark.skipif(not HAS_MYSQL, reason="aiomysql not available")
class TestMySQLDriver:
    @pytest.fixture
    def mock_monitor(self):
        """Create a mock monitor"""
        monitor = Mock()
        query_monitor = Mock()

        # Create a proper async context manager
        @asynccontextmanager
        async def monitor_query(*args, **kwargs):
            yield Mock()

        query_monitor.monitor_query = monitor_query
        monitor.get_query_monitor.return_value = query_monitor
        monitor.start_pool_monitoring = AsyncMock()
        monitor.stop_pool_monitoring = AsyncMock()
        return monitor


    async def test_mysql_pool_get_stats(self):
        """Test MySQL pool statistics"""
        pool = MySQLConnectionPool(
            "localhost",
            3306,
            "root",
            "pass",
            "test",
            min_size=5,
            max_size=25,
        )

        stats = await pool.get_pool_stats()

        assert stats["host"] == "localhost:3306"
        assert stats["database"] == "test"
        assert stats["pool_size"] == "5-25"
        assert stats["is_initialized"] is False
        assert stats["is_healthy"] is False
        assert stats["total_connections_created"] == 0
        assert stats["active_connection_count"] == 0
        assert stats["error_count"] == 0
        assert "circuit_breaker_state" in stats
        assert "last_health_check" in stats

    @pytest.mark.asyncio
    async def test_mysql_pool_with_monitoring(self, mock_monitor):
        """Test MySQL pool with monitoring enabled"""
        mock_pool = AsyncMock()
        mock_pool.close = Mock()  # close() is synchronous

        pool = MySQLConnectionPool(
            "localhost",
            3306,
            "root",
            "pass",
            "test",
            monitor=mock_monitor,
        )

        # Mock the _create_pool method
        async def mock_create_pool(pool_kwargs):
            pool._pool = mock_pool
            pool._total_connections_created += 1
            pool._is_healthy = True

        with patch.object(pool, "_create_pool", side_effect=mock_create_pool):
            await pool.initialize()

            assert pool.monitor == mock_monitor
            mock_monitor.start_pool_monitoring.assert_called_once()

            await pool.shutdown()
            mock_monitor.stop_pool_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_mysql_pool_retry_logic(self):
        """Test MySQL pool retry logic on initialization failures"""
        mock_pool = AsyncMock()

        pool = MySQLConnectionPool("localhost", 3306, "root", "pass", "test")

        # Mock the _create_pool method to fail twice then succeed
        call_count = 0

        async def mock_create_pool(pool_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            pool._pool = mock_pool
            pool._total_connections_created += 1
            pool._is_healthy = True
            return mock_pool

        with patch.object(pool, "_create_pool", side_effect=mock_create_pool):
            await pool.initialize()

            # Verify _create_pool was called 3 times (2 failures + 1 success)
            assert call_count == 3
            assert pool._pool == mock_pool
            assert pool._is_healthy is True

    @pytest.mark.asyncio
    async def test_mysql_pool_circuit_breaker(self):
        """Test MySQL pool circuit breaker integration"""
        mock_pool = AsyncMock()

        pool = MySQLConnectionPool("localhost", 3306, "root", "pass", "test")

        # Mock the _create_pool method
        async def mock_create_pool(pool_kwargs):
            pool._pool = mock_pool
            pool._total_connections_created += 1
            pool._is_healthy = True

        # Mock pool.acquire() to return an async context manager that raises exception
        class FailingAsyncContextManager:
            async def __aenter__(self):
                raise Exception("Connection failed")

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_pool.acquire = Mock(return_value=FailingAsyncContextManager())

        with patch.object(pool, "_create_pool", side_effect=mock_create_pool):
            await pool.initialize()

            # Mock circuit breaker as async context manager
            @asynccontextmanager
            async def mock_circuit_breaker():
                yield

            pool.circuit_breaker = Mock()
            pool.circuit_breaker.protect.side_effect = mock_circuit_breaker

            with pytest.raises(DatabaseConnectionError):
                async with pool.get_connection():
                    pass

            # Verify circuit breaker was used
            pool.circuit_breaker.protect.assert_called_once()

    @pytest.mark.asyncio
    async def test_mysql_connection_with_custom_monitor(self, mock_monitor):
        """Test MySQL connection with custom monitor"""
        mock_conn = AsyncMock()
        conn = MySQLConnection(mock_conn, mock_monitor)

        assert conn.monitor == mock_monitor
        assert conn.connection_id.startswith("mysql_")

    def test_mysql_import_error_when_unavailable(self):
        """Test MySQL import error when aiomysql not available"""
        with patch("quadkit.sql.backends.mysql._pool.HAS_MYSQL", False):
            with pytest.raises(
                ImportError,
                match="aiomysql is required for MySQL support",
            ):
                MySQLConnectionPool("localhost", 3306, "root", "pass", "test")

    @pytest.mark.asyncio
    async def test_mysql_factory_function(self):
        """Test create_mysql_pool factory function"""
        mock_monitor = Mock()
        mock_monitor.start_pool_monitoring = AsyncMock()

        pool = create_mysql_pool(
            host="mysql.example.com",
            port=3307,
            user="admin",
            password="secret",
            database="production",
            min_size=5,
            max_size=50,
            ssl={"ca": "/path/to/ca.pem"},
            monitor=mock_monitor,
        )

        assert isinstance(pool, MySQLConnectionPool)
        assert pool.host == "mysql.example.com"
        assert pool.port == 3307
        assert pool.user == "admin"
        assert pool.database == "production"
        assert pool.min_size == 5
        assert pool.max_size == 50
        assert pool.ssl == {"ca": "/path/to/ca.pem"}
        assert pool.monitor == mock_monitor

    @pytest.mark.asyncio
    async def test_mysql_connection_error_details(self):
        """Test MySQL connection error includes query details"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("Syntax error"))

        conn = MySQLConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.execute("INVALID SQL QUERY", ("param1", "param2"))

        error = exc_info.value
        assert "Query execution failed" in str(error)
        assert error.details["query"] == "INVALID SQL QUERY"
        assert "Syntax error" in error.details["error"]

    @pytest.mark.asyncio
    async def test_mysql_fetch_error_details(self):
        """Test MySQL fetch error includes query details"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock(side_effect=Exception("Table doesn't exist"))

        # Mock cursor() to return a context manager that accepts arguments
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context

        conn = MySQLConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.fetch_one("SELECT * FROM nonexistent_table", (1,))

        error = exc_info.value
        assert "Query fetch failed" in str(error)
        assert error.details["query"] == "SELECT * FROM nonexistent_table"
        assert "Table doesn't exist" in error.details["error"]

    @pytest.mark.asyncio
    async def test_mysql_execute_many_error_details(self):
        """Test MySQL execute_many error includes query details"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.executemany = AsyncMock(
            side_effect=Exception("Constraint violation"),
        )

        # Mock cursor() to return a context manager that accepts arguments
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context

        conn = MySQLConnection(mock_conn)

        params_list = [("value1",), ("value2",)]
        with pytest.raises(QueryError) as exc_info:
            await conn.execute_many("INSERT INTO test VALUES (?)", params_list)

        error = exc_info.value
        assert "Batch execution failed" in str(error)
        assert error.details["query"] == "INSERT INTO test VALUES (?)"
        assert "Constraint violation" in error.details["error"]
