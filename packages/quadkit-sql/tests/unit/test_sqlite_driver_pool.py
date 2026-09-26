"""SQLite pool lifecycle and close tests."""

from __future__ import annotations

"""Tests for SQLite database driver"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    import aiosqlite

    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False
    aiosqlite = None  # type: ignore[assignment]

from quadkit.contracts import HealthStatus
from quadkit.sql.backends.sqlite import (
    HAS_SQLITE,
    SQLiteConnection,
    SQLiteConnectionPool,
    create_sqlite_pool,
)
from quadkit.sql.exceptions import DatabaseConnectionError, QueryError



@pytest.mark.skipif(not HAS_SQLITE, reason="aiosqlite not available")
class TestSQLiteDriver:
    """Test SQLite driver functionality"""

    @pytest.mark.asyncio
    async def test_sqlite_pool_creation(self):
        """Test SQLite pool creation"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

            pool = SQLiteConnectionPool(":memory:")
            await pool.initialize()

            mock_aiosqlite.connect.assert_called_once()
            call_args = mock_aiosqlite.connect.call_args
            assert call_args[0][0] == ":memory:"

    @pytest.mark.asyncio
    async def test_sqlite_pool_initialization_success(self):
        """Test SQLite pool initialization success"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

            pool = SQLiteConnectionPool("test.db")
            await pool.initialize()

            assert pool._conn is not None
            assert pool._is_healthy is True
            assert pool._total_connections_created == 1

    @pytest.mark.asyncio
    async def test_sqlite_pool_initialization_failure(self):
        """Test SQLite pool initialization failure"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite") as mock_aiosqlite:
            mock_aiosqlite.connect = AsyncMock(
                side_effect=OSError("Connection failed"),
            )

            # Mock retry_call to avoid retries in this test
            with patch(
                "quadkit.sql.backends.sqlite._pool.retry_call", new_callable=AsyncMock
            ) as mock_retry:
                mock_retry.side_effect = OSError("Connection failed")

                pool = SQLiteConnectionPool("test.db")

                with pytest.raises(OSError, match="Connection failed"):
                    await pool.initialize()

            assert pool._conn is None
            assert pool._is_healthy is False

            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

            pool = SQLiteConnectionPool("test.db")
            await pool.initialize()
            await pool.initialize()  # Should not create connection again

            # Should only be called once
            mock_aiosqlite.connect.assert_called_once()


    @pytest.mark.asyncio
    async def test_sqlite_pool_get_connection_error(self):
        """Test SQLite pool get_connection error"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

            pool = SQLiteConnectionPool("test.db")
            await pool.initialize()

            # Mock circuit breaker to fail
            mock_circuit_breaker = Mock()

            class MockAsyncContextManager:
                async def __aenter__(self):
                    raise RuntimeError("Circuit breaker open")

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass

            mock_circuit_breaker.protect = Mock(return_value=MockAsyncContextManager())
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
    async def test_sqlite_pool_close(self):
        """Test SQLite pool close"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

            pool = SQLiteConnectionPool("test.db")
            await pool.initialize()

            await pool.shutdown()

            assert pool._conn is None
            assert pool._is_healthy is False
            mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlite_pool_close_without_initialization(self):
        """Test SQLite pool close without initialization"""
        pool = SQLiteConnectionPool("test.db")

        await pool.shutdown()  # Should not raise any errors

