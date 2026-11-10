"""Unit tests for quadkit-workflow configuration classes.

Tests verify BulkOperationConfig and GraphConfig behavior.
"""

import pytest
from quadkit.workflow.config import BulkOperationConfig, GraphConfig


class TestBulkOperationConfigDefaults:
    """Tests for BulkOperationConfig default values."""

    def test_default_batch_size(self) -> None:
        config = BulkOperationConfig()
        assert config.batch_size == 10

    def test_default_max_concurrency(self) -> None:
        config = BulkOperationConfig()
        assert config.max_concurrency == 5

    def test_default_timeout(self) -> None:
        config = BulkOperationConfig()
        assert config.timeout == 300.0

    def test_default_retry_attempts(self) -> None:
        config = BulkOperationConfig()
        assert config.retry_attempts == 3

    def test_default_retry_delay(self) -> None:
        config = BulkOperationConfig()
        assert config.retry_delay == 1.0

    def test_default_enable_progress_tracking(self) -> None:
        config = BulkOperationConfig()
        assert config.enable_progress_tracking is True

    def test_default_circuit_breaker_config(self) -> None:
        config = BulkOperationConfig()
        assert config.circuit_breaker_config is None

    def test_default_pipeline_timeout(self) -> None:
        config = BulkOperationConfig()
        assert config.pipeline_timeout == 60.0


class TestBulkOperationConfigValidation:
    """Tests for BulkOperationConfig field validation."""

    def test_batch_size_must_be_greater_than_zero(self) -> None:
        with pytest.raises(ValueError):
            BulkOperationConfig(batch_size=0)

    def test_max_concurrency_must_be_greater_than_zero(self) -> None:
        with pytest.raises(ValueError):
            BulkOperationConfig(max_concurrency=0)

    def test_timeout_must_be_greater_than_zero(self) -> None:
        with pytest.raises(ValueError):
            BulkOperationConfig(timeout=0.0)

    def test_retry_attempts_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError):
            BulkOperationConfig(retry_attempts=-1)

    def test_retry_delay_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError):
            BulkOperationConfig(retry_delay=-1.0)

    def test_pipeline_timeout_must_be_greater_than_zero(self) -> None:
        with pytest.raises(ValueError):
            BulkOperationConfig(pipeline_timeout=0.0)


class TestBulkOperationConfigCustomValues:
    """Tests for BulkOperationConfig with custom values."""

    def test_custom_batch_size(self) -> None:
        config = BulkOperationConfig(batch_size=50)
        assert config.batch_size == 50

    def test_custom_max_concurrency(self) -> None:
        config = BulkOperationConfig(max_concurrency=20)
        assert config.max_concurrency == 20

    def test_custom_timeout(self) -> None:
        config = BulkOperationConfig(timeout=600.0)
        assert config.timeout == 600.0

    def test_custom_retry_attempts(self) -> None:
        config = BulkOperationConfig(retry_attempts=5)
        assert config.retry_attempts == 5

    def test_custom_retry_delay(self) -> None:
        config = BulkOperationConfig(retry_delay=2.0)
        assert config.retry_delay == 2.0


class TestGraphConfigDefaults:
    """Tests for GraphConfig default values."""

    def test_default_enabled(self) -> None:
        config = GraphConfig()
        assert config.enabled is True

    def test_default_max_iterations(self) -> None:
        config = GraphConfig()
        assert config.max_iterations == 25

    def test_default_node_timeout(self) -> None:
        config = GraphConfig()
        assert config.node_timeout == 120.0

    def test_default_total_timeout(self) -> None:
        config = GraphConfig()
        assert config.total_timeout == 0.0

    def test_default_checkpoint_enabled(self) -> None:
        config = GraphConfig()
        assert config.checkpoint_enabled is False

    def test_default_parallel_branches(self) -> None:
        config = GraphConfig()
        assert config.parallel_branches is True

    def test_default_max_parallel_branches(self) -> None:
        config = GraphConfig()
        assert config.max_parallel_branches == 0


class TestGraphConfigValidation:
    """Tests for GraphConfig field validation."""

    def test_max_iterations_must_be_at_least_one(self) -> None:
        with pytest.raises(ValueError):
            GraphConfig(max_iterations=0)

    def test_node_timeout_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError):
            GraphConfig(node_timeout=-1.0)

    def test_total_timeout_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError):
            GraphConfig(total_timeout=-1.0)

    def test_max_parallel_branches_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError):
            GraphConfig(max_parallel_branches=-1)


class TestGraphConfigCustomValues:
    """Tests for GraphConfig with custom values."""

    def test_custom_enabled(self) -> None:
        config = GraphConfig(enabled=False)
        assert config.enabled is False

    def test_custom_max_iterations(self) -> None:
        config = GraphConfig(max_iterations=50)
        assert config.max_iterations == 50

    def test_custom_node_timeout(self) -> None:
        config = GraphConfig(node_timeout=300.0)
        assert config.node_timeout == 300.0

    def test_custom_total_timeout(self) -> None:
        config = GraphConfig(total_timeout=3600.0)
        assert config.total_timeout == 3600.0

    def test_custom_checkpoint_enabled(self) -> None:
        config = GraphConfig(checkpoint_enabled=True)
        assert config.checkpoint_enabled is True

    def test_custom_parallel_branches(self) -> None:
        config = GraphConfig(parallel_branches=False)
        assert config.parallel_branches is False

    def test_custom_max_parallel_branches(self) -> None:
        config = GraphConfig(max_parallel_branches=10)
        assert config.max_parallel_branches == 10


class TestGraphConfigValidationMethod:
    """Tests for GraphConfig.validate_for_environment."""

    def test_validate_for_environment_returns_empty_list(self) -> None:
        config = GraphConfig()
        issues = config.validate_for_environment()
        assert issues == []

    def test_validate_for_environment_with_env_param(self) -> None:
        config = GraphConfig()
        issues = config.validate_for_environment(env=None)
        assert issues == []


class TestConfigExports:
    """Tests to verify __all__ exports."""

    def test_all_contains_bulk_operation_config(self) -> None:
        from quadkit.workflow import config as config_module

        assert "BulkOperationConfig" in config_module.__all__

    def test_all_contains_graph_config(self) -> None:
        from quadkit.workflow import config as config_module

        assert "GraphConfig" in config_module.__all__