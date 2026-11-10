"""Unit tests for workflow providers and module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.workflow import SagaStoreProtocol, StateMachineProtocol, StatePersistenceProtocol
from quadkit.workflow.config import BulkOperationConfig, GraphConfig
from quadkit.workflow.di.provider import WorkflowProvider
from quadkit.workflow.module import WorkflowModule
from quadkit.di.module import DynamicModule


class TestWorkflowProviderStateMachine:
    def test_state_machine_defaults_to_none(self):
        provider = WorkflowProvider()
        assert provider._state_machine is None

    def test_state_machine_is_stored(self):
        sm = MagicMock(spec=StateMachineProtocol)
        provider = WorkflowProvider(state_machine=sm)
        assert provider._state_machine is sm


class TestWorkflowProviderDbProvider:
    def test_db_provider_defaults_to_none(self):
        provider = WorkflowProvider()
        assert provider._db_provider is None

    def test_db_provider_is_stored(self):
        db = MagicMock()
        provider = WorkflowProvider(db_provider=db)
        assert provider._db_provider is db

    def test_state_table_defaults_to_expected(self):
        provider = WorkflowProvider()
        assert provider._state_table == "workflow_state_transitions"

    def test_state_table_is_customizable(self):
        provider = WorkflowProvider(state_table="custom_table")
        assert provider._state_table == "custom_table"


class TestWorkflowProviderGraphConfig:
    @pytest.mark.asyncio
    async def test_registers_graph_config(self):
        provider = WorkflowProvider()
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        types = [call.args[0] for call in container.singleton.call_args_list]
        assert GraphConfig in types


class TestWorkflowProviderStateMachineRegistration:
    @pytest.mark.asyncio
    async def test_state_machine_not_registered_when_none(self):
        provider = WorkflowProvider()
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        types = [str(t) for call in container.singleton.call_args_list for t in call.args]
        assert "StateMachineProtocol" not in types

    @pytest.mark.asyncio
    async def test_state_machine_registered_when_provided(self):
        sm = MagicMock(spec=StateMachineProtocol)
        provider = WorkflowProvider(state_machine=sm)
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        bound_types = [
            str(call.args[0])
            for call in container.singleton.call_args_list
        ]
        assert any("StateMachineProtocol" in t for t in bound_types)


class TestWorkflowProviderStatePersistence:
    @pytest.mark.asyncio
    async def test_state_persistence_not_registered_when_no_db(self):
        provider = WorkflowProvider()
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        types = [str(t) for call in container.singleton.call_args_list for t in call.args]
        assert "StatePersistenceProtocol" not in types

    @pytest.mark.asyncio
    async def test_state_persistence_registered_when_db_provided(self):
        db = MagicMock()
        provider = WorkflowProvider(db_provider=db, state_table="my_table")
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        bound_types = [
            str(call.args[0])
            for call in container.singleton.call_args_list
        ]
        assert any("StatePersistenceProtocol" in t for t in bound_types)


class TestWorkflowProviderFromConfig:
    def test_from_config_returns_provider_with_config(self):
        config = BulkOperationConfig(batch_size=50)
        provider = WorkflowProvider.from_config(config)

        assert isinstance(provider, WorkflowProvider)
        assert provider._bulk_config.batch_size == 50


class TestWorkflowProviderShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_logs_message(self):
        provider = WorkflowProvider()
        await provider.shutdown()


class TestWorkflowProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self):
        provider = WorkflowProvider()
        result = await provider.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.component == "workflow"
        assert "pipeline" in result.details["components"]
        assert result.details["components"]["pipeline"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_includes_saga_store_when_configured(self):
        store = MagicMock(spec=SagaStoreProtocol)
        provider = WorkflowProvider(saga_store=store)
        result = await provider.health_check()

        assert "saga_store" in result.details["components"]
        assert result.details["components"]["saga_store"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_includes_state_machine_when_configured(self):
        sm = MagicMock(spec=StateMachineProtocol)
        provider = WorkflowProvider(state_machine=sm)
        result = await provider.health_check()

        assert "state_machine" in result.details["components"]
        assert result.details["components"]["state_machine"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_includes_state_persistence_when_db_configured(self):
        db = MagicMock()
        provider = WorkflowProvider(db_provider=db, state_table="test_state")
        result = await provider.health_check()

        assert "state_persistence" in result.details["components"]
        assert result.details["components"]["state_persistence"]["table"] == "test_state"

    @pytest.mark.asyncio
    async def test_health_check_returns_duration(self):
        provider = WorkflowProvider()
        result = await provider.health_check()

        assert result.duration_ms >= 0


class TestWorkflowModuleStub:
    def test_stub_returns_dynamic_module(self):
        result = WorkflowModule.stub()
        assert isinstance(result, DynamicModule)

    def test_stub_module_is_workflow_module(self):
        result = WorkflowModule.stub()
        assert result.module is WorkflowModule

    def test_stub_exports_pipeline_protocol(self):
        from quadkit.contracts.workflow import PipelineProtocol

        result = WorkflowModule.stub()
        assert PipelineProtocol in result.exports

    def test_stub_has_workflow_provider(self):
        result = WorkflowModule.stub()
        assert len(result.providers) == 1
        provider = result.providers[0]
        assert isinstance(provider, WorkflowProvider)