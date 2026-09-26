"""Replica pool tests."""

"""
Unit tests for connection pool implementations

Tests AbstractConnectionPool and SimpleConnectionPool functionality.
"""

import asyncio
from contextlib import asynccontextmanager
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.core import HealthCheckResult

from quadkit.contracts.data import (
    ConnectionPoolProtocol,
)
from quadkit.sql.pool.connection import (
    AbstractConnectionPool,
    SimpleConnectionPool,
    _ProviderConnection,
)




class TestReplicaPool:
    """Test ReplicaPool functionality"""

    @pytest.fixture
    def mock_connection_pool(self):
        """Create a mock connection pool for testing ReplicaPool"""

        class MockConnectionPool(AbstractConnectionPool):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.connections_used = []

            async def _create_connection(self) -> Any:
                conn = MagicMock()
                return conn

            async def _close_connection(self, connection: Any) -> None:
                pass

            async def _validate_connection(self, connection: Any) -> bool:
                return True

        return MockConnectionPool

    def test_init_with_primary_only(self, mock_connection_pool):
        """Test initialization with primary pool only"""
        from quadkit.sql.pool import ReplicaPool

        primary = mock_connection_pool()
        pool = ReplicaPool(primary)

        assert pool.primary_pool is primary
        assert pool.replica_pools == []
        assert pool._replica_index == 0

    def test_init_with_replicas(self, mock_connection_pool):
        """Test initialization with replica pools"""
        from quadkit.sql.pool import ReplicaPool

        primary = mock_connection_pool()
        replica1 = mock_connection_pool()
        replica2 = mock_connection_pool()

        pool = ReplicaPool(primary, [replica1, replica2])

        assert pool.primary_pool is primary
        assert pool.replica_pools == [replica1, replica2]

    @pytest.mark.asyncio
    async def test_read_with_replicas(self):
        """Test read operations use replicas"""
        from unittest.mock import MagicMock

        from quadkit.sql.pool import ReplicaPool

        # Create mock pools that return context managers
        class MockPool:
            def __init__(self, name):
                self.name = name
                self.connections_used = []

            @asynccontextmanager
            async def get_connection(self):
                conn = MagicMock()
                conn.name = self.name
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
                return {"status": "healthy"}

        primary = MockPool("primary")
        replica1 = MockPool("replica1")
        replica2 = MockPool("replica2")

        pool = ReplicaPool(primary, [replica1, replica2])

        # First read should use replica1
        async with pool.read() as conn:
            assert conn.name == "replica1"

        # Second read should use replica2
        async with pool.read() as conn:
            assert conn.name == "replica2"

        # Third read should cycle back to replica1
        async with pool.read() as conn:
            assert conn.name == "replica1"

    @pytest.mark.asyncio
    async def test_read_without_replicas_uses_primary(self):
        """Test read operations fall back to primary when no replicas"""
        from unittest.mock import MagicMock

        from quadkit.sql.pool import ReplicaPool

        # Create mock pool that returns context manager
        class MockPool:
            def __init__(self, name):
                self.name = name

            @asynccontextmanager
            async def get_connection(self):
                conn = MagicMock()
                conn.name = self.name
                try:
                    yield conn
                finally:
                    pass

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            async def health_check(self):
                return {"status": "healthy"}

        primary = MockPool("primary")
        pool = ReplicaPool(primary)

        async with pool.read() as conn:
            assert conn.name == "primary"

    @pytest.mark.asyncio
    async def test_write_always_uses_primary(self):
        """Test write operations always use primary"""
        from unittest.mock import MagicMock

        from quadkit.sql.pool import ReplicaPool

        # Create mock pools that return context managers
        class MockPool:
            def __init__(self, name):
                self.name = name

            @asynccontextmanager
            async def get_connection(self):
                conn = MagicMock()
                conn.name = self.name
                try:
                    yield conn
                finally:
                    pass

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            async def health_check(self):
                return {"status": "healthy"}

        primary = MockPool("primary")
        replica = MockPool("replica")
        pool = ReplicaPool(primary, [replica])

        async with pool.write() as conn:
            assert conn.name == "primary"

    @pytest.mark.asyncio
    async def test_initialize_all_pools(self, mock_connection_pool):
        """Test initialization of all pools"""
        from quadkit.sql.pool import ReplicaPool

        primary = mock_connection_pool()
        replica1 = mock_connection_pool()
        replica2 = mock_connection_pool()

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
        from quadkit.sql.pool import ReplicaPool

        primary = mock_connection_pool()
        replica1 = mock_connection_pool()
        replica2 = mock_connection_pool()

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
        from quadkit.sql.pool import ReplicaPool

        primary = mock_connection_pool()
        replica1 = mock_connection_pool()
        replica2 = mock_connection_pool()

        pool = ReplicaPool(primary, [replica1, replica2])

        # Mock health check methods (legacy dict responses are normalized)
        primary.health_check = AsyncMock(return_value=HealthCheckResult(component="primary", status=HealthStatus.HEALTHY, details={"message": "OK"}))
        replica1.health_check = AsyncMock(return_value=HealthCheckResult(component="replica1", status=HealthStatus.HEALTHY, details={"message": "OK"}))
        replica2.health_check = AsyncMock(return_value=HealthCheckResult(component="replica2", status=HealthStatus.UNHEALTHY, error="High load"))

        health = await pool.health_check()

        assert health.status == HealthStatus.UNHEALTHY  # Because one replica has warning
        assert "primary" in health.details
        assert "replicas" in health.details
        assert len(health.details["replicas"]) == 2
