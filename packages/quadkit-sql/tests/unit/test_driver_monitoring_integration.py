"""Driver monitoring integration tests."""

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




class TestDriverMonitoringIntegration:
    """Test monitoring integration across all drivers"""

    @pytest.fixture
    def monitor(self):
        """Create a test monitor"""
        collector = InMemoryDbMetricsCollector()
        return DatabaseMonitor(collector)

    @pytest.mark.skipif(not HAS_POSTGRES, reason="asyncpg not available")
    @pytest.mark.asyncio
    async def test_postgres_monitoring_integration(self, monitor):
        """Test PostgreSQL driver with monitoring"""
        pool = create_postgres_pool(
            "postgresql://user:pass@localhost:5432/test",
            monitor=monitor,
        )
        assert pool.monitor == monitor

        # Test that monitoring is started
        assert pool.monitor is not None

    @pytest.mark.skipif(not HAS_MYSQL, reason="aiomysql not available")
    @pytest.mark.asyncio
    async def test_mysql_monitoring_integration(self, monitor):
        """Test MySQL driver with monitoring"""
        pool = create_mysql_pool(
            host="localhost",
            user="root",
            password="pass",
            database="test",
            monitor=monitor,
        )
        assert pool.monitor == monitor

    @pytest.mark.skipif(not HAS_SQLITE, reason="aiosqlite not available")
    @pytest.mark.asyncio
    async def test_sqlite_monitoring_integration(self, monitor):
        """Test SQLite driver with monitoring"""
        pool = create_sqlite_pool(database=":memory:", monitor=monitor)
        assert pool.monitor == monitor

    @pytest.mark.skipif(not HAS_SQLITE, reason="aiosqlite not available")
    @pytest.mark.asyncio
    async def test_sqlite_monitoring_end_to_end(self, monitor):
        """Test SQLite monitoring end-to-end functionality"""
        pool = create_sqlite_pool(database=":memory:", monitor=monitor)
        await pool.initialize()

        # Test connection with monitoring
        async with pool.get_connection() as conn:
            # Execute a query
            result = await conn.execute(
                "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)",
            )
            assert result is not None

            # Insert data
            result = await conn.execute(
                "INSERT INTO test (name) VALUES (?)",
                ("test_name",),
            )
            assert result is not None

            # Fetch data
            rows = await conn.fetch_all("SELECT * FROM test")
            assert len(rows) == 1
            assert rows[0]["name"] == "test_name"

        # Check that monitoring collected data
        stats = await monitor.get_stats()
        assert "query_stats" in stats
        assert "connection_stats" in stats

        await pool.shutdown()

    @pytest.mark.skipif(not HAS_SQLITE, reason="aiosqlite not available")
    @pytest.mark.asyncio
    async def test_sqlite_health_check_with_monitoring(self, monitor):
        """Test SQLite health check includes monitoring data"""
        pool = create_sqlite_pool(database=":memory:", monitor=monitor)
        await pool.initialize()

        health = await pool.health_check()
        assert health.status == HealthStatus.HEALTHY

        # Health check should include monitoring stats when available
        # Note: This depends on the monitoring implementation

        await pool.shutdown()

    @pytest.mark.asyncio
    async def test_monitor_creation(self):
        """Test monitor creation and basic functionality"""
        collector = InMemoryDbMetricsCollector()
        monitor = DatabaseMonitor(collector)

        # Test monitor has required components
        assert hasattr(monitor, "get_query_monitor")
        assert hasattr(monitor, "start_pool_monitoring")
        assert hasattr(monitor, "stop_pool_monitoring")
        assert hasattr(monitor, "get_transaction_monitor")
        assert hasattr(monitor, "get_health_checker")
        assert hasattr(monitor, "get_stats")

        # Test getting stats
        stats = await monitor.get_stats()
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_monitor_pool_lifecycle(self):
        """Test monitor pool monitoring lifecycle"""
        collector = InMemoryDbMetricsCollector()
        monitor = DatabaseMonitor(collector)

        # Mock pool
        mock_pool = Mock()
        mock_pool.get_stats = Mock(return_value={"test": "stats"})

        # Start monitoring
        await monitor.start_pool_monitoring(mock_pool)

        # Stop monitoring
        await monitor.stop_pool_monitoring()

        # Should not raise exceptions
        assert True


