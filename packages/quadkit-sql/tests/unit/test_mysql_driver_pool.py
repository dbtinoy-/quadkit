"""MySQL driver pool lifecycle tests."""

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    import aiomysql

    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False
    aiomysql = None  # type: ignore[assignment]

from quadkit.sql.backends.mysql import (
    HAS_MYSQL,
    MySQLConnectionPool,
    create_mysql_pool,
)
from quadkit.sql.exceptions import DatabaseConnectionError


@pytest.mark.skipif(not HAS_MYSQL, reason="aiomysql not available")
class TestMySQLDriver:
    def test_mysql_pool_creation(self):
        """Test MySQL pool creation with various parameters"""
        # Basic creation
        pool = create_mysql_pool(
            host="localhost",
            user="root",
            password="pass",
            database="test",
        )
        assert isinstance(pool, MySQLConnectionPool)
        assert pool.host == "localhost"
        assert pool.user == "root"
        assert pool.password == "pass"
        assert pool.database == "test"
        assert pool.port == 3306  # default
        assert pool.min_size == 10  # default
        assert pool.max_size == 20  # default

        # Custom parameters
        pool = MySQLConnectionPool(
            host="mysql.example.com",
            port=3307,
            user="admin",
            password="secret",
            database="production",
            min_size=5,
            max_size=50,
            ssl={"ca": "/path/to/ca.pem"},
        )
        assert pool.host == "mysql.example.com"
        assert pool.port == 3307
        assert pool.user == "admin"
        assert pool.database == "production"
        assert pool.min_size == 5
        assert pool.max_size == 50
        assert pool.ssl == {"ca": "/path/to/ca.pem"}

    @pytest.mark.asyncio
    async def test_mysql_pool_initialization_success(self):
        """Test successful MySQL pool initialization"""
        mock_pool = AsyncMock()

        pool = MySQLConnectionPool("localhost", 3306, "root", "pass", "test")

        # Mock the _create_pool method to avoid aiomysql.create_pool call
        async def mock_create_pool(pool_kwargs):
            pool._pool = mock_pool
            pool._total_connections_created += 1
            pool._is_healthy = True

        with patch.object(pool, "_create_pool", side_effect=mock_create_pool):
            await pool.initialize()

            assert pool._pool == mock_pool
            assert pool._is_healthy is True
            assert pool._total_connections_created == 1

    @pytest.mark.asyncio
    async def test_mysql_pool_initialization_with_ssl(self):
        """Test MySQL pool initialization with SSL configuration"""
        mock_pool = AsyncMock()

        ssl_config = {"ca": "/path/to/ca.pem", "cert": "/path/to/client-cert.pem"}
        pool = MySQLConnectionPool(
            "localhost",
            3306,
            "root",
            "pass",
            "test",
            ssl=ssl_config,
        )

        # Mock the _create_pool method
        async def mock_create_pool(pool_kwargs):
            pool._pool = mock_pool
            pool._total_connections_created += 1
            pool._is_healthy = True

        with patch.object(pool, "_create_pool", side_effect=mock_create_pool):
            await pool.initialize()

            # Verify SSL config was passed to aiomysql (would be in pool_kwargs)
            assert pool.ssl == ssl_config

    @pytest.mark.asyncio
    async def test_mysql_pool_initialization_failure(self):
        """Test MySQL pool initialization failure"""
        # Explicit single-attempt retry policy: the wrapped error
        # propagates directly (BUG #38 regression guard — the
        # constructor's *default* config now retries and would surface
        # RetryExhaustedError instead).
        from quadkit.contracts.infra.resilience import RetryConfig

        pool = MySQLConnectionPool(
            "localhost",
            3306,
            "root",
            "pass",
            "test",
            retry_config=RetryConfig(max_attempts=1, base_delay=0, jitter=False),
        )

        # Patch retry_call (the function initialize actually awaits) to
        # raise the wrapped driver error.  Note: patching
        # ``pool._create_pool`` does NOT intercept here — initialize calls
        # retry_call directly, which resolves ``self._create_pool`` at
        # call time.
        async def failing_retry(*_args: Any, **_kwargs: Any) -> Any:
            raise DatabaseConnectionError("Connection failed")

        with (
            patch(
                "quadkit.sql.backends.mysql._pool.retry_call",
                side_effect=failing_retry,
            ),
            pytest.raises(DatabaseConnectionError, match="Connection failed"),
        ):
            await pool.initialize()

        assert pool._is_healthy is False
        assert pool._error_count == 0  # Error count is not incremented in this case

    @pytest.mark.asyncio
    async def test_mysql_pool_double_initialization(self):
        """Test that pool initialization is idempotent"""
        mock_pool = AsyncMock()

        pool = MySQLConnectionPool("localhost", 3306, "root", "pass", "test")

        # Mock the _create_pool method
        async def mock_create_pool(pool_kwargs):
            pool._pool = mock_pool
            pool._total_connections_created += 1
            pool._is_healthy = True

        with patch.object(pool, "_create_pool", side_effect=mock_create_pool):
            await pool.initialize()
            await pool.initialize()  # Should not create another pool

            # Should only be called once
            assert pool._total_connections_created == 1

    async def test_mysql_pool_get_connection_error(self):
        """Test MySQL pool get_connection error handling"""
        mock_pool = AsyncMock()

        pool = MySQLConnectionPool("localhost", 3306, "root", "pass", "test")

        # Mock the _create_pool method
        async def mock_create_pool(pool_kwargs):
            pool._pool = mock_pool
            pool._total_connections_created += 1
            pool._is_healthy = True

        # Mock pool.acquire() to return an async context manager that raises exception
        class FailingAsyncContextManager:
            async def __aenter__(self) -> Any:
                msg = "Connection failed"
                raise RuntimeError(msg)

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

            with pytest.raises(
                DatabaseConnectionError,
                match="Connection acquisition failed",
            ):
                async with pool.get_connection():
                    pass

            assert pool._error_count == 1

    @pytest.mark.asyncio
    async def test_mysql_pool_close(self):
        """Test MySQL pool close method"""
        mock_pool = AsyncMock()
        mock_pool.close = Mock()  # close() is synchronous
        mock_pool.wait_closed = AsyncMock()  # wait_closed() is async

        pool = MySQLConnectionPool("localhost", 3306, "root", "pass", "test")

        # Mock the _create_pool method
        async def mock_create_pool(pool_kwargs):
            pool._pool = mock_pool
            pool._total_connections_created += 1
            pool._is_healthy = True

        with patch.object(pool, "_create_pool", side_effect=mock_create_pool):
            await pool.initialize()

            assert pool._pool is not None
            assert pool._is_healthy is True

            await pool.shutdown()

            assert pool._pool is None
            assert pool._is_healthy is False
            mock_pool.close.assert_called_once()
            mock_pool.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_mysql_pool_close_without_initialization(self):
        """Test MySQL pool close when not initialized"""
        pool = MySQLConnectionPool("localhost", 3306, "root", "pass", "test")

        # Should not raise exception
        await pool.shutdown()
        assert pool._pool is None
