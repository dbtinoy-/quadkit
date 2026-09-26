"""CostAwareCacheDecision eviction tests."""

from __future__ import annotations

import pytest

from quadkit.cache.semantic.cost_decision import CostAwareCacheDecision


class TestCostAwareCacheDecision:
    """Test suite for CostAwareCacheDecision."""

    @pytest.fixture
    def decision(self) -> CostAwareCacheDecision:
        return CostAwareCacheDecision(accuracy_weight=0.7)

    def test_cost_aware_decision_uses_cache_high_cost(
        self,
        decision: CostAwareCacheDecision,
    ) -> None:
        result = decision.should_use_cache(
            similarity=0.95,
            api_cost_per_1k_tokens=0.03,
            expected_tokens=5000,
        )
        assert result is True

    def test_cost_aware_decision_skips_cache_low_cost(
        self,
        decision: CostAwareCacheDecision,
    ) -> None:
        result = decision.should_use_cache(
            similarity=0.85,
            api_cost_per_1k_tokens=0.03,
            expected_tokens=100,
        )
        assert result is False

    def test_cost_aware_decision_zero_cost_never_uses_cache(
        self,
        decision: CostAwareCacheDecision,
    ) -> None:
        result = decision.should_use_cache(
            similarity=0.99,
            api_cost_per_1k_tokens=0.0,
            expected_tokens=1000,
        )
        assert result is False

    def test_cost_aware_decision_zero_tokens_never_uses_cache(
        self,
        decision: CostAwareCacheDecision,
    ) -> None:
        result = decision.should_use_cache(
            similarity=0.99,
            api_cost_per_1k_tokens=0.03,
            expected_tokens=0,
        )
        assert result is False

    def test_cost_aware_decision_perfect_similarity(
        self,
        decision: CostAwareCacheDecision,
    ) -> None:
        result = decision.should_use_cache(
            similarity=1.0,
            api_cost_per_1k_tokens=0.001,
            expected_tokens=100,
        )
        assert result is True

    def test_cost_aware_decision_init_invalid_accuracy_weight(self) -> None:
        with pytest.raises(ValueError, match="accuracy_weight"):
            CostAwareCacheDecision(accuracy_weight=1.5)

    def test_cost_aware_decision_init_negative_weight(self) -> None:
        with pytest.raises(ValueError, match="accuracy_weight"):
            CostAwareCacheDecision(accuracy_weight=-0.1)

    def test_cost_aware_decision_invalid_similarity(
        self,
        decision: CostAwareCacheDecision,
    ) -> None:
        with pytest.raises(ValueError, match="similarity"):
            decision.should_use_cache(
                similarity=1.5,
                api_cost_per_1k_tokens=0.03,
                expected_tokens=1000,
            )

    def test_cost_aware_decision_invalid_cost(
        self,
        decision: CostAwareCacheDecision,
    ) -> None:
        with pytest.raises(ValueError, match="api_cost_per_1k_tokens"):
            decision.should_use_cache(
                similarity=0.95,
                api_cost_per_1k_tokens=-0.01,
                expected_tokens=1000,
            )

    def test_cost_aware_decision_invalid_tokens(
        self,
        decision: CostAwareCacheDecision,
    ) -> None:
        with pytest.raises(ValueError, match="expected_tokens"):
            decision.should_use_cache(
                similarity=0.95,
                api_cost_per_1k_tokens=0.03,
                expected_tokens=-100,
            )
