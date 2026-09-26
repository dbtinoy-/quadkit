"""Tests for task types and enums."""

import pytest

from quadkit.tasks.types import PoolStrategy, Priority


class TestPriority:
    """Tests for Priority enum."""

    def test_low_priority(self) -> None:
        assert Priority.LOW == 0

    def test_normal_priority(self) -> None:
        assert Priority.NORMAL == 5

    def test_high_priority(self) -> None:
        assert Priority.HIGH == 10

    def test_critical_priority(self) -> None:
        assert Priority.CRITICAL == 20

    def test_priority_ordering(self) -> None:
        assert Priority.LOW < Priority.NORMAL < Priority.HIGH < Priority.CRITICAL


class TestPoolStrategy:
    """Tests for PoolStrategy enum."""

    def test_fixed_strategy(self) -> None:
        assert PoolStrategy.FIXED.value == "fixed"

    def test_dynamic_strategy(self) -> None:
        assert PoolStrategy.DYNAMIC.value == "dynamic"

    def test_adaptive_strategy(self) -> None:
        assert PoolStrategy.ADAPTIVE.value == "adaptive"
