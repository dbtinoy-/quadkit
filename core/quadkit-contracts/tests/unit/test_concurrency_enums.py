"""Tests for concurrency enums."""

import pytest

from quadkit.contracts.core.concurrency_enums import ExecutionStrategy


class TestExecutionStrategy:
    """Tests for ExecutionStrategy enum."""

    def test_gather_strategy(self) -> None:
        """Test gather strategy value."""
        assert ExecutionStrategy.GATHER.value == "gather"

    def test_race_strategy(self) -> None:
        """Test race strategy value."""
        assert ExecutionStrategy.RACE.value == "race"

    def test_as_completed_strategy(self) -> None:
        """Test as_completed strategy value."""
        assert ExecutionStrategy.AS_COMPLETED.value == "as_completed"

    def test_all_settled_strategy(self) -> None:
        """Test all_settled strategy value."""
        assert ExecutionStrategy.ALL_SETTLED.value == "all_settled"

    def test_all_strategies_defined(self) -> None:
        """Test all strategies are defined."""
        strategies = list(ExecutionStrategy)
        assert len(strategies) == 4
        assert ExecutionStrategy.GATHER in strategies
        assert ExecutionStrategy.RACE in strategies
        assert ExecutionStrategy.AS_COMPLETED in strategies
        assert ExecutionStrategy.ALL_SETTLED in strategies

    def test_strategy_is_string_enum(self) -> None:
        """Test that ExecutionStrategy is a string enum."""
        # String enum allows comparison with string values
        assert ExecutionStrategy.GATHER == "gather"
        assert ExecutionStrategy.RACE == "race"
        assert ExecutionStrategy.AS_COMPLETED == "as_completed"
        assert ExecutionStrategy.ALL_SETTLED == "all_settled"
