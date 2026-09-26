"""PostgreSQL pool health-check tests."""

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
    async def test_postgres_pool_health_check_healthy(self):
        """Test PostgreSQL pool health check when healthy"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value="SELECT 1")

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

            health = await pool.health_check()

            assert health.status == HealthStatus.HEALTHY
            assert health.details.get("pool_size") == "10-20"
            assert health.details.get("connections_created") == 1
            assert "active_connections" in health.details
            assert "error_count" in health.details

    @pytest.mark.asyncio
    async def test_postgres_pool_health_check_unhealthy_no_pool(self):
        """Test PostgreSQL pool health check when pool not initialized"""
        pool = PostgresConnectionPool("postgresql://user:pass@localhost:5432/test")

        health = await pool.health_check()

        assert health.status == HealthStatus.UNHEALTHY
        assert "Pool not initialized" in (health.error or "")

    @pytest.mark.asyncio
    async def test_postgres_pool_health_check_unhealthy_query_failed(self):
        """Test PostgreSQL pool health check when query fails"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_asyncpg.PostgresConnectionError = Exception
            mock_asyncpg.PostgresPoolAcquisitionError = Exception
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

            health = await pool.health_check()

            assert health.status == HealthStatus.UNHEALTHY
            assert health.error is not None
            assert health.details.get("error_count") == 1  # Health check error

    @pytest.mark.asyncio
    async def test_postgres_pool_health_check_caching(self):
        """Test PostgreSQL pool health check caching"""
        with patch("quadkit.sql.backends.postgres.asyncpg") as mock_asyncpg:
            mock_asyncpg.PostgresError = Exception
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value="SELECT 1")

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

            # First health check
            health1 = await pool.health_check()
            assert health1.status == HealthStatus.HEALTHY

            # Second health check (should be cached if within 30 seconds)
            await asyncio.sleep(0.01)  # Small delay
            health2 = await pool.health_check()

            # Should be the same result (cached)
            assert health2.status == HealthStatus.HEALTHY
            assert health2.details.get("cached") is True

