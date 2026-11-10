"""Tests for ClientConfig (LLM client configuration)."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.contracts.ai.types import ModelProvider


class TestClientConfigDefaults:
    """Test ClientConfig default values."""

    def test_default_config_enabled(self) -> None:
        """Default config should be enabled."""
        config = ClientConfig()

        assert config.enabled is True

    def test_default_provider(self) -> None:
        """Default config should use OpenAI provider."""
        config = ClientConfig()

        assert config.provider == ModelProvider.OPENAI

    def test_default_model(self) -> None:
        """Default config should specify a default model."""
        config = ClientConfig()

        assert config.model == "gpt-4-turbo"

    def test_default_temperature(self) -> None:
        """Default config should have reasonable temperature."""
        config = ClientConfig()

        assert config.temperature == 0.7
        assert 0.0 <= config.temperature <= 2.0

    def test_default_timeout(self) -> None:
        """Default config should have timeout set."""
        config = ClientConfig()

        assert config.timeout == 60.0
        assert config.timeout >= 1.0

    def test_default_cache_settings(self) -> None:
        """Default config should have cache disabled by default."""
        config = ClientConfig()

        assert config.enable_cache is False
        assert config.cache_ttl == 3600


class TestClientConfigCustomization:
    """Test ClientConfig customization."""

    def test_can_customize_provider(self) -> None:
        """Config should allow setting provider."""
        config = ClientConfig(provider=ModelProvider.ANTHROPIC)

        assert config.provider == ModelProvider.ANTHROPIC

    def test_can_customize_model(self) -> None:
        """Config should allow setting model."""
        config = ClientConfig(model="claude-3-opus")

        assert config.model == "claude-3-opus"

    def test_can_set_api_key(self) -> None:
        """Config should allow setting API key."""
        config = ClientConfig(api_key="secret-key")

        # API key is a SecretStr, so we check that it was set
        assert config.api_key is not None

    def test_can_customize_temperature(self) -> None:
        """Config should allow setting temperature."""
        config = ClientConfig(temperature=1.0)

        assert config.temperature == 1.0

    def test_can_set_max_tokens(self) -> None:
        """Config should allow setting max tokens."""
        config = ClientConfig(max_tokens=4000)

        assert config.max_tokens == 4000

    def test_can_customize_timeout(self) -> None:
        """Config should allow setting timeout."""
        config = ClientConfig(timeout=120.0)

        assert config.timeout == 120.0

    def test_can_enable_cache(self) -> None:
        """Config should allow enabling cache."""
        config = ClientConfig(enable_cache=True, cache_ttl=7200)

        assert config.enable_cache is True
        assert config.cache_ttl == 7200

    def test_can_set_api_base(self) -> None:
        """Config should allow setting custom API base."""
        config = ClientConfig(api_base="https://api.example.com")

        assert config.api_base == "https://api.example.com"

    def test_full_customization(self) -> None:
        """Config should handle full customization."""
        config = ClientConfig(
            enabled=True,
            provider=ModelProvider.ANTHROPIC,
            model="claude-3-sonnet",
            api_key="key-123",
            api_base="https://custom.api.com",
            temperature=0.5,
            max_tokens=2000,
            timeout=90.0,
            enable_cache=True,
            cache_ttl=3600,
        )

        assert config.enabled is True
        assert config.provider == ModelProvider.ANTHROPIC
        assert config.model == "claude-3-sonnet"
        assert config.temperature == 0.5
        assert config.max_tokens == 2000
        assert config.timeout == 90.0
        assert config.enable_cache is True
        assert config.cache_ttl == 3600


class TestClientConfigValidation:
    """Test ClientConfig validation and constraints."""

    def test_temperature_range_valid(self) -> None:
        """Temperature must be between 0.0 and 2.0."""
        # Valid: minimum
        config = ClientConfig(temperature=0.0)
        assert config.temperature == 0.0

        # Valid: maximum
        config = ClientConfig(temperature=2.0)
        assert config.temperature == 2.0

        # Valid: middle
        config = ClientConfig(temperature=1.0)
        assert config.temperature == 1.0

    def test_max_tokens_must_be_positive(self) -> None:
        """max_tokens must be >= 1 if set."""
        config = ClientConfig(max_tokens=1)
        assert config.max_tokens == 1

        config = ClientConfig(max_tokens=4096)
        assert config.max_tokens == 4096

    def test_timeout_must_be_positive(self) -> None:
        """timeout must be >= 1.0."""
        config = ClientConfig(timeout=1.0)
        assert config.timeout == 1.0

        config = ClientConfig(timeout=300.0)
        assert config.timeout == 300.0


class TestClientConfigProviders:
    """Test support for different providers."""

    def test_openai_provider(self) -> None:
        """Config should support OpenAI provider."""
        config = ClientConfig(provider=ModelProvider.OPENAI)
        assert config.provider == ModelProvider.OPENAI

    def test_anthropic_provider(self) -> None:
        """Config should support Anthropic provider."""
        config = ClientConfig(provider=ModelProvider.ANTHROPIC)
        assert config.provider == ModelProvider.ANTHROPIC

    def test_azure_provider(self) -> None:
        """Config should support Azure provider."""
        config = ClientConfig(provider=ModelProvider.AZURE_OPENAI)
        assert config.provider == ModelProvider.AZURE_OPENAI

    def test_ollama_provider(self) -> None:
        """Config should support Ollama provider."""
        config = ClientConfig(provider=ModelProvider.OLLAMA)
        assert config.provider == ModelProvider.OLLAMA


class TestClientConfigCaching:
    """Test cache-related settings."""

    def test_cache_disabled_by_default(self) -> None:
        """Caching should be disabled by default."""
        config = ClientConfig()

        assert config.enable_cache is False

    def test_can_enable_cache(self) -> None:
        """Caching should be independently enableable."""
        config = ClientConfig(enable_cache=True)

        assert config.enable_cache is True

    def test_cache_ttl_setting(self) -> None:
        """Cache TTL should be configurable."""
        config = ClientConfig(cache_ttl=7200)

        assert config.cache_ttl == 7200

    def test_can_disable_system(self) -> None:
        """LLM subsystem can be disabled."""
        config = ClientConfig(enabled=False)

        assert config.enabled is False
