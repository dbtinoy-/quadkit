"""Unit tests for connection pool implementations"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.core import HealthCheckResult
from quadkit.sql.pool import ConnectionPoolProtocol, ReplicaPool


class TestReplicaPool:
    """Test ReplicaPool functionality"""

    @pytest.fixture
    def mock_connection_pool(self):
        """Create a mock connection pool"""

        class MockPool:
            def __init__(self, name):
                self.name = name
                self.connections_used = []

            @asynccontextmanager
            async def get_connection(self):
                conn = MagicMock()
                conn.pool_name = self.name
                self.connections_used.append(conn)
                try:
                    yield conn
                finally:
                    pass

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            async def health_check(self):
                return HealthCheckResult(
                    component=self.name,
                    status=HealthStatus.HEALTHY,
                    details={"message": f"{self.name} OK"},
                )

        return MockPool

    def test_init_primary_only(self, mock_connection_pool):
        """Test initialization with primary pool only"""
        primary = mock_connection_pool("primary")
        pool = ReplicaPool(primary)

        assert pool.primary_pool == primary
        assert pool.replica_pools == []
        assert pool._replica_index == 0

    def test_init_with_replicas(self, mock_connection_pool):
        """Test initialization with replica pools"""
        primary = mock_connection_pool("primary")
        replica1 = mock_connection_pool("replica1")
        replica2 = mock_connection_pool("replica2")

        pool = ReplicaPool(primary, [replica1, replica2])

        assert pool.primary_pool == primary
        assert pool.replica_pools == [replica1, replica2]

    @pytest.mark.asyncio
    async def test_read_with_replicas_round_robin(self, mock_connection_pool):
        """Test read operations use replicas in round-robin fashion"""
        primary = mock_connection_pool("primary")
        replica1 = mock_connection_pool("replica1")
        replica2 = mock_connection_pool("replica2")

        pool = ReplicaPool(primary, [replica1, replica2])

        # First read should use replica1
        async with pool.read() as conn:
            assert conn.pool_name == "replica1"

        # Second read should use replica2
        async with pool.read() as conn:
            assert conn.pool_name == "replica2"

        # Third read should cycle back to replica1
        async with pool.read() as conn:
            assert conn.pool_name == "replica1"

    @pytest.mark.asyncio
    async def test_read_without_replicas_uses_primary(self, mock_connection_pool):
        """Test read operations fall back to primary when no replicas"""
        primary = mock_connection_pool("primary")
        pool = ReplicaPool(primary)

        async with pool.read() as conn:
            assert conn.pool_name == "primary"

    @pytest.mark.asyncio
    async def test_write_always_uses_primary(self, mock_connection_pool):
        """Test write operations always use primary pool"""
        primary = mock_connection_pool("primary")
        replica = mock_connection_pool("replica")
        pool = ReplicaPool(primary, [replica])

        async with pool.write() as conn:
            assert conn.pool_name == "primary"

    @pytest.mark.asyncio
    async def test_initialize_all_pools(self, mock_connection_pool):
        """Test initialization of all pools"""
        primary = mock_connection_pool("primary")
        replica1 = mock_connection_pool("replica1")
        replica2 = mock_connection_pool("replica2")

        pool = ReplicaPool(primary, [replica1, replica2])

        # Mock initialize methods
        primary.initialize = AsyncMock()
        replica1.initialize = AsyncMock()
        replica2.initialize = AsyncMock()

        await pool.initialize()

        primary.initialize.assert_called_once()
        replica1.initialize.assert_called_once()
        replica2.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_all_pools(self, mock_connection_pool):
        """Test shutdown of all pools"""
        primary = mock_connection_pool("primary")
        replica1 = mock_connection_pool("replica1")
        replica2 = mock_connection_pool("replica2")

        pool = ReplicaPool(primary, [replica1, replica2])

        # Mock shutdown methods
        primary.shutdown = AsyncMock()
        replica1.shutdown = AsyncMock()
        replica2.shutdown = AsyncMock()

        await pool.shutdown()

        primary.shutdown.assert_called_once()
        replica1.shutdown.assert_called_once()
        replica2.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_all_pools(self, mock_connection_pool):
        """Test health check of all pools"""
        from quadkit.contracts.core import HealthStatus
        from quadkit.contracts.core import HealthCheckResult

        primary = mock_connection_pool("primary")
        replica1 = mock_connection_pool("replica1")
        replica2 = mock_connection_pool("replica2")

        pool = ReplicaPool(primary, [replica1, replica2])

        primary.health_check = AsyncMock(return_value=HealthCheckResult(component="primary", status=HealthStatus.HEALTHY, details={"message": "Primary OK"}))
        replica1.health_check = AsyncMock(return_value=HealthCheckResult(component="replica1", status=HealthStatus.HEALTHY, details={"message": "Replica1 OK"}))
        replica2.health_check = AsyncMock(return_value=HealthCheckResult(component="replica2", status=HealthStatus.UNHEALTHY, details={"message": "Replica2 high load"}))

        health = await pool.health_check()

        assert health.status == HealthStatus.UNHEALTHY
        assert "primary" in health.details
        assert "replicas" in health.details
        assert len(health.details["replicas"]) == 2

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, mock_connection_pool):
        """Test health check when all pools are healthy"""
        from quadkit.contracts.core import HealthStatus

        primary = mock_connection_pool("primary")
        replica = mock_connection_pool("replica")

        pool = ReplicaPool(primary, [replica])

        primary.health_check = AsyncMock(return_value=HealthCheckResult(component="primary", status=HealthStatus.HEALTHY, details={"message": "Primary OK"}))
        replica.health_check = AsyncMock(return_value=HealthCheckResult(component="replica", status=HealthStatus.HEALTHY, details={"message": "Replica OK"}))

        health = await pool.health_check()

        assert health.status == HealthStatus.HEALTHY
        assert health.details["primary"].status == HealthStatus.HEALTHY
        assert health.details["replicas"][0].status == HealthStatus.HEALTHY
