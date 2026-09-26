"""SQLite connection execution and fetch tests."""

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
    @pytest.fixture
    def mock_monitor(self):
        """Create a mock monitor"""
        monitor = Mock()
        query_monitor = Mock()

        # Create a mock for monitor_query that can track calls
        monitor_query_mock = Mock()

        @asynccontextmanager
        async def monitor_query(*args, **kwargs):
            yield Mock()

        monitor_query_mock.side_effect = monitor_query
        query_monitor.monitor_query = monitor_query_mock
        monitor.get_query_monitor.return_value = query_monitor
        monitor.start_pool_monitoring = AsyncMock()
        monitor.stop_pool_monitoring = AsyncMock()
        monitor.get_stats = AsyncMock(return_value={})
        return monitor


    @pytest.mark.asyncio
    async def test_sqlite_connection_creation(self):
        """Test SQLite connection creation"""
        with patch("quadkit.sql.backends.sqlite._pool.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

            pool = SQLiteConnectionPool("test.db")
            await pool.initialize()

            # Mock circuit breaker as async context manager
            mock_circuit_breaker = Mock()

            @asynccontextmanager
            async def mock_protect():
                yield

            mock_circuit_breaker.protect = Mock(side_effect=mock_protect)
            pool.circuit_breaker = mock_circuit_breaker

            async with pool.get_connection() as conn:
                assert isinstance(conn, SQLiteConnection)
                assert conn._conn == mock_conn
                assert pool._connection_count == 1

    @pytest.mark.asyncio
    async def test_sqlite_connection_execute_select_without_monitoring(self):
        """Test SQLite connection execute SELECT without monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        conn = SQLiteConnection(mock_conn)

        result = await conn.execute("SELECT * FROM test")

        assert result == mock_cursor
        mock_conn.execute.assert_called_once_with("SELECT * FROM test")

    @pytest.mark.asyncio
    async def test_sqlite_connection_execute_insert_without_monitoring(self):
        """Test SQLite connection execute INSERT without monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 1
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        conn = SQLiteConnection(mock_conn)

        result = await conn.execute("INSERT INTO test VALUES (?, ?)", (1, "test"))

        assert result == 1
        mock_conn.execute.assert_called_once_with(
            "INSERT INTO test VALUES (?, ?)",
            (1, "test"),
        )
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlite_connection_execute_with_monitoring(self, mock_monitor):
        """Test SQLite connection execute with monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 1
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        conn = SQLiteConnection(mock_conn, mock_monitor)

        result = await conn.execute("INSERT INTO test VALUES (?, ?)", (1, "test"))

        assert result == 1
        mock_monitor.get_query_monitor.assert_called_once()
        mock_monitor.get_query_monitor().monitor_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlite_connection_execute_error(self):
        """Test SQLite connection execute error"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=aiosqlite.Error("Syntax error"))

        conn = SQLiteConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.execute("INVALID SQL")

        error = exc_info.value
        assert "Query execution failed" in str(error)
        assert error.details["query"] == "INVALID SQL"
        assert "Syntax error" in error.details["error"]

    @pytest.mark.asyncio
    async def test_sqlite_connection_execute_many(self):
        """Test SQLite connection execute_many"""
        mock_conn = AsyncMock()
        mock_conn.executemany = AsyncMock()
        mock_conn.commit = AsyncMock()

        conn = SQLiteConnection(mock_conn)

        params_list = [(1, "test1"), (2, "test2"), (3, "test3")]
        await conn.execute_many("INSERT INTO test VALUES (?, ?)", params_list)

        mock_conn.executemany.assert_called_once_with(
            "INSERT INTO test VALUES (?, ?)",
            params_list,
        )
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlite_connection_execute_many_error(self):
        """Test SQLite connection execute_many error"""
        mock_conn = AsyncMock()
        mock_conn.executemany = AsyncMock(
            side_effect=aiosqlite.Error("Constraint violation")
        )

        conn = SQLiteConnection(mock_conn)

        params_list = [(1, "test1"), (2, "test2")]
        with pytest.raises(QueryError) as exc_info:
            await conn.execute_many("INSERT INTO test VALUES (?, ?)", params_list)

        error = exc_info.value
        assert "Batch execution failed" in str(error)
        assert error.details["query"] == "INSERT INTO test VALUES (?, ?)"
        assert "Constraint violation" in error.details["error"]

    @pytest.mark.asyncio
    async def test_sqlite_connection_fetch_one_without_monitoring(self):
        """Test SQLite connection fetch_one without monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(1, "test"))
        mock_cursor.description = [("id",), ("name",)]
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        conn = SQLiteConnection(mock_conn)

        result = await conn.fetch_one("SELECT * FROM test WHERE id = ?", (1,))

        assert result == {"id": 1, "name": "test"}
        mock_conn.execute.assert_called_once_with(
            "SELECT * FROM test WHERE id = ?",
            (1,),
        )

    @pytest.mark.asyncio
    async def test_sqlite_connection_fetch_one_with_monitoring(self, mock_monitor):
        """Test SQLite connection fetch_one with monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(1, "test"))
        mock_cursor.description = [("id",), ("name",)]
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        conn = SQLiteConnection(mock_conn, mock_monitor)

        result = await conn.fetch_one("SELECT * FROM test WHERE id = ?", (1,))

        assert result == {"id": 1, "name": "test"}
        mock_monitor.get_query_monitor.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlite_connection_fetch_one_none_result(self):
        """Test SQLite connection fetch_one with no results"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.description = [("id",), ("name",)]
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        conn = SQLiteConnection(mock_conn)

        result = await conn.fetch_one("SELECT * FROM test WHERE id = ?", (999,))

        assert result is None

    @pytest.mark.asyncio
    async def test_sqlite_connection_fetch_one_error(self):
        """Test SQLite connection fetch_one error"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(
            side_effect=aiosqlite.Error("Table doesn't exist")
        )

        conn = SQLiteConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.fetch_one("SELECT * FROM nonexistent_table")

        error = exc_info.value
        assert "Query fetch failed" in str(error)
        assert error.details["query"] == "SELECT * FROM nonexistent_table"
        assert "Table doesn't exist" in error.details["error"]

    @pytest.mark.asyncio
    async def test_sqlite_connection_fetch_all_without_monitoring(self):
        """Test SQLite connection fetch_all without monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(
            return_value=[(1, "test1"), (2, "test2"), (3, "test3")],
        )
        mock_cursor.description = [("id",), ("name",)]
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        conn = SQLiteConnection(mock_conn)

        result = await conn.fetch_all("SELECT * FROM test")

        assert len(result) == 3
        assert result[0] == {"id": 1, "name": "test1"}
        assert result[1] == {"id": 2, "name": "test2"}
        assert result[2] == {"id": 3, "name": "test3"}
        mock_conn.execute.assert_called_once_with("SELECT * FROM test")

    @pytest.mark.asyncio
    async def test_sqlite_connection_fetch_all_empty_result(self):
        """Test SQLite connection fetch_all with empty results"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.description = [("id",), ("name",)]
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        conn = SQLiteConnection(mock_conn)

        result = await conn.fetch_all("SELECT * FROM test WHERE id = ?", (999,))

        assert result == []

    @pytest.mark.asyncio
    async def test_sqlite_connection_fetch_all_with_monitoring(self, mock_monitor):
        """Test SQLite connection fetch_all with monitoring"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[(1, "test1"), (2, "test2")])
        mock_cursor.description = [("id",), ("name",)]
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        conn = SQLiteConnection(mock_conn, mock_monitor)

        result = await conn.fetch_all("SELECT * FROM test")

        assert len(result) == 2
        mock_monitor.get_query_monitor.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlite_connection_fetch_all_error(self):
        """Test SQLite connection fetch_all error"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=aiosqlite.Error("Permission denied"))

        conn = SQLiteConnection(mock_conn)

        with pytest.raises(QueryError) as exc_info:
            await conn.fetch_all("SELECT * FROM restricted_table")

        error = exc_info.value
        assert "Query fetch all failed" in str(error)
        assert error.details["query"] == "SELECT * FROM restricted_table"
        assert "Permission denied" in error.details["error"]

    @pytest.mark.asyncio
    async def test_sqlite_connection_close(self):
        """Test SQLite connection close"""
        mock_conn = AsyncMock()
        conn = SQLiteConnection(mock_conn)

        await conn.close()  # Should not raise any errors

