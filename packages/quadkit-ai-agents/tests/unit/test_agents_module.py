"""Tests for agents module."""

from __future__ import annotations

import pytest

from quadkit.ai.agents import AgentsModule
from quadkit.contracts.ai import AgentExecutorProtocol, ToolRegistryProtocol
from quadkit.di.module import DynamicModule
from quadkit.di.module.constants import MODULE_METADATA_ATTR


class TestAgentsModule:
    """Test suite for AgentsModule."""

    def test_module_decorator_exists(self) -> None:
        """Verify @module decorator is applied to AgentsModule."""
        assert hasattr(AgentsModule, MODULE_METADATA_ATTR)

    def test_configure_returns_dynamic_module(self) -> None:
        """Verify configure() returns DynamicModule instance."""
        result = AgentsModule.configure(None)
        assert isinstance(result, DynamicModule)
        assert result.module is AgentsModule

    def test_configure_exports_agent_protocols(self) -> None:
        """Verify configure() exports agent protocols."""
        result = AgentsModule.configure(None)
        assert AgentExecutorProtocol in result.exports
        assert ToolRegistryProtocol in result.exports

    def test_configure_with_dict_config(self) -> None:
        """Verify configure() accepts dict configuration."""
        config = {"max_iterations": 10}
        result = AgentsModule.configure(config)
        assert isinstance(result, DynamicModule)
        assert result.module is AgentsModule
