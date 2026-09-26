"""PostgreSQL connection execution and fetch tests."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    import asyncpg

    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False
    asyncpg = None  # type: ignore[assignment]

from quadkit.contracts.core import HealthStatus
from quadkit.sql.backends.postgres import (
    HAS_POSTGRES,
    PostgresConnection,
    PostgresConnectionPool,
    create_postgres_pool,
)
from quadkit.sql.exceptions import DatabaseConnectionError, QueryError



@pytest.mark.skipif(not HAS_POSTGRES, reason="asyncpg not available")
class TestPostgresDriver:
    """Test PostgreSQL driver functionality"""

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

        # Make monitor_query both callable and have mock methods
        monitor_query_mock.side_effect = monitor_query
        query_monitor.monitor_query = monitor_query_mock
        monitor.get_query_monitor.return_value = query_monitor
        monitor.start_pool_monitoring = AsyncMock()
        monitor.stop_pool_monitoring = AsyncMock()
        monitor.get_stats = AsyncMock(return_value={})
        return monitor


    @pytest.mark.asyncio
    async def test_postgres_connection_creation(self):
        """Test PostgreSQL connection creation"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()

            # Mock pool.acquire() to return an async context manager
            @asynccontextmanager
            async def mock_acquire():
                yield mock_conn

            mock_pool.acquire = mock_acquire
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            pool = PostgresConnectionPool("postgresql://user:pass@localhost:5432/test")
            await pool.initialize()

            # Mock circuit breaker as async context manager
            mock_circuit_breaker = AsyncMock()

            @asynccontextmanager
            async def mock_protect():
                yield

            mock_circuit_breaker.protect = mock_protect
            mock_circuit_breaker.state = AsyncMock()
            mock_circuit_breaker.state.value = "closed"
            pool.circuit_breaker = mock_circuit_breaker

            async with pool.get_connection() as conn:
                assert isinstance(conn, PostgresConnection)
                assert conn._conn == mock_conn
                assert pool._connection_count == 1

    @pytest.mark.asyncio
    async def test_postgres_connection_execute_without_monitoring(self):
        """Test PostgreSQL connection execute without monitoring"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        conn = PostgresConnection(mock_conn)

        result = await conn.execute("INSERT INTO test VALUES ($1)", (1,))

        assert result == "INSERT 1"
        mock_conn.execute.assert_called_once_with("INSERT INTO test VALUES ($1)", 1)

    @pytest.mark.asyncio
    async def test_postgres_connection_execute_with_monitoring(self, mock_monitor):
        """Test PostgreSQL connection execute with monitoring"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        conn = PostgresConnection(mock_conn, mock_monitor)

        result = await conn.execute("INSERT INTO test VALUES ($1)", (1,))

        assert result == "INSERT 1"
        mock_monitor.get_query_monitor.assert_called_once()
        mock_monitor.get_query_monitor().monitor_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_postgres_connection_execute_error(self):
        """Test PostgreSQL connection execute error"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=asyncpg.PostgresError("Syntax error"))

        conn = PostgresConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.execute("INVALID SQL")

        error = exc_info.value
        assert "Query execution failed" in str(error)
        assert error.details["query"] == "INVALID SQL"
        assert "Syntax error" in error.details["error"]

    @pytest.mark.asyncio
    async def test_postgres_connection_execute_many(self):
        """Test PostgreSQL connection execute_many"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        # Mock transaction as async context manager
        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_conn.transaction = mock_transaction

        conn = PostgresConnection(mock_conn)

        params_list = [(1,), (2,), (3,)]
        await conn.execute_many("INSERT INTO test VALUES ($1)", params_list)

        # Verify executes were called
        assert mock_conn.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_get_stats_reports_monitoring_enabled(self, mock_monitor):
        """Pool.get_stats should report monitoring availability"""
        with patch("quadkit.sql.backends.postgres.HAS_MONITORING", True):
            pool = PostgresConnectionPool(
                "postgresql://user:pass@localhost:5432/test",
                monitor=mock_monitor,
            )
            stats = await pool.get_pool_stats()
            assert stats.get("monitoring_enabled") is True

    @pytest.mark.asyncio
    async def test_postgres_connection_execute_many_error(self):
        """Test PostgreSQL connection execute_many error"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(
            side_effect=asyncpg.PostgresError("Constraint violation"),
        )

        # Mock transaction as async context manager
        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_conn.transaction = mock_transaction

        conn = PostgresConnection(mock_conn)

        params_list = [(1,), (2,)]
        with pytest.raises(QueryError) as exc_info:
            await conn.execute_many("INSERT INTO test VALUES ($1)", params_list)

        error = exc_info.value
        assert "Batch execution failed" in str(error)
        assert error.details["query"] == "INSERT INTO test VALUES ($1)"
        assert "Constraint violation" in error.details["error"]

    @pytest.mark.asyncio
    async def test_postgres_connection_fetch_one_without_monitoring(self):
        """Test PostgreSQL connection fetch_one without monitoring"""
        mock_conn = AsyncMock()
        mock_record = Mock()
        mock_record.__getitem__ = Mock(
            side_effect=lambda k: {"id": 1, "name": "test"}[k],
        )
        mock_record.keys = Mock(return_value=["id", "name"])
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        conn = PostgresConnection(mock_conn)

        result = await conn.fetch_one("SELECT * FROM test WHERE id = $1", (1,))

        assert result == {"id": 1, "name": "test"}
        mock_conn.fetchrow.assert_called_once_with(
            "SELECT * FROM test WHERE id = $1",
            1,
        )

    @pytest.mark.asyncio
    async def test_postgres_connection_fetch_one_with_monitoring(self, mock_monitor):
        """Test PostgreSQL connection fetch_one with monitoring"""
        mock_conn = AsyncMock()
        mock_record = Mock()
        mock_record.__getitem__ = Mock(
            side_effect=lambda k: {"id": 1, "name": "test"}[k],
        )
        mock_record.keys = Mock(return_value=["id", "name"])
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        conn = PostgresConnection(mock_conn, mock_monitor)

        result = await conn.fetch_one("SELECT * FROM test WHERE id = $1", (1,))

        assert result == {"id": 1, "name": "test"}
        mock_monitor.get_query_monitor.assert_called_once()

    @pytest.mark.asyncio
    async def test_postgres_connection_fetch_one_none_result(self):
        """Test PostgreSQL connection fetch_one with no results"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        conn = PostgresConnection(mock_conn)

        result = await conn.fetch_one("SELECT * FROM test WHERE id = $1", (999,))

        assert result is None

    @pytest.mark.asyncio
    async def test_postgres_connection_fetch_one_error(self):
        """Test PostgreSQL connection fetch_one error"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            side_effect=asyncpg.PostgresError("Table doesn't exist"),
        )

        conn = PostgresConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.fetch_one("SELECT * FROM nonexistent_table")

        error = exc_info.value
        assert "Query fetch failed" in str(error)
        assert error.details["query"] == "SELECT * FROM nonexistent_table"
        assert "Table doesn't exist" in error.details["error"]

    @pytest.mark.asyncio
    async def test_postgres_connection_fetch_all_without_monitoring(self):
        """Test PostgreSQL connection fetch_all without monitoring"""
        mock_conn = AsyncMock()
        mock_records = []
        for i in range(3):
            mock_record = Mock()

            # Create a closure with the current value of i
            def make_getitem(record_id):
                return lambda self, k: {"id": record_id, "name": f"test{record_id}"}[k]

            mock_record.__getitem__ = make_getitem(i + 1)
            mock_record.keys = Mock(return_value=["id", "name"])
            mock_records.append(mock_record)

        mock_conn.fetch = AsyncMock(return_value=mock_records)

        conn = PostgresConnection(mock_conn)

        result = await conn.fetch_all("SELECT * FROM test")

        assert len(result) == 3
        assert result[0] == {"id": 1, "name": "test1"}
        assert result[1] == {"id": 2, "name": "test2"}
        assert result[2] == {"id": 3, "name": "test3"}
        mock_conn.fetch.assert_called_once_with("SELECT * FROM test")

    @pytest.mark.asyncio
    async def test_postgres_connection_fetch_all_empty_result(self):
        """Test PostgreSQL connection fetch_all with empty results"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        conn = PostgresConnection(mock_conn)

        result = await conn.fetch_all("SELECT * FROM test WHERE id = $1", (999,))

        assert result == []

    @pytest.mark.asyncio
    async def test_postgres_connection_fetch_all_with_monitoring(self, mock_monitor):
        """Test PostgreSQL connection fetch_all with monitoring"""
        mock_conn = AsyncMock()
        mock_records = []
        for i in range(2):
            mock_record = Mock()

            # Create a closure with the current value of i
            def make_getitem(record_id):
                return lambda self, k: {"id": record_id, "name": f"test{record_id}"}[k]

            mock_record.__getitem__ = make_getitem(i + 1)
            mock_record.keys = Mock(return_value=["id", "name"])
            mock_records.append(mock_record)

        mock_conn.fetch = AsyncMock(return_value=mock_records)

        conn = PostgresConnection(mock_conn, mock_monitor)

        result = await conn.fetch_all("SELECT * FROM test")

        assert len(result) == 2
        mock_monitor.get_query_monitor.assert_called_once()

    @pytest.mark.asyncio
    async def test_postgres_connection_fetch_all_error(self):
        """Test PostgreSQL connection fetch_all error"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            side_effect=asyncpg.PostgresError("Permission denied"),
        )

        conn = PostgresConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.fetch_all("SELECT * FROM restricted_table")

        error = exc_info.value
        assert "Query fetch all failed" in str(error)
        assert error.details["query"] == "SELECT * FROM restricted_table"
        assert "Permission denied" in error.details["error"]

    @pytest.mark.asyncio
    async def test_postgres_connection_close(self):
        """Test PostgreSQL connection close"""
        mock_conn = AsyncMock()
        conn = PostgresConnection(mock_conn)

        await conn.close()  # Should not raise any errors

