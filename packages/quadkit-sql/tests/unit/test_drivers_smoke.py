"""Cross-driver availability, instantiation, and import tests."""

"""Tests for Quadkit DB drivers"""

from contextlib import asynccontextmanager
import importlib.util
from unittest.mock import AsyncMock, Mock, patch

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.sql.backends.mysql import MySQLConnectionPool, create_mysql_pool
from quadkit.sql.backends.postgres import PostgresConnectionPool, create_postgres_pool
from quadkit.sql.backends.sqlite import (
    SQLiteConnection,
    SQLiteConnectionPool,
    create_sqlite_pool,
)
from quadkit.sql.monitoring import DatabaseMonitor, InMemoryDbMetricsCollector

# Import availability flags
try:
    from quadkit.sql.backends.postgres import HAS_POSTGRES
except ImportError:
    HAS_POSTGRES = False

try:
    from quadkit.sql.backends.mysql import HAS_MYSQL
except ImportError:
    HAS_MYSQL = False

try:
    from quadkit.sql.backends.sqlite import HAS_SQLITE
except ImportError:
    HAS_SQLITE = False




class TestPostgresDriver:
    """Test PostgreSQL driver"""

    @pytest.mark.skipif(not HAS_POSTGRES, reason="asyncpg not available")
    @pytest.mark.asyncio
    async def test_postgres_pool_creation(self):
        """Test PostgreSQL pool creation"""
        pool = create_postgres_pool(
            host="localhost",
            port=5432,
            user="user",
            password="pass",
            database="test",
        )
        assert isinstance(pool, PostgresConnectionPool)
        assert pool.host == "localhost"
        assert pool.database == "test"

    @pytest.mark.skipif(not HAS_POSTGRES, reason="asyncpg not available")
    @pytest.mark.asyncio
    @patch("quadkit.sql.backends.postgres.asyncpg.create_pool", new_callable=AsyncMock)
    async def test_postgres_pool_initialization(self, mock_create_pool):
        """Test PostgreSQL pool initialization"""
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        pool = PostgresConnectionPool(
            host="localhost",
            port=5432,
            user="user",
            password="pass",
            database="test",
        )

        await pool.initialize()

        mock_create_pool.assert_called_once()
        assert pool._pool == mock_pool

    @pytest.mark.skipif(not HAS_POSTGRES, reason="asyncpg not available")
    @pytest.mark.asyncio
    @patch("quadkit.sql.backends.postgres.asyncpg.create_pool")
    async def test_postgres_health_check(self, mock_create_pool):
        """Test PostgreSQL health check functionality"""
        from unittest.mock import AsyncMock, MagicMock

        mock_conn = AsyncMock()
        mock_pool = MagicMock()  # Use MagicMock instead of AsyncMock
        mock_conn.execute.return_value = "SELECT 1"

        # Create a proper async context manager for acquire()
        class MockAcquireContext:
            def __init__(self, conn):
                self.conn = conn

            async def __aenter__(self):
                return self.conn

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_pool.acquire.return_value = MockAcquireContext(mock_conn)

        # Make the mock return a coroutine that returns the mock pool
        async def mock_create_pool_coro(*args, **kwargs):
            return mock_pool

        mock_create_pool.side_effect = mock_create_pool_coro

        pool = PostgresConnectionPool(
            host="localhost",
            port=5432,
            user="user",
            password="pass",
            database="test",
        )

        await pool.initialize()

        health = await pool.health_check()
        assert health.status == HealthStatus.HEALTHY
        assert "pool_size" in health.details
        assert "connections_created" in health.details

    @pytest.mark.skipif(not HAS_POSTGRES, reason="asyncpg not available")
    @pytest.mark.asyncio
    async def test_postgres_pool_with_ssl(self):
        """Test PostgreSQL pool creation with SSL configuration"""
        pool = create_postgres_pool(
            host="localhost",
            port=5432,
            user="user",
            password="pass",
            database="test",
            ssl={"verify_cert": False},
        )
        assert pool.ssl == {"verify_cert": False}

        assert isinstance(pool, PostgresConnectionPool)

    @pytest.mark.skipif(not HAS_POSTGRES, reason="asyncpg not available")
    @pytest.mark.asyncio
    async def test_postgres_pool_stats(self):
        """Test PostgreSQL pool statistics"""
        pool = PostgresConnectionPool(
            host="localhost",
            port=5432,
            user="user",
            password="pass",
            database="test",
        )
        stats = await pool.get_pool_stats()

        assert "pool_size" in stats
        assert "is_initialized" in stats
        assert "is_healthy" in stats
        assert "total_connections_created" in stats
        assert "error_count" in stats
        assert "circuit_breaker_state" in stats


class TestMySQLDriver:
    """Test MySQL driver"""

    @pytest.mark.skipif(not HAS_MYSQL, reason="aiomysql not available")
    @pytest.mark.asyncio
    async def test_mysql_pool_creation(self):
        """Test MySQL pool creation"""
        pool = create_mysql_pool(
            host="localhost",
            user="root",
            password="pass",
            database="test",
        )
        assert isinstance(pool, MySQLConnectionPool)
        assert pool.host == "localhost"
        assert pool.user == "root"
        assert pool.database == "test"

    @pytest.mark.skipif(not HAS_MYSQL, reason="aiomysql not available")
    @pytest.mark.asyncio
    @patch("quadkit.sql.backends.mysql._pool.aiomysql.create_pool", new_callable=AsyncMock)
    async def test_mysql_pool_initialization(self, mock_create_pool):
        """Test MySQL pool initialization"""
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        pool = MySQLConnectionPool("localhost", 3306, "root", "pass", "test")
        await pool.initialize()

        mock_create_pool.assert_called_once()
        assert pool._pool == mock_pool


class TestSQLiteDriver:
    """Test SQLite driver"""

    @pytest.mark.skipif(not HAS_SQLITE, reason="aiosqlite not available")
    @pytest.mark.asyncio
    async def test_sqlite_pool_creation(self):
        """Test SQLite pool creation"""
        pool = create_sqlite_pool(":memory:")
        assert isinstance(pool, SQLiteConnectionPool)
        assert pool.database == ":memory:"

    @pytest.mark.skipif(not HAS_SQLITE, reason="aiosqlite not available")
    @pytest.mark.asyncio
    @patch("quadkit.sql.backends.sqlite._pool.aiosqlite")
    async def test_sqlite_pool_initialization(self, mock_aiosqlite):
        """Test SQLite pool initialization"""
        mock_conn = AsyncMock()
        mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

        pool = SQLiteConnectionPool(":memory:")
        await pool.initialize()

        mock_aiosqlite.connect.assert_called_once()
        assert pool._conn == mock_conn


class TestDriverImports:
    """Test driver imports work correctly"""

    def test_postgres_import(self):
        """Test PostgreSQL driver can be imported"""
        if importlib.util.find_spec("quadkit.sql.backends.postgres") is None:
            pytest.skip("asyncpg not available")

    def test_mysql_import(self):
        """Test MySQL driver can be imported"""
        if importlib.util.find_spec("quadkit.sql.backends.mysql") is None:
            pytest.skip("aiomysql not available")

    def test_sqlite_import(self):
        """Test SQLite driver can be imported"""
        if importlib.util.find_spec("quadkit.sql.backends.sqlite") is None:
            pytest.skip("aiosqlite not available")


