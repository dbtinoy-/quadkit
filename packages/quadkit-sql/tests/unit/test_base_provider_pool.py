"""Pool lifecycle tests for BaseDatabaseProvider."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from quadkit.contracts.data import (
    ConnectionPoolProtocol,
    QueryLoggerProtocol,
)
from quadkit.contracts.core import HealthStatus
from quadkit.sql.providers.base_provider import DatabaseDriver


class ConcreteDatabaseProvider(DatabaseDriver):
    """Concrete implementation for testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._connections_created = []
        self._connections_closed = []

    async def _create_connection(self):
        conn = Mock()
        self._connections_created.append(conn)
        return conn

    async def _close_connection(self, connection):
        self._connections_closed.append(connection)

    async def _execute_query_raw(
        self, connection, sql: str, params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        if "SELECT 1" in sql:
            return [{"health_check": 1}]
        elif "sqlite_master" in sql:
            return [{"name": "test_table"}]
        elif "PRAGMA table_info" in sql:
            return [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "notnull": 1,
                    "dflt_value": None,
                    "pk": 1,
                },
                {
                    "name": "name",
                    "type": "VARCHAR",
                    "notnull": 0,
                    "dflt_value": None,
                    "pk": 0,
                },
            ]
        return []

    async def _execute_modify_raw(
        self, connection, sql: str, params: list[Any] | None = None,
    ) -> int:
        return 1

    async def _begin_transaction_raw(self, connection, isolation=None):
        pass

    async def _commit_transaction_raw(self, connection):
        pass

    async def _rollback_transaction_raw(self, connection):
        pass

    async def _get_last_insert_id(self, connection, table: str) -> Any | None:
        return 123


class TestBaseDatabaseProviderPoolLifecycle:
    """Test pool lifecycle: init, connect, disconnect, stats."""

    @pytest.fixture
    def mock_connection_pool(self):
        pool = Mock(spec=ConnectionPoolProtocol)
        pool.initialize = AsyncMock()
        pool.shutdown = AsyncMock()
        pool.get_connection = MagicMock()
        pool.get_connection.return_value.__aenter__ = AsyncMock(return_value=Mock())
        pool.get_connection.return_value.__aexit__ = AsyncMock(return_value=None)
        return pool

    @pytest.fixture
    def mock_query_logger(self):
        logger = Mock(spec=QueryLoggerProtocol)
        logger.log_query = AsyncMock()
        return logger

    @pytest.mark.asyncio
    async def test_init_basic_connection_string(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")

        assert provider.connection_manager.connection_string == "sqlite:///test.db"
        assert provider.database_type == "sqlite"
        assert provider.connection_manager.database == "test.db"
        assert provider.connection_manager.host is None
        assert provider.connection_manager.port is None
        assert provider.connection_manager.username is None
        assert provider.connection_manager.password is None
        assert provider.connection_pool is None
        assert provider.query_executor.query_logger is None
        assert await provider.is_connected() is False

    @pytest.mark.asyncio
    async def test_init_complex_connection_string(self):
        provider = ConcreteDatabaseProvider(
            "postgresql://user:pass@localhost:5432/mydb",
        )

        assert provider.database_type == "postgresql"
        assert provider.connection_manager.host == "localhost"
        assert provider.connection_manager.port == 5432
        assert provider.connection_manager.database == "mydb"
        assert provider.connection_manager.username == "user"
        assert provider.connection_manager.password == "pass"

    @pytest.mark.asyncio
    async def test_init_with_connection_pool(self, mock_connection_pool):
        provider = ConcreteDatabaseProvider(
            "sqlite:///test.db", connection_pool=mock_connection_pool,
        )

        assert provider.connection_pool == mock_connection_pool

    @pytest.mark.asyncio
    async def test_init_with_query_logger(self, mock_query_logger):
        provider = ConcreteDatabaseProvider(
            "sqlite:///test.db", query_logger=mock_query_logger,
        )

        assert provider.query_executor.query_logger == mock_query_logger

    @pytest.mark.asyncio
    async def test_connect_without_pool(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")

        await provider.connect()

        assert await provider.is_connected() is True
        assert len(provider._connections_created) == 1

    @pytest.mark.asyncio
    async def test_connect_with_pool(self, mock_connection_pool):
        provider = ConcreteDatabaseProvider(
            "sqlite:///test.db", connection_pool=mock_connection_pool,
        )

        await provider.connect()

        mock_connection_pool.initialize.assert_called_once()
        assert await provider.is_connected() is True

    @pytest.mark.asyncio
    async def test_disconnect_without_pool(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        await provider.disconnect()

        assert await provider.is_connected() is False
        assert len(provider._connections_closed) == 1

    @pytest.mark.asyncio
    async def test_disconnect_with_pool(self, mock_connection_pool):
        provider = ConcreteDatabaseProvider(
            "sqlite:///test.db", connection_pool=mock_connection_pool,
        )
        await provider.connect()

        await provider.disconnect()

        mock_connection_pool.shutdown.assert_called_once()
        assert await provider.is_connected() is False

    @pytest.mark.asyncio
    async def test_is_connected(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")

        assert await provider.is_connected() is False

        await provider.connect()
        assert await provider.is_connected() is True

        await provider.disconnect()
        assert await provider.is_connected() is False

    @pytest.mark.asyncio
    async def test_get_stats(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")

        stats = await provider.get_stats()

        assert stats["database_type"] == "sqlite"
        assert stats["connected"] is False
        assert stats["connection_pool"] is False
        assert stats["query_logger"] is False

        mock_pool = Mock()
        mock_pool.initialize = AsyncMock()
        mock_pool.shutdown = AsyncMock()
        mock_pool.get_connection = MagicMock()
        mock_pool.get_connection.return_value.__aenter__ = AsyncMock(return_value=Mock())
        mock_pool.get_connection.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_logger = Mock()
        provider = ConcreteDatabaseProvider(
            "sqlite:///test.db", connection_pool=mock_pool, query_logger=mock_logger,
        )
        await provider.connect()

        stats = await provider.get_stats()

        assert stats["connected"] is True
        assert stats["connection_pool"] is True
        assert stats["query_logger"] is True

    @pytest.mark.asyncio
    async def test_connection_pool_context_manager(self, mock_connection_pool):
        provider = ConcreteDatabaseProvider(
            "sqlite:///test.db", connection_pool=mock_connection_pool,
        )
        await provider.connect()

        mock_conn = Mock()
        mock_connection_pool.get_connection.return_value.__aenter__.return_value = (
            mock_conn
        )

        mock_connection_pool.get_connection.assert_called_once()
        mock_connection_pool.get_connection.return_value.__aenter__.assert_called_once()
        mock_connection_pool.get_connection.return_value.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_connection_context_manager(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        assert len(provider._connections_created) == 1

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        health = await provider.health_check()

        assert health.status == HealthStatus.HEALTHY
        assert "message" in health.details
        assert health.details["message"] == "Database connection successful"
        assert health.duration_ms is not None
        assert health.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        original_execute_query_raw = provider._execute_query_raw

        async def failing_query(*args, **kwargs):
            raise RuntimeError("Connection failed")

        provider._execute_query_raw = failing_query

        health = await provider.health_check()

        assert health.status == HealthStatus.UNHEALTHY
        assert "Database connection failed: Connection failed" in health.error
        assert health.details["database_type"] == "sqlite"

        provider._execute_query_raw = original_execute_query_raw
