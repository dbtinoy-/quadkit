"""Unit of Work commit, rollback and context-manager tests."""

from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.contracts import DatabaseProviderProtocol
from quadkit.sql.exceptions import DatabaseError
from quadkit.sql.unit_of_work.simple import (
    EntityOperation,
    SimpleUnitOfWork,
)


class MockEntity:
    """Mock entity for testing."""

    def __init__(self, id=None, name=None, value=None):
        self.id = id
        self.name = name
        self.value = value
        self.__table_name__ = "mock_entities"


class TestEntityOperation:
    """Test EntityOperation dataclass."""

    def test_entity_operation_creation(self):
        entity = MockEntity(id=1, name="test")
        operation = EntityOperation(
            entity=entity,
            operation_type="insert",
            table_name="test_table",
            primary_key="id",
        )

        assert operation.entity == entity
        assert operation.operation_type == "insert"
        assert operation.table_name == "test_table"
        assert operation.primary_key == "id"

    def test_entity_operation_defaults(self):
        entity = MockEntity()
        operation = EntityOperation(
            entity=entity, operation_type="update", table_name="test_table",
        )

        assert operation.primary_key is None


class TestSimpleUnitOfWorkCommitRollback:
    """Test SimpleUnitOfWork commit and rollback lifecycle."""

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

    def test_initialization(self, mock_provider):
        uow = SimpleUnitOfWork(mock_provider)

        assert uow.provider == mock_provider
        assert uow._operations == []
        assert uow._in_transaction is False
        assert uow._committed is False
        assert uow._rolled_back is False

    @pytest.mark.asyncio
    async def test_context_manager_entry(self, unit_of_work, mock_provider):
        async with unit_of_work as uow:
            assert uow is unit_of_work
            assert unit_of_work._in_transaction is True
            mock_provider.begin_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_exit_success(self, unit_of_work, mock_provider):
        async with unit_of_work:
            pass

        mock_provider.begin_transaction.assert_called_once()
        mock_provider.commit_transaction.assert_called_once()
        assert unit_of_work._committed is True

    @pytest.mark.asyncio
    async def test_context_manager_exit_exception(self, unit_of_work, mock_provider):
        with pytest.raises(ValueError):
            async with unit_of_work:
                raise ValueError("Test exception")

        mock_provider.begin_transaction.assert_called_once()
        mock_provider.rollback_transaction.assert_called_once()
        assert unit_of_work._rolled_back is True

    @pytest.mark.asyncio
    async def test_commit_success(self, unit_of_work, mock_provider):
        entity = MockEntity(id=1, name="test")
        unit_of_work.register_new(entity)

        mock_provider.execute_insert.return_value = Mock(success=True)

        async with unit_of_work:
            pass

        assert unit_of_work._committed is True
        assert unit_of_work._operations == []
        mock_provider.execute_insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_failure(self, unit_of_work, mock_provider):
        entity = MockEntity(id=1, name="test")
        unit_of_work.register_new(entity)

        mock_provider.execute_insert.side_effect = DatabaseError("Insert failed")

        with pytest.raises(DatabaseError, match="Insert failed"):
            async with unit_of_work:
                pass

        assert unit_of_work._committed is False
        assert unit_of_work._rolled_back is True
        mock_provider.rollback_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_not_in_transaction(self, unit_of_work):
        with pytest.raises(RuntimeError, match="Not in a transaction"):
            await unit_of_work.commit()

    @pytest.mark.asyncio
    async def test_commit_already_committed(self, unit_of_work, mock_provider):
        async with unit_of_work:
            pass

        assert unit_of_work._committed is True

    @pytest.mark.asyncio
    async def test_rollback_success(self, unit_of_work, mock_provider):
        entity = MockEntity(id=1, name="test")
        unit_of_work.register_new(entity)

        with pytest.raises(ValueError):
            async with unit_of_work:
                raise ValueError("Force rollback")

        assert unit_of_work._rolled_back is True
        assert unit_of_work._operations == []
        mock_provider.rollback_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_not_in_transaction(self, unit_of_work):
        with pytest.raises(RuntimeError, match="Not in a transaction"):
            await unit_of_work.rollback()

    @pytest.mark.asyncio
    async def test_rollback_already_rolled_back(self, unit_of_work, mock_provider):
        with pytest.raises(ValueError):
            async with unit_of_work:
                raise ValueError("Force rollback")

        assert unit_of_work._rolled_back is True

    def test_register_new(self, unit_of_work):
        entity = MockEntity(id=1, name="test")
        unit_of_work.register_new(entity)

        assert len(unit_of_work._operations) == 1
        operation = unit_of_work._operations[0]
        assert operation.entity == entity
        assert operation.operation_type == "insert"
        assert operation.table_name == "mock_entities"

    def test_register_new_custom_table_name(self, unit_of_work):
        entity = MockEntity(id=1, name="test")
        entity.__table_name__ = "custom_table"
        unit_of_work.register_new(entity)

        operation = unit_of_work._operations[0]
        assert operation.table_name == "custom_table"

    def test_register_new_no_table_name(self, unit_of_work):
        entity = MockEntity(id=1, name="test")
        delattr(entity, "__table_name__")
        unit_of_work.register_new(entity)

        operation = unit_of_work._operations[0]
        assert operation.table_name == "mockentity"

    def test_register_dirty(self, unit_of_work):
        entity = MockEntity(id=1, name="updated")
        unit_of_work.register_dirty(entity)

        assert len(unit_of_work._operations) == 1
        operation = unit_of_work._operations[0]
        assert operation.entity == entity
        assert operation.operation_type == "update"
        assert operation.table_name == "mock_entities"

    def test_register_deleted(self, unit_of_work):
        entity = MockEntity(id=1, name="deleted")
        unit_of_work.register_deleted(entity)

        assert len(unit_of_work._operations) == 1
        operation = unit_of_work._operations[0]
        assert operation.entity == entity
        assert operation.operation_type == "delete"
        assert operation.table_name == "mock_entities"

    def test_register_after_commit_raises_error(self, unit_of_work):
        unit_of_work._committed = True
        entity = MockEntity(id=1, name="test")

        with pytest.raises(RuntimeError, match="Unit of work is closed"):
            unit_of_work.register_new(entity)

    def test_register_after_rollback_raises_error(self, unit_of_work):
        unit_of_work._rolled_back = True
        entity = MockEntity(id=1, name="test")

        with pytest.raises(RuntimeError, match="Unit of work is closed"):
            unit_of_work.register_new(entity)

    def test_manual_event_registration_and_collection(self, unit_of_work):
        unit_of_work.register_event("evt1")
        unit_of_work.register_event("evt2")

        collected = unit_of_work.collect_events()
        assert collected == ["evt1", "evt2"]
        assert unit_of_work.collect_events() == []

    def test_entity_event_collection(self, unit_of_work):

        class EventEntity:
            def __init__(self):
                self._events = ["a", "b"]

            def collect_events(self):
                evts = self._events.copy()
                self._events.clear()
                return evts

        entity = EventEntity()
        unit_of_work.register_new(entity)

        assert unit_of_work.collect_events() == ["a", "b"]
        assert entity._events == []

    @pytest.mark.asyncio
    async def test_events_cleared_on_rollback(self, unit_of_work, mock_provider):
        unit_of_work.register_event("fail")
        with pytest.raises(ValueError):
            async with unit_of_work:
                raise ValueError("force")

        assert unit_of_work.collect_events() == []
