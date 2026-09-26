"""MySQL driver connection execution tests."""

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


    async def test_mysql_connection_creation(self):
        """Test MySQL connection creation from pool"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()

        pool = MySQLConnectionPool("localhost", 3306, "root", "pass", "test")

        # Mock the _create_pool method
        async def mock_create_pool(pool_kwargs):
            pool._pool = mock_pool
            pool._total_connections_created += 1
            pool._is_healthy = True

        # Create an async context manager for pool.acquire()
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_conn

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_pool.acquire = Mock(return_value=MockAcquireContext())

        with patch.object(pool, "_create_pool", side_effect=mock_create_pool):
            await pool.initialize()

            # Mock circuit breaker as async context manager
            @asynccontextmanager
            async def mock_circuit_breaker():
                yield

            pool.circuit_breaker = Mock()
            pool.circuit_breaker.protect.side_effect = mock_circuit_breaker

            async with pool.get_connection() as conn:
                assert isinstance(conn, MySQLConnection)
                assert conn._conn == mock_conn
                assert conn.connection_id.startswith("mysql_")

            # Verify connection was acquired and released
            # Note: We can't easily verify the call counts with the context manager mock

    @pytest.mark.asyncio
    async def test_mysql_connection_execute_without_monitoring(self):
        """Test MySQL connection execute method without monitoring"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=None)
        mock_conn.affected_rows = 5

        conn = MySQLConnection(mock_conn)

        # Execute without parameters
        result = await conn.execute("CREATE TABLE test (id INT)")
        assert result == 5
        mock_conn.execute.assert_called_with("CREATE TABLE test (id INT)")

        # Execute with parameters
        mock_conn.execute.reset_mock()
        result = await conn.execute("INSERT INTO test VALUES (?)", (1,))
        assert result == 5
        mock_conn.execute.assert_called_with("INSERT INTO test VALUES (?)", (1,))

    @pytest.mark.asyncio
    async def test_mysql_connection_execute_with_monitoring(self, mock_monitor):
        """Test MySQL connection execute method with monitoring"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=None)
        mock_conn.affected_rows = 3

        conn = MySQLConnection(mock_conn, mock_monitor)

        result = await conn.execute("UPDATE test SET name = ?", ("new_name",))
        assert result == 3

        # Verify monitoring was called
        mock_monitor.get_query_monitor.assert_called_once()
        # The monitor_query context manager should have been used

    @pytest.mark.asyncio
    async def test_mysql_connection_execute_error(self):
        """Test MySQL connection execute error handling"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=aiomysql.Error("Query failed"))

        conn = MySQLConnection(mock_conn)

        with pytest.raises(QueryError, match="Query execution failed"):
            await conn.execute("INVALID QUERY")

    @pytest.mark.asyncio
    async def test_mysql_connection_execute_many(self):
        """Test MySQL connection execute_many method"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()

        # Mock cursor() to return a context manager that accepts arguments
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context

        conn = MySQLConnection(mock_conn)

        params_list = [("value1",), ("value2",), ("value3",)]
        await conn.execute_many("INSERT INTO test VALUES (?)", params_list)

        # Verify cursor was used correctly
        mock_cursor.executemany.assert_called_once_with(
            "INSERT INTO test VALUES (?)",
            params_list,
        )
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mysql_connection_execute_many_error(self):
        """Test MySQL connection execute_many error handling"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()

        # Mock cursor() to return a context manager
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context
        mock_cursor.executemany = AsyncMock(
            side_effect=aiomysql.Error("Batch insert failed"),
        )

        conn = MySQLConnection(mock_conn)

        with pytest.raises(QueryError, match="Batch execution failed"):
            await conn.execute_many("INSERT INTO test VALUES (?)", [("value1",)])

    @pytest.mark.asyncio
    async def test_mysql_connection_fetch_one_without_monitoring(self):
        """Test MySQL connection fetch_one method without monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"id": 1, "name": "test"})

        # Mock cursor() to return a context manager that accepts arguments
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context

        conn = MySQLConnection(mock_conn)

        # Fetch without parameters
        result = await conn.fetch_one("SELECT * FROM test LIMIT 1")
        assert result == {"id": 1, "name": "test"}
        mock_cursor.execute.assert_called_with("SELECT * FROM test LIMIT 1")

        # Fetch with parameters
        mock_cursor.fetchone.reset_mock()
        mock_cursor.execute.reset_mock()
        result = await conn.fetch_one("SELECT * FROM test WHERE id = ?", (1,))
        assert result == {"id": 1, "name": "test"}
        mock_cursor.execute.assert_called_with("SELECT * FROM test WHERE id = ?", (1,))

    @pytest.mark.asyncio
    async def test_mysql_connection_fetch_one_with_monitoring(self, mock_monitor):
        """Test MySQL connection fetch_one method with monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"id": 1, "name": "test"})

        # Mock cursor() to return a context manager that accepts arguments
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context

        conn = MySQLConnection(mock_conn, mock_monitor)

        result = await conn.fetch_one("SELECT * FROM test WHERE id = ?", (1,))
        assert result == {"id": 1, "name": "test"}

        # Verify monitoring was called
        mock_monitor.get_query_monitor.assert_called_once()

    @pytest.mark.asyncio
    async def test_mysql_connection_fetch_one_none_result(self):
        """Test MySQL connection fetch_one with no results"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        # Mock cursor() to return a context manager that accepts arguments
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context

        conn = MySQLConnection(mock_conn)

        result = await conn.fetch_one("SELECT * FROM test WHERE id = ?", (999,))
        assert result is None

    @pytest.mark.asyncio
    async def test_mysql_connection_fetch_one_error(self):
        """Test MySQL connection fetch_one error handling"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()

        # Mock cursor() to return a context manager
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context
        mock_cursor.execute = AsyncMock(side_effect=aiomysql.Error("Fetch failed"))

        conn = MySQLConnection(mock_conn)

        with pytest.raises(QueryError, match="Query fetch failed"):
            await conn.fetch_one("SELECT * FROM nonexistent")

    @pytest.mark.asyncio
    async def test_mysql_connection_fetch_all_without_monitoring(self):
        """Test MySQL connection fetch_all method without monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(
            return_value=[{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}],
        )

        # Mock cursor() to return a context manager that accepts arguments
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context

        conn = MySQLConnection(mock_conn)

        # Fetch without parameters
        result = await conn.fetch_all("SELECT * FROM test")
        assert result == [{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}]

        # Fetch with parameters
        mock_cursor.fetchall.reset_mock()
        mock_cursor.execute.reset_mock()
        result = await conn.fetch_all(
            "SELECT * FROM test WHERE status = ?",
            ("active",),
        )
        assert result == [{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}]

    @pytest.mark.asyncio
    async def test_mysql_connection_fetch_all_empty_result(self):
        """Test MySQL connection fetch_all with empty results"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        # Mock cursor() to return a context manager that accepts arguments
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context

        conn = MySQLConnection(mock_conn)

        result = await conn.fetch_all("SELECT * FROM test WHERE id > ?", (100,))
        assert result == []

    @pytest.mark.asyncio
    async def test_mysql_connection_fetch_all_with_monitoring(self, mock_monitor):
        """Test MySQL connection fetch_all method with monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[{"id": 1, "name": "test"}])

        # Mock cursor() to return a context manager that accepts arguments
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context

        conn = MySQLConnection(mock_conn, mock_monitor)

        result = await conn.fetch_all("SELECT * FROM test")
        assert result == [{"id": 1, "name": "test"}]

        # Verify monitoring was called
        mock_monitor.get_query_monitor.assert_called_once()

    @pytest.mark.asyncio
    async def test_mysql_connection_fetch_all_error(self):
        """Test MySQL connection fetch_all error handling"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()

        # Mock cursor() to return a context manager
        @asynccontextmanager
        async def mock_cursor_context(*args, **kwargs):
            yield mock_cursor

        mock_conn.cursor = mock_cursor_context
        mock_cursor.execute = AsyncMock(side_effect=aiomysql.Error("Fetch all failed"))

        conn = MySQLConnection(mock_conn)

        with pytest.raises(QueryError, match="Query fetch all failed"):
            await conn.fetch_all("SELECT * FROM nonexistent")

    @pytest.mark.asyncio
    async def test_mysql_connection_close(self):
        """Test MySQL connection close method (should be no-op)"""
        mock_conn = AsyncMock()
        conn = MySQLConnection(mock_conn)

        # Close should not raise exception (it's a no-op for MySQL connections)
        await conn.close()

