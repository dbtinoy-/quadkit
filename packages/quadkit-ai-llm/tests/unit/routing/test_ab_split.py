"""Tests for A/B split routing strategy."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.routing.ab_split import ABSplitConfig, ABSplitStrategy


class MockRequest:
    """Simple request mock with user_id attribute."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id


class MockLLMClient:
    """Mock LLM client."""

    def __init__(self, name: str) -> None:
        self.name = name


class TestABSplitConfig:
    """Tests for ABSplitConfig validation."""

    def test_invalid_percentage_raises(self) -> None:
        """Percentage outside [0,100] raises ValueError."""
        with pytest.raises(ValueError, match="treatment_percentage"):
            ABSplitConfig(
                control_key="control",
                treatment_key="treatment",
                treatment_percentage=101,
            )

    def test_valid_config_created(self) -> None:
        """Valid config is created without errors."""
        config = ABSplitConfig(
            control_key="ctrl",
            treatment_key="treat",
            treatment_percentage=20,
        )
        assert config.treatment_percentage == 20


class TestABSplitStrategy:
    """Tests for ABSplitStrategy routing."""

    def _make_strategy(
        self, treatment_percentage: int = 50
    ) -> tuple[ABSplitStrategy, MockLLMClient, MockLLMClient]:
        control = MockLLMClient("control")
        treatment = MockLLMClient("treatment")
        config = ABSplitConfig(
            control_key="ctrl",
            treatment_key="treat",
            treatment_percentage=treatment_percentage,
        )
        strategy = ABSplitStrategy(config=config, control=control, treatment=treatment)
        return strategy, control, treatment

    @pytest.mark.asyncio
    async def test_zero_percent_always_routes_to_control(self) -> None:
        """0% treatment routes every request to control."""
        strategy, control, treatment = self._make_strategy(treatment_percentage=0)
        for i in range(20):
            result = await strategy.route(MockRequest(user_id=f"user-{i}"))
            assert result is control

    @pytest.mark.asyncio
    async def test_hundred_percent_always_routes_to_treatment(self) -> None:
        """100% treatment routes every request to treatment."""
        strategy, control, treatment = self._make_strategy(treatment_percentage=100)
        for i in range(20):
            result = await strategy.route(MockRequest(user_id=f"user-{i}"))
            assert result is treatment

    @pytest.mark.asyncio
    async def test_deterministic_routing_same_user_same_variant(self) -> None:
        """Same user_id always maps to same variant (deterministic)."""
        strategy, control, treatment = self._make_strategy(treatment_percentage=50)
        request = MockRequest(user_id="user-stable")
        first_result = await strategy.route(request)
        for _ in range(10):
            result = await strategy.route(request)
            assert result is first_result

    def test_bucket_distribution_is_reasonable(self) -> None:
        """With 50% treatment, roughly half of users get treatment."""
        strategy, control, treatment = self._make_strategy(treatment_percentage=50)
        results = [
            strategy._should_use_treatment(MockRequest(user_id=f"user-{i}"))
            for i in range(200)
        ]
        treatment_count = sum(results)
        # Should be roughly 50%, allow wide tolerance
        assert 60 <= treatment_count <= 140
