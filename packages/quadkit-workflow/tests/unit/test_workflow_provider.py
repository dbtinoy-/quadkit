"""Unit tests for WorkflowProvider DI registration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.workflow.config import BulkOperationConfig
from quadkit.workflow.di import WorkflowProvider
from quadkit.workflow.pipeline import Pipeline


def _mock_container():
    """Build a minimal container mock that records singleton calls."""
    container = MagicMock()
    container.singleton = MagicMock()
    container.resolve = AsyncMock(return_value=BulkOperationConfig())
    return container


class TestWorkflowProviderInit:
    def test_default_config_is_used_when_none_given(self):
        provider = WorkflowProvider()
        assert isinstance(provider._bulk_config, BulkOperationConfig)

    def test_custom_config_is_stored(self):
        cfg = BulkOperationConfig(batch_size=999)
        provider = WorkflowProvider(config=cfg)
        assert provider._bulk_config.batch_size == 999

    def test_saga_store_defaults_to_none(self):
        provider = WorkflowProvider()
        assert provider._saga_store is None

    def test_saga_store_is_stored(self):
        store = AsyncMock()
        provider = WorkflowProvider(saga_store=store)
        assert provider._saga_store is store

    def test_provider_name_is_workflow(self):
        assert WorkflowProvider().name == "workflow"


class TestWorkflowProviderRegister:
    @pytest.mark.asyncio
    async def test_registers_self(self):
        provider = WorkflowProvider()
        container = _mock_container()

        await provider.register(container)

        types = [call.args[0] for call in container.singleton.call_args_list]
        assert WorkflowProvider in types

    @pytest.mark.asyncio
    async def test_registers_bulk_operation_config(self):
        provider = WorkflowProvider()
        container = _mock_container()

        await provider.register(container)

        types = [call.args[0] for call in container.singleton.call_args_list]
        assert BulkOperationConfig in types

    @pytest.mark.asyncio
    async def test_bulk_config_reflects_provider_config(self):
        cfg = BulkOperationConfig(
            batch_size=42,
            max_concurrency=7,
            timeout=99.0,
        )
        provider = WorkflowProvider(config=cfg)
        container = _mock_container()

        await provider.register(container)

        # Find the BulkOperationConfig factory and invoke it.
        bulk_factory = None
        for call in container.singleton.call_args_list:
            if call.args[0] is BulkOperationConfig:
                bulk_factory = call.args[1]
                break
        assert bulk_factory is not None

        bulk_cfg = bulk_factory()
        assert bulk_cfg.batch_size == 42
        assert bulk_cfg.max_concurrency == 7
        assert bulk_cfg.timeout == 99.0

    @pytest.mark.asyncio
    async def test_no_saga_store_registration_when_none(self):
        from quadkit.contracts.workflow import SagaStoreProtocol

        provider = WorkflowProvider()
        container = _mock_container()

        await provider.register(container)

        types = [call.args[0] for call in container.singleton.call_args_list]
        # SagaStoreProtocol should NOT be registered when store is None.
        assert SagaStoreProtocol not in types

    @pytest.mark.asyncio
    async def test_saga_store_registered_when_provided(self):
        from quadkit.contracts.workflow import SagaStoreProtocol

        store = AsyncMock()
        provider = WorkflowProvider(saga_store=store)
        container = _mock_container()

        await provider.register(container)

        # Find any factory bound to SagaStoreProtocol.
        bound_types = [str(call.args[0]) for call in container.singleton.call_args_list]
        protocol_registered = any("SagaStoreProtocol" in t for t in bound_types)
        assert protocol_registered


class TestWorkflowProviderBoot:
    @pytest.mark.asyncio
    async def test_boot_succeeds_with_valid_container(self):
        provider = WorkflowProvider()
        container = _mock_container()
        await provider.register(container)

        # No exception should be raised.
        await provider.boot(container)

    @pytest.mark.asyncio
    async def test_boot_tolerates_resolve_failure(self):
        """Boot must not raise even if container.resolve() fails."""
        provider = WorkflowProvider()
        container = _mock_container()
        container.resolve = AsyncMock(side_effect=RuntimeError("not registered"))

        # Should complete without raising.
        await provider.boot(container)
