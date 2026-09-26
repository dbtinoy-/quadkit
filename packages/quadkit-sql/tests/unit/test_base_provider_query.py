"""Query execution, transaction and table-operation tests for BaseDatabaseProvider."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from quadkit.contracts.data import (
    ConnectionPoolProtocol,
    DeleteResult,
    InsertResult,
    QueryLoggerProtocol,
    QueryResult,
    UpdateResult,
)
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


class TestBaseDatabaseProviderQueryExecution:
    """Test query execution, transactions, table ops and logging."""

    @pytest.fixture
    def mock_query_logger(self):
        logger = Mock(spec=QueryLoggerProtocol)
        logger.log_query = AsyncMock()
        return logger

    @pytest.mark.asyncio
    async def test_execute_query_success(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        result = await provider.execute_query("SELECT * FROM test_table", ["param1"])

        assert isinstance(result, QueryResult)
        assert result.success is True
        assert result.execution_time >= 0
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_execute_query_with_exception(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        original_method = provider._execute_query_raw

        async def failing_query(*args, **kwargs):
            raise RuntimeError("Query failed")

        provider._execute_query_raw = failing_query

        with pytest.raises(RuntimeError, match="Query failed"):
            await provider.execute_query("SELECT * FROM test_table")

        provider._execute_query_raw = original_method

    @pytest.mark.asyncio
    async def test_execute_insert_success(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        result = await provider.execute_insert(
            "test_table", {"name": "test", "value": 42},
        )

        assert isinstance(result, InsertResult)
        assert result.affected_rows == 1
        assert result.inserted_id == 123
        assert result.execution_time >= 0
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_update_success(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        result = await provider.execute_update(
            "test_table", {"name": "updated"}, "id = ?", [1],
        )

        assert isinstance(result, UpdateResult)
        assert result.affected_rows == 1
        assert result.execution_time >= 0
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_delete_success(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        result = await provider.execute_delete("test_table", "id = ?", [1])

        assert isinstance(result, DeleteResult)
        assert result.affected_rows == 1
        assert result.execution_time >= 0
        assert result.success is True

    @pytest.mark.asyncio
    async def test_transaction_context_manager_success(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        async with provider.transaction():
            assert provider.transaction_manager.in_transaction is True
            assert provider.transaction_manager._transaction_connection is not None

        assert provider.transaction_manager.in_transaction is False
        assert provider.transaction_manager._transaction_connection is None

    @pytest.mark.asyncio
    async def test_transaction_context_manager_exception(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        with pytest.raises(ValueError):
            async with provider.transaction():
                assert provider.transaction_manager.in_transaction is True
                raise ValueError("Test exception")

        assert provider.transaction_manager.in_transaction is False
        assert provider.transaction_manager._transaction_connection is None

    @pytest.mark.asyncio
    async def test_nested_transaction(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        async with provider.transaction():
            assert provider.transaction_manager.in_transaction is True

            async with provider.transaction():
                assert provider.transaction_manager.in_transaction is True

            assert provider.transaction_manager.in_transaction is True

        assert provider.transaction_manager.in_transaction is False

    @pytest.mark.asyncio
    async def test_manual_transaction_methods(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")

        await provider.begin_transaction()
        assert provider.transaction_manager.in_transaction is True
        assert provider.transaction_manager._transaction_connection is not None

        await provider.commit_transaction()
        assert provider.transaction_manager.in_transaction is False
        assert provider.transaction_manager._transaction_connection is None

        await provider.begin_transaction()
        await provider.rollback_transaction()
        assert provider.transaction_manager.in_transaction is False
        assert provider.transaction_manager._transaction_connection is None

    @pytest.mark.asyncio
    async def test_table_exists_sqlite_syntax(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        exists = await provider.table_exists("test_table")
        assert exists is True

    @pytest.mark.asyncio
    async def test_table_exists_fallback(self):
        provider = ConcreteDatabaseProvider("postgresql://user:pass@localhost/mydb")
        await provider.connect()

        original_execute_query = provider.execute_query

        async def mock_execute_query(sql, params=None):
            if "SELECT 1 FROM test_table" in sql:
                return QueryResult(
                    rows=[{"col": 1}], row_count=1, execution_time=0.01, success=True,
                )
            return await original_execute_query(sql, params)

        provider.execute_query = mock_execute_query

        exists = await provider.table_exists("test_table")
        assert exists is True

    @pytest.mark.asyncio
    async def test_get_table_columns(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        columns = await provider.get_table_columns("test_table")

        assert len(columns) == 2
        assert columns[0]["name"] == "id"
        assert columns[0]["type"] == "INTEGER"
        assert columns[0]["nullable"] is False
        assert columns[0]["primary_key"] is True
        assert columns[1]["name"] == "name"
        assert columns[1]["type"] == "VARCHAR"
        assert columns[1]["nullable"] is True
        assert columns[1]["primary_key"] is False

    @pytest.mark.asyncio
    async def test_create_table(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        await provider.create_table(
            "test_table",
            {"id": "INTEGER", "name": "VARCHAR(100)", "user_id": "INTEGER"},
        )

        assert True

    @pytest.mark.asyncio
    async def test_drop_table(self):
        provider = ConcreteDatabaseProvider("sqlite:///test.db")
        await provider.connect()

        await provider.drop_table("test_table")

        assert True

    @pytest.mark.asyncio
    async def test_query_logging(self, mock_query_logger):
        provider = ConcreteDatabaseProvider(
            "sqlite:///test.db", query_logger=mock_query_logger,
        )
        await provider.connect()

        await provider.execute_query("SELECT * FROM test_table", ["param"])

        mock_query_logger.log_query.assert_called_once()
        call_args = mock_query_logger.log_query.call_args[0][0]

        assert call_args.sql == "SELECT * FROM test_table"
        assert list(call_args.params) == ["param"]
        assert call_args.success is True
        assert call_args.execution_time >= 0

    @pytest.mark.asyncio
    async def test_query_logging_with_exception(self, mock_query_logger):
        provider = ConcreteDatabaseProvider(
            "sqlite:///test.db", query_logger=mock_query_logger,
        )
        await provider.connect()

        original_method = provider._execute_query_raw

        async def failing_query(*args, **kwargs):
            raise RuntimeError("Query failed")

        provider._execute_query_raw = failing_query

        with pytest.raises(RuntimeError):
            await provider.execute_query("SELECT * FROM test_table")

        mock_query_logger.log_query.assert_called_once()
        call_args = mock_query_logger.log_query.call_args[0][0]

        assert call_args.success is False
        assert "Query failed" in call_args.error_message

        provider._execute_query_raw = original_method
