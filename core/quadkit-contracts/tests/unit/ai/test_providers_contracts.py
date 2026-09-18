"""Tests for provider contracts."""

import pytest
from dataclasses import replace
from datetime import datetime, timezone

from quadkit.contracts.ai.providers import (
    FallbackChainProtocol,
    ModelCapability,
    ModelInfo,
    ModelSelectorProtocol,
    ProviderHealth,
    ProviderRegistryProtocol,
    SelectionStrategy,
)


class TestProviderEnums:
    """Test provider enum definitions."""

    def test_model_capability_enum(self) -> None:
        """ModelCapability should have all expected values."""
        assert ModelCapability.CHAT.value == "chat"
        assert ModelCapability.COMPLETION.value == "completion"
        assert ModelCapability.EMBEDDING.value == "embedding"
        assert ModelCapability.VISION.value == "vision"
        assert ModelCapability.FUNCTION_CALLING.value == "function_calling"
        assert ModelCapability.STREAMING.value == "streaming"
        assert ModelCapability.JSON_MODE.value == "json_mode"
        assert ModelCapability.AUDIO.value == "audio"
        assert ModelCapability.CODE.value == "code"
        assert len(ModelCapability) == 9

    def test_selection_strategy_enum(self) -> None:
        """SelectionStrategy should have all expected values."""
        assert SelectionStrategy.COST_OPTIMAL.value == "cost_optimal"
        assert SelectionStrategy.LATENCY_OPTIMAL.value == "latency_optimal"
        assert SelectionStrategy.CAPABILITY_MATCH.value == "capability_match"
        assert SelectionStrategy.ROUND_ROBIN.value == "round_robin"
        assert SelectionStrategy.PREFERRED.value == "preferred"
        assert len(SelectionStrategy) == 5


class TestProviderDataclasses:
    """Test provider dataclass definitions."""

    def test_model_info_frozen(self) -> None:
        """ModelInfo should be frozen."""
        info = ModelInfo(
            model_id="gpt-4",
            provider="openai",
            display_name="GPT-4",
            capabilities=frozenset([ModelCapability.CHAT]),
            context_window=8192,
            max_output_tokens=2048,
            input_cost_per_million=0.03,
            output_cost_per_million=0.06,
        )
        with pytest.raises(AttributeError):
            info.context_window = 16384

    def test_model_info_defaults(self) -> None:
        """ModelInfo should have proper defaults."""
        info = ModelInfo(
            model_id="gpt-4",
            provider="openai",
            display_name="GPT-4",
            capabilities=frozenset([ModelCapability.CHAT]),
            context_window=8192,
            max_output_tokens=2048,
            input_cost_per_million=0.03,
            output_cost_per_million=0.06,
        )
        assert info.is_available is True
        assert info.metadata == {}

    def test_provider_health_mutable(self) -> None:
        """ProviderHealth should allow creating new instances with updated values."""
        health = ProviderHealth(
            provider="openai",
            is_healthy=True,
            latency_ms=100.0,
            error_rate=0.0,
            last_check=datetime.now(timezone.utc),
        )
        # Should be able to create a new instance with updated values
        updated_health = replace(health, is_healthy=False)
        assert updated_health.is_healthy is False
        assert health.is_healthy is True  # Original unchanged

    def test_provider_health_defaults(self) -> None:
        """ProviderHealth should have proper defaults."""
        health = ProviderHealth(
            provider="openai",
            is_healthy=True,
            latency_ms=100.0,
            error_rate=0.0,
            last_check=datetime.now(timezone.utc),
        )
        assert health.details == {}


class TestProviderProtocols:
    """Test provider protocols are runtime checkable."""

    def test_provider_registry_protocol_runtime_checkable(self) -> None:
        """ProviderRegistryProtocol should be runtime checkable."""
        assert isinstance(ProviderRegistryProtocol, type)

        class MockRegistry:
            async def register_provider(self, name, client, models):
                pass

            async def get_client(self, provider):
                return None

            def list_providers(self):
                return []

            def list_models(self, capabilities=None):
                return []

            def get_model_info(self, model_id):
                return None

        mock = MockRegistry()
        assert isinstance(mock, ProviderRegistryProtocol)

    def test_model_selector_protocol_runtime_checkable(self) -> None:
        """ModelSelectorProtocol should be runtime checkable."""
        assert isinstance(ModelSelectorProtocol, type)

        class MockSelector:
            async def select(
                self,
                capabilities,
                preferred_provider=None,
                max_cost_per_million=None,
                strategy=SelectionStrategy.COST_OPTIMAL,
            ):
                return None

        mock = MockSelector()
        assert isinstance(mock, ModelSelectorProtocol)

    def test_fallback_chain_protocol_runtime_checkable(self) -> None:
        """FallbackChainProtocol should be runtime checkable."""
        assert isinstance(FallbackChainProtocol, type)

        class MockFallback:
            async def execute(self, request, providers):
                return None

        mock = MockFallback()
        assert isinstance(mock, FallbackChainProtocol)
