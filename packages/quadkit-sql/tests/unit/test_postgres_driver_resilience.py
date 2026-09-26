"""PostgreSQL monitoring, retry, circuit-breaker, and factory tests."""

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
    async def test_postgres_pool_get_stats(self):
        """Test PostgreSQL pool statistics"""
        pool = PostgresConnectionPool(
            "postgresql://user:pass@localhost:5432/test",
            min_size=5,
            max_size=25,
        )

        stats = await pool.get_pool_stats()

        assert stats["pool_size"] == "5-25"
        assert stats["is_initialized"] is False
        assert stats["is_healthy"] is False
        assert stats["total_connections_created"] == 0
        assert stats["active_connection_count"] == 0
        assert stats["error_count"] == 0
        assert "circuit_breaker_state" in stats
        assert "last_health_check" in stats

    @pytest.mark.asyncio
    async def test_postgres_pool_with_monitoring(self, mock_monitor):
        """Test PostgreSQL pool with monitoring enabled"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            pool = PostgresConnectionPool(
                "postgresql://user:pass@localhost:5432/test",
                monitor=mock_monitor,
            )
            await pool.initialize()

            assert pool.monitor == mock_monitor
            mock_monitor.start_pool_monitoring.assert_called_once()

            await pool.shutdown()
            mock_monitor.stop_pool_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_postgres_pool_retry_logic(self):
        """Test PostgreSQL pool retry logic on initialization failures"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_asyncpg.create_pool = AsyncMock()
            # Mock retry to track calls

            with patch(
                "quadkit.sql.backends.postgres.retry_call", new_callable=AsyncMock
            ) as mock_retry:
                mock_pool = AsyncMock()
                mock_retry.return_value = mock_pool

                pool = PostgresConnectionPool(
                    "postgresql://user:pass@localhost:5432/test",
                )
                await pool.initialize()

                # Verify retry_async was called with correct parameters
                mock_retry.assert_called_once()
                call_args = mock_retry.call_args
                assert call_args[0][0] == pool._create_pool  # Function to retry
                assert call_args[1]["config"] == pool.retry_config  # Retry config

    @pytest.mark.asyncio
    async def test_postgres_pool_circuit_breaker(self):
        """Test PostgreSQL pool circuit breaker integration"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()

            # Mock pool.acquire() to return an async context manager that raises exception
            class FailingAsyncContextManager:
                async def __aenter__(self):
                    raise Exception("Connection failed")

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass

            mock_pool.acquire = Mock(return_value=FailingAsyncContextManager())
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            pool = PostgresConnectionPool("postgresql://user:pass@localhost:5432/test")
            await pool.initialize()

            # Mock circuit breaker
            mock_circuit_breaker = Mock()

            @asynccontextmanager
            async def mock_protect():
                yield

            mock_circuit_breaker.protect = Mock(side_effect=mock_protect)
            pool.circuit_breaker = mock_circuit_breaker

            with pytest.raises(DatabaseConnectionError):
                async with pool.get_connection():
                    pass

            # Verify circuit breaker was used
            mock_circuit_breaker.protect.assert_called_once()

    @pytest.mark.asyncio
    async def test_postgres_connection_with_custom_monitor(self, mock_monitor):
        """Test PostgreSQL connection with custom monitor"""
        mock_conn = AsyncMock()
        conn = PostgresConnection(mock_conn, mock_monitor)

        assert conn.monitor == mock_monitor
        assert conn.connection_id.startswith("postgres_")


    def test_postgres_import_error_when_unavailable(self):
        """Test PostgreSQL import error when asyncpg not available"""
        with patch("quadkit.sql.backends.postgres.HAS_POSTGRES", False):
            with pytest.raises(
                ImportError,
                match="asyncpg is required for PostgreSQL support",
            ):
                PostgresConnectionPool(
                    host="localhost",
                    port=5432,
                    user="user",
                    password="pass",
                    database="test",
                )

    @pytest.mark.asyncio
    async def test_postgres_factory_function(self):
        """Test create_postgres_pool factory function"""
        mock_monitor = Mock()
        mock_monitor.start_pool_monitoring = AsyncMock()

        pool = create_postgres_pool(
            host="postgres.example.com",
            port=5432,
            user="admin",
            password="secret",
            database="production",
            min_size=5,
            max_size=50,
            ssl={"verify_cert": False},
            monitor=mock_monitor,
        )

        assert isinstance(pool, PostgresConnectionPool)
        assert pool.host == "postgres.example.com"
        assert pool.database == "production"

        assert pool.min_size == 5
        assert pool.max_size == 50
        assert pool.ssl == {"verify_cert": False}

        assert pool.monitor == mock_monitor

    @pytest.mark.asyncio
    async def test_postgres_connection_error_details(self):
        """Test PostgreSQL connection error includes query details"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("Network timeout"))

        conn = PostgresConnection(mock_conn)

        with pytest.raises(DatabaseConnectionError) as exc_info:
            await conn.execute("SELECT * FROM large_table", (1, 2, 3))

        error = exc_info.value
        assert "Connection error" in str(error)
        assert error.details["query"] == "SELECT * FROM large_table"
        assert "Network timeout" in error.details["error"]

    @pytest.mark.asyncio
    async def test_postgres_fetch_error_details(self):
        """Test PostgreSQL fetch error includes query details"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            side_effect=asyncpg.PostgresError("Column doesn't exist"),
        )

        conn = PostgresConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.fetch_one("SELECT nonexistent_column FROM test", (1,))

        error = exc_info.value
        assert "Query fetch failed" in str(error)
        assert error.details["query"] == "SELECT nonexistent_column FROM test"
        assert "Column doesn't exist" in error.details["error"]

    @pytest.mark.asyncio
    async def test_postgres_execute_many_error_details(self):
        """Test PostgreSQL execute_many error includes query details"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(
            side_effect=asyncpg.PostgresError("Duplicate key"),
        )

        # Mock transaction as async context manager
        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_conn.transaction = mock_transaction

        conn = PostgresConnection(mock_conn)

        params_list = [("value1",), ("value2",)]
        with pytest.raises(QueryError) as exc_info:
            await conn.execute_many("INSERT INTO unique_table VALUES ($1)", params_list)

        error = exc_info.value
        assert "Batch execution failed" in str(error)
        assert error.details["query"] == "INSERT INTO unique_table VALUES ($1)"
        assert "Duplicate key" in error.details["error"]
