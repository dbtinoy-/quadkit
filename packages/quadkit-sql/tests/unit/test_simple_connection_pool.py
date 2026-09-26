"""SimpleConnectionPool tests."""

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




class TestSimpleConnectionPool:
    """Test SimpleConnectionPool functionality"""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock database provider"""
        provider = MagicMock(spec=ConnectionPoolProtocol)
        provider.is_connected = AsyncMock(return_value=True)
        return provider

    def test_init(self, mock_provider):
        """Test SimpleConnectionPool initialization"""
        pool = SimpleConnectionPool(
            provider=mock_provider, min_connections=2, max_connections=20,
        )

        assert pool.provider == mock_provider
        assert pool.min_connections == 2
        assert pool.max_connections == 20

    @pytest.mark.asyncio
    async def test_create_connection(self, mock_provider):
        """Test _create_connection returns provider"""
        pool = SimpleConnectionPool(provider=mock_provider)

        conn = await pool._create_connection()

        assert conn == mock_provider

    @pytest.mark.asyncio
    async def test_close_connection(self, mock_provider):
        """Test _close_connection does nothing for providers"""
        pool = SimpleConnectionPool(provider=mock_provider)

        # Should not raise any exception
        await pool._close_connection(mock_provider)

    @pytest.mark.asyncio
    async def test_validate_connection_with_is_connected(self, mock_provider):
        """Test _validate_connection uses provider.is_connected()"""
        pool = SimpleConnectionPool(provider=mock_provider)

        mock_provider.is_connected.return_value = True
        result = await pool._validate_connection(mock_provider)
        assert result is True

        mock_provider.is_connected.return_value = False
        result = await pool._validate_connection(mock_provider)
        assert result is False

        mock_provider.is_connected.assert_called()

    @pytest.mark.asyncio
    async def test_validate_connection_without_is_connected(self):
        """Test _validate_connection defaults to True when no validation methods present"""
        provider_without_validation = MagicMock()
        del provider_without_validation.is_connected  # Remove is_connected
        del provider_without_validation.execute  # Remove execute (no SQL ping)

        pool = SimpleConnectionPool(provider=provider_without_validation)

        result = await pool._validate_connection(provider_without_validation)
        assert result is True

    @pytest.mark.asyncio
    async def test_full_integration(self, mock_provider):
        """Test full integration of SimpleConnectionPool"""
        pool = SimpleConnectionPool(
            provider=mock_provider, min_connections=1, max_connections=3,
        )

        # Initialize
        await pool.initialize()
        assert pool._total_connections == 1

        # Get connection
        async with pool.get_connection() as conn:
            assert conn == mock_provider
            assert pool._active_connections == 1

        # Check stats
        stats = await pool.get_pool_stats()
        assert stats["total_connections"] == 1
        assert stats["active_connections"] == 0
        assert stats["pool_size"] == 1

        # Health check
        health = await pool.health_check()
        assert health.status == HealthStatus.HEALTHY

        # Shutdown
        await pool.shutdown()
        assert pool._shutdown is True
        assert pool._total_connections == 0

    @pytest.mark.asyncio
    async def test_create_connection_with_proxy(self, mock_provider):
        """Test _create_connection returns proxy when enabled"""
        pool = SimpleConnectionPool(provider=mock_provider, use_provider_proxy=True)

        conn = await pool._create_connection()

        assert isinstance(conn, _ProviderConnection)
        assert conn._provider is mock_provider


