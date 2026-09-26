"""Unit of Work operation execution, nesting and entity-to-dict tests."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.contracts import DatabaseProviderProtocol
from quadkit.sql.unit_of_work.simple import (
    SimpleUnitOfWork,
    unit_of_work,
)


class MockEntity:
    """Mock entity for testing."""

    def __init__(self, id=None, name=None, value=None):
        self.id = id
        self.name = name
        self.value = value
        self.__table_name__ = "mock_entities"


class TestSimpleUnitOfWorkOperations:
    """Test operation execution, nesting and entity_to_dict."""

    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=DatabaseProviderProtocol)
        provider.begin_transaction = AsyncMock()
        provider.commit_transaction = AsyncMock()
        provider.rollback_transaction = AsyncMock()
        provider.execute_insert = AsyncMock()
        provider.execute_update = AsyncMock()
        provider.execute_delete = AsyncMock()
        return provider

    @pytest.fixture
    def unit_of_work(self, mock_provider):
        return SimpleUnitOfWork(mock_provider)

    @pytest.mark.asyncio
    async def test_nested_context_manager(self, unit_of_work, mock_provider):
        async with unit_of_work:
            assert unit_of_work._in_transaction is True

            async with unit_of_work:
                assert unit_of_work._in_transaction is True
                assert mock_provider.begin_transaction.call_count == 1

            assert unit_of_work._in_transaction is True

        assert unit_of_work._in_transaction is True
        assert unit_of_work._committed is True
        mock_provider.begin_transaction.assert_called_once()
        mock_provider.commit_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_insert_operation(self, unit_of_work, mock_provider):
        from quadkit.sql.unit_of_work.simple import EntityOperation

        entity = MockEntity(id=1, name="test", value=42)
        operation = EntityOperation(
            entity=entity, operation_type="insert", table_name="test_table",
        )

        mock_provider.execute_insert.return_value = Mock(success=True)

        await unit_of_work._execute_operation(operation)

        mock_provider.execute_insert.assert_called_once_with(
            table="test_table", data={"id": 1, "name": "test", "value": 42},
        )

    @pytest.mark.asyncio
    async def test_execute_insert_failure(self, unit_of_work, mock_provider):
        from quadkit.sql.unit_of_work.simple import EntityOperation

        entity = MockEntity(id=1, name="test")
        operation = EntityOperation(
            entity=entity, operation_type="insert", table_name="test_table",
        )

        mock_provider.execute_insert.return_value = Mock(
            success=False, error_message="Insert failed",
        )

        with pytest.raises(RuntimeError, match="Insert failed"):
            await unit_of_work._execute_operation(operation)

    @pytest.mark.asyncio
    async def test_execute_update_operation(self, unit_of_work, mock_provider):
        from quadkit.sql.unit_of_work.simple import EntityOperation

        entity = MockEntity(id=1, name="updated", value=100)
        operation = EntityOperation(
            entity=entity, operation_type="update", table_name="test_table",
        )

        mock_provider.execute_update.return_value = Mock(success=True)

        await unit_of_work._execute_operation(operation)

        mock_provider.execute_update.assert_called_once_with(
            table="test_table",
            data={"id": 1, "name": "updated", "value": 100},
            where_clause="id = ?",
            where_params=[1],
        )

    @pytest.mark.asyncio
    async def test_execute_update_no_id(self, unit_of_work, mock_provider):
        from quadkit.sql.unit_of_work.simple import EntityOperation

        entity = MockEntity(name="test")
        operation = EntityOperation(
            entity=entity, operation_type="update", table_name="test_table",
        )

        with pytest.raises(
            ValueError, match="Entity must have an 'id' attribute for updates",
        ):
            await unit_of_work._execute_operation(operation)

    @pytest.mark.asyncio
    async def test_execute_delete_operation(self, unit_of_work, mock_provider):
        from quadkit.sql.unit_of_work.simple import EntityOperation

        entity = MockEntity(id=1, name="deleted")
        operation = EntityOperation(
            entity=entity, operation_type="delete", table_name="test_table",
        )

        mock_provider.execute_delete.return_value = Mock(success=True)

        await unit_of_work._execute_operation(operation)

        mock_provider.execute_delete.assert_called_once_with(
            table="test_table", where_clause="id = ?", where_params=[1],
        )

    @pytest.mark.asyncio
    async def test_execute_delete_no_id(self, unit_of_work, mock_provider):
        from quadkit.sql.unit_of_work.simple import EntityOperation

        entity = MockEntity(name="test")
        operation = EntityOperation(
            entity=entity, operation_type="delete", table_name="test_table",
        )

        with pytest.raises(
            ValueError, match="Entity must have an 'id' attribute for deletes",
        ):
            await unit_of_work._execute_operation(operation)

    @pytest.mark.asyncio
    async def test_execute_unknown_operation(self, unit_of_work):
        from quadkit.sql.unit_of_work.simple import EntityOperation

        entity = MockEntity(id=1, name="test")
        operation = EntityOperation(
            entity=entity, operation_type="unknown", table_name="test_table",
        )

        with pytest.raises(ValueError, match="Unknown operation type: unknown"):
            await unit_of_work._execute_operation(operation)

    def test_entity_to_dict_with_dict(self, unit_of_work):
        entity = {"id": 1, "name": "test"}
        result = unit_of_work._entity_to_dict(entity)

        assert result == {"id": 1, "name": "test"}
        assert result is not entity

    def test_entity_to_dict_with_object(self, unit_of_work):
        entity = MockEntity(id=1, name="test", value=42)
        entity._private = "private"

        result = unit_of_work._entity_to_dict(entity)

        assert result == {"id": 1, "name": "test", "value": 42}
        assert "_private" not in result
        assert "__table_name__" not in result

    def test_entity_to_dict_invalid_type(self, unit_of_work):
        entity = "invalid"

        with pytest.raises(ValueError, match="Cannot convert entity to dict"):
            unit_of_work._entity_to_dict(entity)

    def test_entity_to_dict_with_dataclass(self, unit_of_work):

        @dataclass
        class DEntity:
            id: int
            name: str
            _private: str = "secret"

        entity = DEntity(id=2, name="dc")
        result = unit_of_work._entity_to_dict(entity)
        assert result == {"id": 2, "name": "dc"}
        assert "_private" not in result

    def test_entity_to_dict_with_model_dump(self, unit_of_work):

        class PydanticLike:
            def __init__(self, id, name):
                self.id = id
                self.name = name

            def model_dump(self):
                return {"id": self.id, "name": self.name, "_secret": "x"}

        entity = PydanticLike(3, "pyd")
        result = unit_of_work._entity_to_dict(entity)
        assert result == {"id": 3, "name": "pyd"}
        assert "_secret" not in result


class TestUnitOfWorkContextManager:
    """Test the unit_of_work context manager function."""

    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=DatabaseProviderProtocol)
        provider.begin_transaction = AsyncMock()
        provider.commit_transaction = AsyncMock()
        provider.rollback_transaction = AsyncMock()
        provider.execute_insert = AsyncMock()
        provider.execute_update = AsyncMock()
        provider.execute_delete = AsyncMock()
        return provider

    @pytest.mark.asyncio
    async def test_unit_of_work_context_manager_success(self, mock_provider):
        async with unit_of_work(mock_provider) as uow:
            assert isinstance(uow, SimpleUnitOfWork)
            assert uow.provider == mock_provider
            assert uow._in_transaction is True

        assert uow._committed is True
        mock_provider.begin_transaction.assert_called_once()
        mock_provider.commit_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_unit_of_work_context_manager_exception(self, mock_provider):
        with pytest.raises(ValueError):
            async with unit_of_work(mock_provider) as uow:
                assert uow._in_transaction is True
                raise ValueError("Test exception")

        assert uow._rolled_back is True
        mock_provider.begin_transaction.assert_called_once()
        mock_provider.rollback_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_unit_of_work_context_manager_operations(self, mock_provider):
        entity = MockEntity(id=1, name="test")

        mock_provider.execute_insert.return_value = Mock(success=True)

        async with unit_of_work(mock_provider) as uow:
            uow.register_new(entity)

        assert mock_provider.execute_insert.call_count == 1
        assert uow._committed is True
