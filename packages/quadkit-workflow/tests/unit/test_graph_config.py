"""Unit tests for GraphConfig configuration dataclass."""

from __future__ import annotations

import pytest

from quadkit.workflow.config import GraphConfig


class TestGraphConfigDefaults:
    def test_max_iterations_default(self) -> None:
        config = GraphConfig()
        assert config.max_iterations == 25

    def test_node_timeout_default(self) -> None:
        config = GraphConfig()
        assert config.node_timeout == 120.0

    def test_total_timeout_default_is_zero(self) -> None:
        config = GraphConfig()
        assert config.total_timeout == 0.0

    def test_checkpoint_enabled_default_is_false(self) -> None:
        config = GraphConfig()
        assert config.checkpoint_enabled is False

    def test_parallel_branches_default_is_true(self) -> None:
        config = GraphConfig()
        assert config.parallel_branches is True

    def test_max_parallel_branches_default_is_zero(self) -> None:
        config = GraphConfig()
        assert config.max_parallel_branches == 0


class TestGraphConfigCustomValues:
    def test_custom_max_iterations(self) -> None:
        config = GraphConfig(max_iterations=50)
        assert config.max_iterations == 50

    def test_custom_node_timeout(self) -> None:
        config = GraphConfig(node_timeout=30.0)
        assert config.node_timeout == 30.0

    def test_custom_total_timeout(self) -> None:
        config = GraphConfig(total_timeout=300.0)
        assert config.total_timeout == 300.0

    def test_checkpoint_enabled_true(self) -> None:
        config = GraphConfig(checkpoint_enabled=True)
        assert config.checkpoint_enabled is True

    def test_parallel_branches_false(self) -> None:
        config = GraphConfig(parallel_branches=False)
        assert config.parallel_branches is False

    def test_max_parallel_branches_custom(self) -> None:
        config = GraphConfig(max_parallel_branches=4)
        assert config.max_parallel_branches == 4


class TestGraphConfigConstraints:
    def test_max_iterations_must_be_at_least_one(self) -> None:
        with pytest.raises((ValueError, Exception)):
            GraphConfig(max_iterations=0)

    def test_node_timeout_must_be_non_negative(self) -> None:
        with pytest.raises((ValueError, Exception)):
            GraphConfig(node_timeout=-1.0)

    def test_total_timeout_must_be_non_negative(self) -> None:
        with pytest.raises((ValueError, Exception)):
            GraphConfig(total_timeout=-0.1)

    def test_max_parallel_branches_must_be_non_negative(self) -> None:
        with pytest.raises((ValueError, Exception)):
            GraphConfig(max_parallel_branches=-1)
