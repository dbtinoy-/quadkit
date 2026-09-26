"""PostgreSQL pool lifecycle and close tests."""

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


    @pytest.mark.asyncio
    async def test_postgres_pool_creation(self):
        """Test PostgreSQL pool creation"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            pool = PostgresConnectionPool("postgresql://user:pass@localhost:5432/test")
            await pool.initialize()

            mock_asyncpg.create_pool.assert_called_once()
            call_args = mock_asyncpg.create_pool.call_args
            assert call_args[1]["min_size"] == 10
            assert call_args[1]["max_size"] == 20

    @pytest.mark.asyncio
    async def test_postgres_pool_initialization_success(self):
        """Test PostgreSQL pool initialization success"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            pool = PostgresConnectionPool("postgresql://user:pass@localhost:5432/test")
            await pool.initialize()

            assert pool._pool is not None
            assert pool._is_healthy is True
            assert pool._total_connections_created == 1

    @pytest.mark.asyncio
    async def test_postgres_pool_initialization_with_ssl(self):
        """Test PostgreSQL pool initialization with SSL"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            pool = PostgresConnectionPool(
                "postgresql://user:pass@localhost:5432/test",
                ssl={"verify_cert": False},
            )

            await pool.initialize()

            mock_asyncpg.create_pool.assert_called_once()
            call_args = mock_asyncpg.create_pool.call_args
            assert call_args[1]["ssl"] is not None

    @pytest.mark.asyncio
    async def test_postgres_pool_initialization_failure(self):
        """Test PostgreSQL pool initialization failure"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.create_pool = AsyncMock(
                side_effect=Exception("Connection failed"),
            )

            # Create a custom retry config with proper exception types
            from quadkit.contracts.infra.resilience import RetryConfig

            retry_config = RetryConfig(
                max_attempts=3,
                base_delay=1.0,
                retry_on=(ConnectionError,),
            )

            pool = PostgresConnectionPool(
                "postgresql://user:pass@localhost:5432/test",
                retry_config=retry_config,
            )

            with pytest.raises(DatabaseConnectionError, match="Pool creation failed"):
                await pool.initialize()

            assert pool._pool is None
            assert pool._is_healthy is False
            assert pool._error_count == 1

    @pytest.mark.asyncio
    async def test_postgres_pool_double_initialization(self):
        """Test PostgreSQL pool double initialization"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            pool = PostgresConnectionPool("postgresql://user:pass@localhost:5432/test")
            await pool.initialize()
            await pool.initialize()  # Should not create pool again

            # Should only be called once
            mock_asyncpg.create_pool.assert_called_once()


    @pytest.mark.asyncio
    async def test_postgres_pool_get_connection_error(self):
        """Test PostgreSQL pool get_connection error"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()

            # Mock pool.acquire() to return an async context manager that raises exception
            class FailingAsyncContextManager:
                async def __aenter__(self):
                    raise Exception("Pool exhausted")

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass

            mock_pool.acquire = Mock(return_value=FailingAsyncContextManager())
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            pool = PostgresConnectionPool("postgresql://user:pass@localhost:5432/test")
            await pool.initialize()

            # Mock circuit breaker
            mock_circuit_breaker = AsyncMock()

            @asynccontextmanager
            async def mock_protect():
                yield

            mock_circuit_breaker.protect = mock_protect
            pool.circuit_breaker = mock_circuit_breaker

            with pytest.raises(
                DatabaseConnectionError,
                match="Connection acquisition failed",
            ):
                async with pool.get_connection():
                    pass

            assert pool._error_count == 1
            assert pool._is_healthy is False

    @pytest.mark.asyncio
    async def test_postgres_pool_close(self):
        """Test PostgreSQL pool close"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            pool = PostgresConnectionPool("postgresql://user:pass@localhost:5432/test")
            await pool.initialize()

            await pool.shutdown()

            assert pool._pool is None
            assert pool._is_healthy is False
            mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_postgres_pool_close_without_initialization(self):
        """Test PostgreSQL pool close without initialization"""
        pool = PostgresConnectionPool("postgresql://user:pass@localhost:5432/test")

        await pool.shutdown()  # Should not raise any errors

