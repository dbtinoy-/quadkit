"""Tests for agent configuration."""

import pytest

from quadkit.ai.agents.config import AgentConfig


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_default_config(self) -> None:
        """Test default agent configuration."""
        config = AgentConfig()
        assert config.max_iterations == 10
        assert config.default_temperature == 0.7
        assert config.default_max_tokens == 2048
        assert config.enable_tracing is True
        assert config.enable_metrics is True

    def test_custom_max_iterations(self) -> None:
        """Test configuring custom max iterations."""
        config = AgentConfig(max_iterations=20)
        assert config.max_iterations == 20

    def test_max_iterations_minimum(self) -> None:
        """Test that max_iterations must be at least 1."""
        with pytest.raises(ValueError):
            AgentConfig(max_iterations=0)

    def test_custom_temperature(self) -> None:
        """Test configuring custom temperature."""
        config = AgentConfig(default_temperature=0.5)
        assert config.default_temperature == 0.5

    def test_temperature_range(self) -> None:
        """Test temperature range validation."""
        # Valid range is 0.0 to 2.0
        config = AgentConfig(default_temperature=0.0)
        assert config.default_temperature == 0.0

        config = AgentConfig(default_temperature=2.0)
        assert config.default_temperature == 2.0

    def test_temperature_too_high(self) -> None:
        """Test that temperature must be <= 2.0."""
        with pytest.raises(ValueError):
            AgentConfig(default_temperature=2.5)

    def test_temperature_negative(self) -> None:
        """Test that temperature must be >= 0.0."""
        with pytest.raises(ValueError):
            AgentConfig(default_temperature=-0.1)

    def test_custom_max_tokens(self) -> None:
        """Test configuring custom max tokens."""
        config = AgentConfig(default_max_tokens=4096)
        assert config.default_max_tokens == 4096

    def test_max_tokens_minimum(self) -> None:
        """Test that max_tokens must be at least 1."""
        with pytest.raises(ValueError):
            AgentConfig(default_max_tokens=0)

    def test_disable_tracing(self) -> None:
        """Test disabling tracing."""
        config = AgentConfig(enable_tracing=False)
        assert config.enable_tracing is False

    def test_disable_metrics(self) -> None:
        """Test disabling metrics."""
        config = AgentConfig(enable_metrics=False)
        assert config.enable_metrics is False

    def test_full_custom_config(self) -> None:
        """Test configuring all options."""
        config = AgentConfig(
            max_iterations=50,
            default_temperature=1.0,
            default_max_tokens=8192,
            enable_tracing=False,
            enable_metrics=False,
        )
        assert config.max_iterations == 50
        assert config.default_temperature == 1.0
        assert config.default_max_tokens == 8192
        assert config.enable_tracing is False
        assert config.enable_metrics is False
