"""Integration tests for quadkit-ai-agents package."""

from __future__ import annotations

import pytest

from quadkit.ai.agents.config import AgentConfig
from quadkit.ai.agents.di.provider import AgentsProvider


class TestAgentsProviderIntegration:
    """Integration tests for AgentsProvider basic functionality."""

    @pytest.mark.integration
    def test_provider_initialization_default(self):
        """Test AgentsProvider initialization with default config."""
        provider = AgentsProvider()
        assert provider.name == "ai-agents"

    @pytest.mark.integration
    def test_provider_initialization_with_config(self):
        """Test AgentsProvider initialization with custom config."""
        config = AgentConfig()
        provider = AgentsProvider(config=config)
        assert provider.name == "ai-agents"

    @pytest.mark.integration
    def test_provider_from_config(self):
        """Test AgentsProvider from_config factory."""
        config = AgentConfig()
        provider = AgentsProvider.from_config(config)
        assert provider.name == "ai-agents"

    @pytest.mark.integration
    def test_provider_has_required_attributes(self):
        """Test provider has required attributes."""
        provider = AgentsProvider()
        assert hasattr(provider, "name")

    @pytest.mark.integration
    def test_provider_priority(self):
        """Test provider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority
        provider = AgentsProvider()
        assert provider.priority == ProviderPriority.DOMAIN


class TestAgentConfigIntegration:
    """Integration tests for AgentConfig."""

    @pytest.mark.integration
    def test_agent_config_creation(self):
        """Test AgentConfig can be created."""
        config = AgentConfig()
        assert config is not None

    @pytest.mark.integration
    def test_agent_config_model_dump(self):
        """Test AgentConfig model can be serialized."""
        config = AgentConfig()
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)


class TestAgentsModuleIntegration:
    """Integration tests for AgentsModule."""

    @pytest.mark.integration
    def test_agents_module_import(self):
        """Test AgentsModule can be imported."""
        from quadkit.ai.agents.module import AgentsModule
        assert AgentsModule is not None


class TestAgentStrategiesIntegration:
    """Integration tests for agent strategies."""

    @pytest.mark.integration
    def test_react_strategy_import(self):
        """Test ReAct strategy can be imported."""
        from quadkit.ai.agents.strategies.react import ReActStrategy
        assert ReActStrategy is not None

    @pytest.mark.integration
    def test_strategy_registry_import(self):
        """Test StrategyRegistry can be imported."""
        from quadkit.ai.agents.strategies.strategy_registry import AgentStrategyRegistry
        assert AgentStrategyRegistry is not None