"""Unit tests for DatabaseHealthChecker."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None  # type: ignore[assignment]
from quadkit.sql.monitoring.database_monitor import (
    ConnectionPoolMonitor,
    DatabaseHealthChecker,
    DatabaseMonitor,
    QueryMonitor,
    TransactionMonitor,
)
from quadkit.sql.monitoring.metrics import (
    HealthStatus,
    InMemoryDbMetricsCollector,
    QueryMetrics,
    TransactionMetrics,
)


@pytest.fixture(autouse=True)
def mock_db_logger():
    """Patch the db.monitor logger to use a standard library logger so caplog works."""
    with patch("quadkit.sql.monitoring.database_monitor.health.logger") as mock_log:
        yield mock_log


class TestHealthChecker:
    """Test DatabaseHealthChecker functionality"""

    @pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def collector(self):
        """Create a test metrics collector"""
        return InMemoryDbMetricsCollector()

    @pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def checker(self, collector):
        """Create a DatabaseHealthChecker instance"""
        return DatabaseHealthChecker(collector)

    @pytest.mark.asyncio
    async def test_init(self, collector):
        """Test DatabaseHealthChecker initialization"""
        checker = DatabaseHealthChecker(collector)
        assert checker.collector == collector

    @pytest.mark.asyncio
    async def test_check_database_health_success(self, checker):
        """Test successful database health check"""
        # Mock a successful database connection
        with patch("sqlalchemy.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = [1]
            mock_conn.execute.return_value = mock_result
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)

            mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
                return_value=mock_conn,
            )
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(
                return_value=None,
            )
            mock_engine.return_value.dispose = MagicMock()

            result = await checker.check_database_health("sqlite:///test.db")

            assert result.status == "healthy"
            assert "successful" in result.message
            assert result.component == "database"

    @pytest.mark.asyncio
    async def test_check_database_health_failure(self, checker):
        """Test failed database health check"""
        with patch("sqlalchemy.create_engine") as mock_engine:
            mock_engine.side_effect = RuntimeError("Connection failed")

            result = await checker.check_database_health("invalid://connection")

            assert result.status == "critical"
            assert "failed" in result.message

    @pytest.mark.asyncio
    async def test_check_connection_pool_health(self, checker):
        """Test connection pool health check"""
        # Mock a connection pool
        pool = MagicMock()
        pool._active_connections = 8
        pool._total_connections = 10

        result = await checker.check_connection_pool_health(pool)

        assert result.status == "healthy"
        assert "healthy" in result.message
        assert result.details["utilization"] == 0.8

    @pytest.mark.asyncio
    async def test_check_connection_pool_health_overutilized(self, checker):
        """Test overutilized connection pool health check"""
        pool = MagicMock()
        pool._active_connections = 9
        pool._total_connections = 10

        result = await checker.check_connection_pool_health(pool)

        assert result.status == "warning"
        assert "highly utilized" in result.message

    @pytest.mark.asyncio
    async def test_check_database_health_timeout(self, checker):
        """Test database health check timeout"""
        with patch("sqlalchemy.create_engine") as mock_engine:
            # Mock timeout
            mock_engine.side_effect = TimeoutError()

            result = await checker.check_database_health(
                "timeout://connection",
                timeout=0.1,
            )

            assert result.status == "critical"
            assert "timeout" in result.message

    @pytest.mark.asyncio
    async def test_check_database_health_query_failure(self, checker):
        """Test database health check where query returns unexpected result"""
        with patch("sqlalchemy.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = [0]  # Not 1
            mock_conn.execute.return_value = mock_result
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)

            mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
                return_value=mock_conn,
            )
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(
                return_value=None,
            )
            mock_engine.return_value.dispose = MagicMock()

            result = await checker.check_database_health("sqlite:///test.db")

            assert result.status == "critical"
            assert "failed" in result.message

    @pytest.mark.asyncio
    async def test_check_database_health_with_sqlite_file(self, checker, tmp_path):
        """Integration-like unit test: real SQLite file should return healthy"""
        # Use an in-memory SQLite DB for a deterministic unit check
        conn_str = "sqlite:///:memory:"

        result = await checker.check_database_health(conn_str, timeout=1.0)
        assert result.status == "healthy", (
            f"status={result.status}, message={result.message}"
        )
        assert "successful" in result.message

    @pytest.mark.asyncio
    async def test_check_connection_pool_health_critical_utilization(self, checker):
        """Test connection pool health with critical utilization"""
        pool = MagicMock()
        pool._active_connections = 96
        pool._total_connections = 100

        result = await checker.check_connection_pool_health(pool)

        assert result.status == "critical"
        assert "critically overutilized" in result.message

    @pytest.mark.asyncio
    async def test_check_connection_pool_health_exception(self, checker):
        """Test connection pool health check with exception"""
        pool = MagicMock()
        pool._active_connections = MagicMock(
            side_effect=AttributeError("No such attribute"),
        )

        result = await checker.check_connection_pool_health(pool)

        assert result.status == "critical"
        assert "failed" in result.message
        assert "error" in result.details

    @pytest.mark.asyncio
    async def test_check_performance_health_critical_query_time(
        self,
        checker,
        collector,
    ):
        """Test performance health with critical query time"""
        # Add slow query metrics
        await collector.record_query_metrics(
            QueryMetrics(
                query="SELECT * FROM slow_table",
                parameters=None,
                execution_time=3.0,  # Above critical threshold (2.0)
                timestamp=datetime.now(UTC),
                success=True,
            ),
        )

        results = await checker.check_performance_health()

        query_check = next(
            (r for r in results if r.component == "query_performance"),
            None,
        )
        assert query_check is not None
        assert query_check.status == "critical"
        assert "critically high" in query_check.message

    @pytest.mark.asyncio
    async def test_check_performance_health_warning_query_time(
        self,
        checker,
        collector,
    ):
        """Test performance health with warning query time"""
        # Add moderately slow query
        await collector.record_query_metrics(
            QueryMetrics(
                query="SELECT * FROM medium_table",
                parameters=None,
                execution_time=0.8,  # Above warning threshold (0.5) but below critical (2.0)
                timestamp=datetime.now(UTC),
                success=True,
            ),
        )

        results = await checker.check_performance_health()

        query_check = next(
            (r for r in results if r.component == "query_performance"),
            None,
        )
        assert query_check is not None
        assert query_check.status == "warning"
        assert "elevated" in query_check.message

    @pytest.mark.asyncio
    async def test_check_performance_health_critical_commit_ratio(
        self,
        checker,
        collector,
    ):
        """Test performance health with critical commit ratio"""
        # Add failed transactions
        await collector.record_transaction_metrics(
            TransactionMetrics(
                transaction_id="tx1",
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
                duration=0.1,
                operation="rollback",
                success=False,
                deadlock_detected=False,
            ),
        )

        results = await checker.check_performance_health()

        tx_check = next(
            (r for r in results if r.component == "transaction_performance"),
            None,
        )
        assert tx_check is not None
        assert tx_check.status == "critical"
        assert "critically low" in tx_check.message

    @pytest.mark.asyncio
    async def test_check_performance_health_warning_commit_ratio(
        self,
        checker,
        collector,
    ):
        """Test performance health with warning commit ratio"""
        # Add transactions to get commit ratio between warning and critical thresholds
        # Need commit_ratio >= 0.7 and < 0.85 for warning
        # With 7 commits and 3 rollbacks = 10 total, ratio = 0.7
        for i in range(7):
            await collector.record_transaction_metrics(
                TransactionMetrics(
                    transaction_id=f"tx_commit_{i}",
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    duration=0.1,
                    operation="commit",
                    success=True,
                    deadlock_detected=False,
                ),
            )
        for i in range(3):
            await collector.record_transaction_metrics(
                TransactionMetrics(
                    transaction_id=f"tx_rollback_{i}",
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    duration=0.1,
                    operation="rollback",
                    success=False,
                    deadlock_detected=False,
                ),
            )

        results = await checker.check_performance_health()

        tx_check = next(
            (r for r in results if r.component == "transaction_performance"),
            None,
        )
        assert tx_check is not None
        assert tx_check.status == "warning"
        assert "low" in tx_check.message


