"""Unit tests for quadkit-tasks types."""

import pytest

from quadkit.tasks.types import PoolStrategy, Priority


class TestPriority:
    """Tests for Priority enum."""

    def test_priority_values(self) -> None:
        """Test Priority enum values."""
        assert Priority.LOW == 0
        assert Priority.NORMAL == 5
        assert Priority.HIGH == 10
        assert Priority.CRITICAL == 20

    def test_priority_ordering(self) -> None:
        """Test Priority enum ordering."""
        assert Priority.LOW < Priority.NORMAL
        assert Priority.NORMAL < Priority.HIGH
        assert Priority.HIGH < Priority.CRITICAL

    def test_priority_is_intenum(self) -> None:
        """Test Priority is an IntEnum."""
        assert isinstance(Priority.LOW, int)
        assert isinstance(Priority.NORMAL, int)
        assert isinstance(Priority.HIGH, int)
        assert isinstance(Priority.CRITICAL, int)

    def test_priority_comparison(self) -> None:
        """Test Priority comparison with integers."""
        assert Priority.LOW == 0
        assert Priority.NORMAL == 5
        assert Priority.HIGH == 10
        assert Priority.CRITICAL == 20

    def test_priority_names(self) -> None:
        """Test Priority enum names."""
        assert Priority.LOW.name == "LOW"
        assert Priority.NORMAL.name == "NORMAL"
        assert Priority.HIGH.name == "HIGH"
        assert Priority.CRITICAL.name == "CRITICAL"

    def test_priority_from_value(self) -> None:
        """Test Priority enum from value."""
        assert Priority(0) == Priority.LOW
        assert Priority(5) == Priority.NORMAL
        assert Priority(10) == Priority.HIGH
        assert Priority(20) == Priority.CRITICAL


class TestPoolStrategy:
    """Tests for PoolStrategy enum."""

    def test_pool_strategy_values(self) -> None:
        """Test PoolStrategy enum values."""
        assert PoolStrategy.FIXED.value == "fixed"
        assert PoolStrategy.DYNAMIC.value == "dynamic"
        assert PoolStrategy.ADAPTIVE.value == "adaptive"

    def test_pool_strategy_names(self) -> None:
        """Test PoolStrategy enum names."""
        assert PoolStrategy.FIXED.name == "FIXED"
        assert PoolStrategy.DYNAMIC.name == "DYNAMIC"
        assert PoolStrategy.ADAPTIVE.name == "ADAPTIVE"

    def test_pool_strategy_from_value(self) -> None:
        """Test PoolStrategy enum from value."""
        assert PoolStrategy("fixed") == PoolStrategy.FIXED
        assert PoolStrategy("dynamic") == PoolStrategy.DYNAMIC
        assert PoolStrategy("adaptive") == PoolStrategy.ADAPTIVE

    def test_pool_strategy_is_string_based(self) -> None:
        """Test PoolStrategy is a string-based enum."""
        assert isinstance(PoolStrategy.FIXED.value, str)
        assert isinstance(PoolStrategy.DYNAMIC.value, str)
        assert isinstance(PoolStrategy.ADAPTIVE.value, str)

    def test_all_exports(self) -> None:
        """Test that all types are properly exported."""
        from quadkit.tasks import types

        expected = ["PoolStrategy", "Priority"]
        for name in expected:
            assert hasattr(types, name)
