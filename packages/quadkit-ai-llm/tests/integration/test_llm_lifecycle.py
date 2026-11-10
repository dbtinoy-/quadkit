"""Integration tests for quadkit-ai-llm package lifecycle."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.di.provider import LLMProvider


class TestLLMProviderIntegration:
    """Integration tests for LLMProvider basic functionality."""

    @pytest.mark.integration
    def test_provider_initialization_default(self):
        """Test LLMProvider initialization with default config."""
        provider = LLMProvider()
        assert provider.name == "llm"

    @pytest.mark.integration
    def test_provider_initialization_with_config(self):
        """Test LLMProvider initialization with custom config."""
        config = ClientConfig(provider="openai", model="gpt-4")
        provider = LLMProvider(config=config)
        assert provider.name == "llm"

    @pytest.mark.integration
    def test_provider_has_required_attributes(self):
        """Test provider has required attributes."""
        provider = LLMProvider()
        assert hasattr(provider, "name")

    @pytest.mark.integration
    def test_provider_priority(self):
        """Test provider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority
        provider = LLMProvider()
        assert provider.priority == ProviderPriority.DOMAIN


class TestClientConfigIntegration:
    """Integration tests for ClientConfig."""

    @pytest.mark.integration
    def test_client_config_creation(self):
        """Test ClientConfig can be created."""
        config = ClientConfig(provider="openai", model="gpt-4")
        assert config is not None

    @pytest.mark.integration
    def test_client_config_model_dump(self):
        """Test ClientConfig model can be serialized."""
        config = ClientConfig(provider="openai", model="gpt-4")
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)

    @pytest.mark.integration
    def test_client_config_has_provider(self):
        """Test ClientConfig has provider field."""
        config = ClientConfig(provider="openai", model="gpt-4")
        assert config.provider == "openai"

    @pytest.mark.integration
    def test_client_config_has_model(self):
        """Test ClientConfig has model field."""
        config = ClientConfig(provider="openai", model="gpt-4")
        assert config.model == "gpt-4"


class TestLLMModuleIntegration:
    """Integration tests for LLMModule."""

    @pytest.mark.integration
    def test_llm_module_import(self):
        """Test LLMModule can be imported."""
        from quadkit.ai.llm.module import LLMModule
        assert LLMModule is not None


class TestLLMClientsIntegration:
    """Integration tests for LLM clients."""

    @pytest.mark.integration
    def test_ollama_client_import(self):
        """Test OllamaClient can be imported."""
        from quadkit.ai.llm.clients.ollama import OllamaClient
        assert OllamaClient is not None

    @pytest.mark.integration
    def test_openai_client_import(self):
        """Test OpenAI client can be imported."""
        from quadkit.ai.llm.clients.openai import OpenAIClient
        assert OpenAIClient is not None

    @pytest.mark.integration
    def test_anthropic_client_import(self):
        """Test Anthropic client can be imported."""
        from quadkit.ai.llm.clients.anthropic import AnthropicClient
        assert AnthropicClient is not None


class TestLLMTypesIntegration:
    """Integration tests for LLM types."""

    @pytest.mark.integration
    def test_chat_message_import(self):
        """Test ChatMessage can be imported."""
        from quadkit.ai.llm.types import ChatMessage
        assert ChatMessage is not None

    @pytest.mark.integration
    def test_role_import(self):
        """Test Role enum can be imported."""
        from quadkit.ai.llm.types import Role
        assert Role is not None

    @pytest.mark.integration
    def test_completion_import(self):
        """Test Completion can be imported."""
        from quadkit.ai.llm.types import Completion
        assert Completion is not None


class TestLLMConfigIntegration:
    """Integration tests for LLM config types."""

    @pytest.mark.integration
    def test_client_config_has_provider(self):
        """Test ClientConfig has provider field."""
        config = ClientConfig(provider="openai", model="gpt-4")
        assert config.provider == "openai"

    @pytest.mark.integration
    def test_client_config_has_model(self):
        """Test ClientConfig has model field."""
        config = ClientConfig(provider="openai", model="gpt-4")
        assert config.model == "gpt-4"