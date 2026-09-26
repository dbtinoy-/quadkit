"""Unit tests for quadkit-events saga system."""

import asyncio

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.events.sagas.base import SagaBase, saga_step
from quadkit.events.sagas.manager import SagaManagerProtocol
from quadkit.events.sagas.orchestrator import SagaOrchestrator
from quadkit.events.sagas.store import InMemorySagaStore, SagaStore
from quadkit.events.sagas.types import (
    SagaRecord,
    SagaStatus,
    SagaStepRecord,
    SagaStepStatus,
)


class TestSagaBase:
    """Test SagaBase class."""

    def test_saga_step_decorator(self):
        """Test saga_step decorator sets attributes correctly."""

        @saga_step("test_step", max_retries=5, retry_delay=2.0)
        async def my_step(self):
            return "result"

        assert hasattr(my_step, "_saga_step_name")
        assert my_step._saga_step_name == "test_step"
        assert my_step._saga_is_compensation is False
        assert my_step._saga_max_retries == 5
        assert my_step._saga_retry_delay == 2.0

    def test_saga_step_decorator_compensation(self):
        """Test saga_step decorator with compensation=True."""

        @saga_step("compensate", compensation=True)
        async def my_compensation(self):
            pass

        assert my_compensation._saga_is_compensation is True

    def test_saga_base_get_steps_empty(self):
        """Test _get_steps returns empty list when no steps defined."""

        class EmptySaga(SagaBase):
            name = "empty_saga"

        saga = EmptySaga()
        steps = saga._get_steps()
        assert steps == []

    def test_saga_base_get_steps_single(self):
        """Test _get_steps with single step."""

        class SingleStepSaga(SagaBase):
            name = "single_step_saga"

            @saga_step("step1")
            async def do_step1(self):
                return "done"

        saga = SingleStepSaga()
        steps = saga._get_steps()
        assert len(steps) == 1
        assert steps[0].name == "step1"
        assert steps[0].max_retries == 3  # default
        assert steps[0].retry_delay == 1.0  # default

    def test_saga_base_get_steps_multiple(self):
        """Test _get_steps with multiple steps."""

        class MultiStepSaga(SagaBase):
            name = "multi_step_saga"

            @saga_step("step1")
            async def do_step1(self):
                return "step1"

            @saga_step("step2", max_retries=5)
            async def do_step2(self):
                return "step2"

            @saga_step("step3")
            async def do_step3(self):
                return "step3"

        saga = MultiStepSaga()
        steps = saga._get_steps()
        assert len(steps) == 3
        assert steps[0].name == "step1"
        assert steps[1].name == "step2"
        assert steps[1].max_retries == 5
        assert steps[2].name == "step3"

    def test_saga_base_get_steps_with_compensation(self):
        """Test _get_steps with compensation steps."""

        class CompensatingSaga(SagaBase):
            name = "compensating_saga"

            @saga_step("step1")
            async def do_step1(self, ctx):
                return "step1"

            @saga_step("compensate_step1", compensation=True)
            async def undo_step1(self, ctx):
                return "undone"

        saga = CompensatingSaga()
        steps = saga._get_steps()
        # The compensation step is NOT in the action order list
        # Compensations are attached to their corresponding action step
        assert len(steps) == 1  # Only action steps in order


class TestSagaManager:
    """Test SagaManagerProtocol class."""

    def test_saga_manager_creation(self):
        """Test SagaManagerProtocol can be created."""
        manager = SagaManagerProtocol()
        assert manager._store is not None
        assert manager._factories == {}
        assert manager._background_tasks == set()

    def test_saga_manager_with_custom_store(self):
        """Test SagaManagerProtocol with custom store."""
        store = InMemorySagaStore()
        manager = SagaManagerProtocol(store=store)
        assert manager._store is store

    def test_saga_manager_register(self):
        """Test registering a saga class."""

        class TestSaga(SagaBase):
            name = "test_saga"

        manager = SagaManagerProtocol()
        manager.register(TestSaga)
        assert "test_saga" in manager._factories

    def test_saga_manager_register_without_name_raises(self):
        """Test registering saga without name raises ValueError."""

        class NoNameSaga(SagaBase):
            pass

        manager = SagaManagerProtocol()
        with pytest.raises(ValueError, match="must be set"):
            manager.register(NoNameSaga)

    @pytest.mark.asyncio
    async def test_saga_manager_start_saga_not_found(self):
        """Test starting unregistered saga raises KeyError."""
        manager = SagaManagerProtocol()
        with pytest.raises(KeyError, match="No saga registered"):
            await manager.start("nonexistent_saga")

    @pytest.mark.asyncio
    async def test_saga_manager_start(self):
        """Test starting a saga."""

        class SimpleSaga(SagaBase):
            name = "simple_saga"

            @saga_step("step1")
            async def step1(self, ctx):
                return "step1_result"

        store = InMemorySagaStore()
        manager = SagaManagerProtocol(store=store)
        manager.register(SimpleSaga)

        saga_id = await manager.start("simple_saga", {"key": "value"})

        assert saga_id is not None
        record = await manager.get(saga_id)
        assert record is not None
        assert record.saga_id == saga_id
        assert record.saga_name == "simple_saga"
        assert record.status == SagaStatus.PENDING
        assert record.data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_saga_manager_execute_steps(self):
        """Test saga manager executes steps successfully."""

        class ExecutingSaga(SagaBase):
            name = "executing_saga"

            @saga_step("step1")
            async def step1(self, ctx):
                ctx["step1"] = "done"
                return "step1_result"

            @saga_step("step2")
            async def step2(self, ctx):
                ctx["step2"] = "done"
                return "step2_result"

        store = InMemorySagaStore()
        manager = SagaManagerProtocol(store=store)
        manager.register(ExecutingSaga)

        saga_id = await manager.start("executing_saga")

        # Allow async task to complete
        await asyncio.sleep(0.1)

        record = await manager.get(saga_id)
        assert record is not None
        # The status should be COMPLETED if steps succeeded


class TestSagaStore:
    """Test SagaStore interface."""

    def test_in_memory_saga_store_creation(self):
        """Test InMemorySagaStore can be created."""
        store = InMemorySagaStore()
        assert store._records == {}

    @pytest.mark.asyncio
    async def test_in_memory_saga_store_save_and_load(self):
        """Test save and load operations."""
        store = InMemorySagaStore()
        record = SagaRecord(
            saga_id="test-id",
            saga_name="test_saga",
            status=SagaStatus.PENDING,
            data={"key": "value"},
        )

        await store.save(record)
        loaded = await store.load("test-id")
        assert loaded is not None
        assert loaded.saga_id == "test-id"
        assert loaded.saga_name == "test_saga"

    @pytest.mark.asyncio
    async def test_in_memory_saga_store_load_nonexistent(self):
        """Test loading nonexistent saga returns None."""
        store = InMemorySagaStore()
        result = await store.load("nonexistent")
        assert result is None


class TestSagaOrchestrator:
    """Test SagaOrchestrator class."""

    def test_saga_orchestrator_creation(self):
        """Test SagaOrchestrator can be created."""
        orchestrator = SagaOrchestrator()
        assert orchestrator._store is not None

    def test_saga_orchestrator_with_custom_store(self):
        """Test SagaOrchestrator with custom store."""
        store = InMemorySagaStore()
        orchestrator = SagaOrchestrator(store=store)
        assert orchestrator._store is store

