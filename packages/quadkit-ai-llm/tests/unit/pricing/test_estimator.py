"""Tests for PricingCostEstimator."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.pricing import ModelPricing, PricingManager
from quadkit.ai.llm.pricing.estimator import PricingCostEstimator
from quadkit.ai.llm.pricing.sources import AbstractPricingSource


class FakeSource(AbstractPricingSource):
    """Pricing source double returning a fixed snapshot."""

    source_name = "fake"

    def __init__(self, data: dict[str, ModelPricing]) -> None:
        self._data = data

    async def get_pricing(self, model: str) -> ModelPricing | None:
        return self._data.get(model)

    async def get_all_pricing(self) -> dict[str, ModelPricing]:
        return dict(self._data)


def _pricing(
    model: str,
    prompt_per_1m: float,
    completion_per_1m: float,
) -> dict[str, ModelPricing]:
    return {
        model: ModelPricing(
            model=model,
            prompt_per_1m=prompt_per_1m,
            completion_per_1m=completion_per_1m,
            provider="openai",
        )
    }


class TestPricingCostEstimator:
    """Tests for PricingCostEstimator."""

    def test_split_prices_prompt_and_completion(self) -> None:
        estimator = PricingCostEstimator(_pricing("gpt-4o", 2.5, 10.0))

        cost = estimator.estimate_cost(
            "gpt-4o", 1500, prompt_tokens=1000, completion_tokens=500
        )

        assert cost == pytest.approx(0.0025 + 0.005)

    def test_unknown_split_prices_total_at_input_rate(self) -> None:
        estimator = PricingCostEstimator(_pricing("gpt-4o", 2.5, 10.0))

        cost = estimator.estimate_cost("gpt-4o", 1000)

        assert cost == pytest.approx(0.0025)

    def test_case_insensitive_exact_match(self) -> None:
        estimator = PricingCostEstimator(_pricing("Gpt-4o", 2.5, 10.0))

        cost = estimator.estimate_cost("gpt-4o", 1000)

        assert cost == pytest.approx(0.0025)

    def test_fuzzy_match_finds_slug(self) -> None:
        estimator = PricingCostEstimator(
            _pricing("openai/gpt-4o", 2.5, 10.0)
        )

        cost = estimator.estimate_cost("gpt-4o", 1000)

        assert cost == pytest.approx(0.0025)

    def test_fuzzy_match_finds_suffix(self) -> None:
        estimator = PricingCostEstimator(_pricing("gpt-4o", 2.5, 10.0))

        cost = estimator.estimate_cost("gpt-4o-mini", 1000)

        assert cost == pytest.approx(0.0025)

    def test_unknown_model_prices_zero(self) -> None:
        estimator = PricingCostEstimator(_pricing("gpt-4o", 2.5, 10.0))

        assert estimator.estimate_cost("unknown-model", 1000) == 0.0

    def test_fuzzy_disabled_returns_zero(self) -> None:
        estimator = PricingCostEstimator(
            _pricing("openai/gpt-4o", 2.5, 10.0),
            enable_fuzzy_match=False,
        )

        assert estimator.estimate_cost("gpt-4o", 1000) == 0.0

    @pytest.mark.asyncio
    async def test_warm_reloads_from_manager(self) -> None:
        data = _pricing("openai/gpt-4o", 2.5, 10.0)
        manager = PricingManager(
            sources=[FakeSource(data)], enable_fuzzy_match=True
        )
        estimator = PricingCostEstimator({})

        await estimator.warm(manager)

        assert "openai/gpt-4o" in estimator.pricing
        assert estimator.pricing["openai/gpt-4o"] is data["openai/gpt-4o"]
