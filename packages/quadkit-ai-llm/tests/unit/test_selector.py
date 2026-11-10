"""Unit tests for quadkit-ai-llm model selector."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.selection.core import (
    DEFAULT_MODEL_CAPABILITIES,
    ModelCapabilities,
    ModelSelector,
    SelectionCriteria,
    SelectionStrategy,
    create_balanced_selector,
    create_cost_optimized_selector,
    create_quality_optimized_selector,
)


class TestSelectionCriteria:
    """Tests for SelectionCriteria enum."""

    def test_token_count_criteria(self) -> None:
        """Test TOKEN_COUNT criteria."""
        assert SelectionCriteria.TOKEN_COUNT == "token_count"

    def test_cost_criteria(self) -> None:
        """Test COST criteria."""
        assert SelectionCriteria.COST == "cost"

    def test_latency_criteria(self) -> None:
        """Test LATENCY criteria."""
        assert SelectionCriteria.LATENCY == "latency"

    def test_quality_criteria(self) -> None:
        """Test QUALITY criteria."""
        assert SelectionCriteria.QUALITY == "quality"


class TestSelectionStrategy:
    """Tests for SelectionStrategy."""

    def test_default_strategy(self) -> None:
        """Test SelectionStrategy default values."""
        strategy = SelectionStrategy(
            name="test",
            model="gpt-4",
        )

        assert strategy.name == "test"
        assert strategy.model == "gpt-4"
        assert strategy.conditions == {}

    def test_strategy_with_conditions(self) -> None:
        """Test SelectionStrategy with conditions."""
        strategy = SelectionStrategy(
            name="complex",
            model="gpt-4-turbo",
            conditions={"min_tokens": 1000, "quality": "high"},
        )

        assert strategy.name == "complex"
        assert strategy.model == "gpt-4-turbo"
        assert strategy.conditions["min_tokens"] == 1000
        assert strategy.conditions["quality"] == "high"


class TestModelCapabilities:
    """Tests for ModelCapabilities."""

    def test_default_capabilities(self) -> None:
        """Test ModelCapabilities default values."""
        caps = ModelCapabilities(
            max_tokens=8192,
        )

        assert caps.max_tokens == 8192
        assert caps.supports_functions is False

    def test_custom_capabilities(self) -> None:
        """Test ModelCapabilities with custom values."""
        caps = ModelCapabilities(
            max_tokens=4096,
            cost_per_1k_input=0.001,
            cost_per_1k_output=0.002,
            supports_functions=True,
            supports_vision=False,
        )

        assert caps.cost_per_1k_input == 0.001
        assert caps.cost_per_1k_output == 0.002
        assert caps.supports_functions is True
        assert caps.supports_vision is False


class TestModelSelector:
    """Tests for ModelSelector."""

    def test_empty_selector(self) -> None:
        """Test ModelSelector with no strategies."""
        selector = ModelSelector(default_model="gpt-3.5-turbo")

        # Should return default model
        model = selector.select("Simple prompt")
        assert model == "gpt-3.5-turbo"

    def test_selector_with_strategy(self) -> None:
        """Test ModelSelector with selection strategy."""
        selector = ModelSelector(
            default_model="gpt-3.5-turbo",
            strategies=[
                SelectionStrategy(
                    name="complex",
                    model="gpt-4-turbo",
                    conditions={"min_tokens": 1000},
                ),
            ],
        )

        # Should select gpt-4-turbo for long prompts
        model = selector.select("Write a very long and detailed story " * 200)
        assert model == "gpt-4-turbo"

    def test_selector_fallback_chain(self) -> None:
        """Test ModelSelector with fallback chain."""
        selector = ModelSelector(
            default_model="gpt-3.5-turbo",
            fallback_chain=["gpt-4-turbo", "gpt-3.5-turbo"],
        )

        # Should use fallback
        model = selector.select("Test prompt")
        # Will return default if no strategy matches
        assert model is not None

    def test_selector_with_multiple_strategies(self) -> None:
        """Test ModelSelector with multiple strategies."""
        selector = ModelSelector(
            default_model="gpt-3.5-turbo",
            strategies=[
                SelectionStrategy(
                    name="quick",
                    model="gpt-3.5-turbo",
                    conditions={"max_latency_ms": 1000},
                ),
                SelectionStrategy(
                    name="quality",
                    model="gpt-4-turbo",
                    conditions={"quality": "high"},
                ),
            ],
        )

        model = selector.select("Test prompt")
        assert model is not None


class TestDefaultCapabilities:
    """Tests for DEFAULT_MODEL_CAPABILITIES."""

    def test_default_capabilities_exist(self) -> None:
        """Test DEFAULT_MODEL_CAPABILITIES is populated."""
        # Should have at least some known models
        assert len(DEFAULT_MODEL_CAPABILITIES) > 0

    def test_gpt4_capabilities(self) -> None:
        """Test GPT-4 is in default capabilities."""
        assert "gpt-4" in DEFAULT_MODEL_CAPABILITIES
        caps = DEFAULT_MODEL_CAPABILITIES["gpt-4"]
        assert caps.max_tokens > 0


class TestSelectorFactories:
    """Tests for selector factory functions."""

    def test_create_balanced_selector(self) -> None:
        """Test create_balanced_selector factory."""
        selector = create_balanced_selector()

        assert isinstance(selector, ModelSelector)
        assert selector.default_model is not None
        assert len(selector.strategies) > 0

    def test_create_cost_optimized_selector(self) -> None:
        """Test create_cost_optimized_selector factory."""
        selector = create_cost_optimized_selector()

        assert isinstance(selector, ModelSelector)
        # Cost-optimized should prefer cheaper models

    def test_create_quality_optimized_selector(self) -> None:
        """Test create_quality_optimized_selector factory."""
        selector = create_quality_optimized_selector()

        assert isinstance(selector, ModelSelector)
        # Quality-optimized should prefer better models


class TestModelSelectorEdgeCases:
    """Edge case tests for ModelSelector."""

    def test_select_with_empty_prompt(self) -> None:
        """Test selecting model with empty prompt."""
        selector = ModelSelector(default_model="gpt-3.5-turbo")

        model = selector.select("")
        assert model == "gpt-3.5-turbo"

    def test_selector_with_criteria(self) -> None:
        """Test selector with selection criteria."""
        selector = ModelSelector(
            default_model="gpt-3.5-turbo",
        )

        model = selector.select("Test", required_capabilities=["supports_functions"])
        assert model == "gpt-3.5-turbo"

    def test_selector_respects_max_tokens(self) -> None:
        """Test selector considers max_tokens in selection."""
        selector = ModelSelector(
            default_model="gpt-3.5-turbo",
            strategies=[
                SelectionStrategy(
                    name="long",
                    model="gpt-4-turbo",
                    conditions={"min_tokens": 5000},
                ),
            ],
        )

        model = selector.select("Test", context={"tokens": 6000})
        # Should prefer model with larger context
        assert model == "gpt-4-turbo"
