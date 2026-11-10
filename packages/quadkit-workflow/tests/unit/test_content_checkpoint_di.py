"""Unit tests for ContentCheckpointConfig and DI wiring."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointStoreProtocol,
)
from quadkit.workflow.config import ContentCheckpointConfig
from quadkit.workflow.di.provider import WorkflowProvider
from quadkit.workflow.module import WorkflowModule


class TestContentCheckpointConfig:
    def test_defaults(self):
        config = ContentCheckpointConfig()
        assert config.enabled is True
        assert config.inline_threshold_bytes == 1_048_576
        assert config.default_ttl_seconds == 86400

    def test_custom_values(self):
        config = ContentCheckpointConfig(
            enabled=False,
            inline_threshold_bytes=512,
            default_ttl_seconds=3600,
        )
        assert config.enabled is False
        assert config.inline_threshold_bytes == 512
        assert config.default_ttl_seconds == 3600


class TestWorkflowProviderCheckpointStore:
    @pytest.mark.asyncio
    async def test_registers_checkpoint_store_when_provided(self):
        mock_store = MagicMock(spec=ContentCheckpointStoreProtocol)
        provider = WorkflowProvider(content_checkpoint_store=mock_store)

        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        registered_calls = container.singleton.call_args_list
        registered_types = [call[0][0] for call in registered_calls]
        assert ContentCheckpointStoreProtocol in registered_types

    @pytest.mark.asyncio
    async def test_does_not_register_when_not_provided(self):
        provider = WorkflowProvider()

        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        registered_calls = container.singleton.call_args_list
        registered_types = [call[0][0] for call in registered_calls]
        assert ContentCheckpointStoreProtocol not in registered_types


class TestWorkflowModuleCheckpointStore:
    def test_configure_accepts_checkpoint_store(self):
        mock_store = MagicMock(spec=ContentCheckpointStoreProtocol)

        module = WorkflowModule.configure(
            content_checkpoint_store=mock_store,
        )

        assert module is not None
        assert len(module.providers) == 1
        provider = module.providers[0]
        assert isinstance(provider, WorkflowProvider)
