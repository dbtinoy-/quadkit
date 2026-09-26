"""MySQL driver pool health-check tests."""

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


    async def test_mysql_pool_health_check_healthy(self):
        """Test MySQL pool health check when healthy"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=None)
        mock_conn.affected_rows = 1

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

            # Mock circuit breaker as async context manager for get_connection
            @asynccontextmanager
            async def mock_circuit_breaker():
                yield

            mock_cb = Mock()
            mock_cb.protect.side_effect = mock_circuit_breaker

            pool.circuit_breaker = mock_cb

            health = await pool.health_check()

            assert health.status == HealthStatus.HEALTHY
            assert health.details.get("host") == "localhost:3306"
            assert health.details.get("database") == "test"
            assert health.details.get("pool_size") == "10-20"
            assert health.details.get("connections_created") == 1
            assert "active_connections" in health.details
            assert "error_count" in health.details

    @pytest.mark.asyncio
    async def test_mysql_pool_health_check_unhealthy_no_pool(self):
        """Test MySQL pool health check when pool not initialized"""
        pool = MySQLConnectionPool("localhost", 3306, "root", "pass", "test")

        health = await pool.health_check()

        assert health.status == HealthStatus.UNHEALTHY
        assert "Pool not initialized" in (health.error or "")

    @pytest.mark.asyncio
    async def test_mysql_pool_health_check_unhealthy_query_failed(self):
        """Test MySQL pool health check when query fails"""
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

            health = await pool.health_check()

            assert health.status == HealthStatus.UNHEALTHY
            assert health.error is not None
            assert health.details.get("error_count") == 1

    @pytest.mark.asyncio
    async def test_mysql_pool_health_check_caching(self):
        """Test MySQL pool health check caching"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=None)
        mock_conn.affected_rows = 1

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

            # Mock circuit breaker as async context manager for get_connection
            @asynccontextmanager
            async def mock_circuit_breaker():
                yield

            mock_cb = Mock()
            mock_cb.protect.side_effect = mock_circuit_breaker

            pool.circuit_breaker = mock_cb

            # First health check
            health1 = await pool.health_check()
            assert health1.status == HealthStatus.HEALTHY

            # Second health check (should be cached if within 30 seconds)
            await asyncio.sleep(0.01)  # Small delay
            health2 = await pool.health_check()

            # Should be the same result (cached)
            assert health2.status == HealthStatus.HEALTHY
            assert health2.details.get("cached") is True

