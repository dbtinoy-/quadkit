"""Unit tests for quadkit.workflow.constants module."""

from __future__ import annotations

import pytest

from quadkit.workflow import constants


class TestBulkOperationConstants:
    """Tests for bulk operation constants."""

    def test_default_bulk_batch_size(self) -> None:
        """Test DEFAULT_BULK_BATCH_SIZE is 100."""
        assert constants.DEFAULT_BULK_BATCH_SIZE == 100

    def test_default_bulk_batch_size_is_int(self) -> None:
        """Test DEFAULT_BULK_BATCH_SIZE is an integer."""
        assert isinstance(constants.DEFAULT_BULK_BATCH_SIZE, int)

    def test_default_bulk_concurrency(self) -> None:
        """Test DEFAULT_BULK_CONCURRENCY is 10."""
        assert constants.DEFAULT_BULK_CONCURRENCY == 10

    def test_default_bulk_concurrency_is_int(self) -> None:
        """Test DEFAULT_BULK_CONCURRENCY is an integer."""
        assert isinstance(constants.DEFAULT_BULK_CONCURRENCY, int)

    def test_default_bulk_timeout(self) -> None:
        """Test DEFAULT_BULK_TIMEOUT is 300.0 seconds."""
        assert constants.DEFAULT_BULK_TIMEOUT == 300.0

    def test_default_bulk_timeout_is_float(self) -> None:
        """Test DEFAULT_BULK_TIMEOUT is a float."""
        assert isinstance(constants.DEFAULT_BULK_TIMEOUT, float)

    def test_default_pipeline_timeout(self) -> None:
        """Test DEFAULT_PIPELINE_TIMEOUT is 60.0 seconds."""
        assert constants.DEFAULT_PIPELINE_TIMEOUT == 60.0

    def test_default_pipeline_timeout_is_float(self) -> None:
        """Test DEFAULT_PIPELINE_TIMEOUT is a float."""
        assert isinstance(constants.DEFAULT_PIPELINE_TIMEOUT, float)


class TestGraphEngineConstants:
    """Tests for graph engine constants."""

    def test_default_graph_max_iterations(self) -> None:
        """Test DEFAULT_GRAPH_MAX_ITERATIONS is 25."""
        assert constants.DEFAULT_GRAPH_MAX_ITERATIONS == 25

    def test_default_graph_max_iterations_is_int(self) -> None:
        """Test DEFAULT_GRAPH_MAX_ITERATIONS is an integer."""
        assert isinstance(constants.DEFAULT_GRAPH_MAX_ITERATIONS, int)

    def test_default_graph_node_timeout(self) -> None:
        """Test DEFAULT_GRAPH_NODE_TIMEOUT is 120.0 seconds."""
        assert constants.DEFAULT_GRAPH_NODE_TIMEOUT == 120.0

    def test_default_graph_node_timeout_is_float(self) -> None:
        """Test DEFAULT_GRAPH_NODE_TIMEOUT is a float."""
        assert isinstance(constants.DEFAULT_GRAPH_NODE_TIMEOUT, float)

    def test_graph_env_prefix(self) -> None:
        """Test GRAPH_ENV_PREFIX is correct prefix."""
        assert constants.GRAPH_ENV_PREFIX == "QK_WORKFLOW__GRAPH__"

    def test_graph_env_prefix_is_string(self) -> None:
        """Test GRAPH_ENV_PREFIX is a string."""
        assert isinstance(constants.GRAPH_ENV_PREFIX, str)

    def test_graph_env_prefix_format(self) -> None:
        """Test GRAPH_ENV_PREFIX follows naming convention."""
        assert constants.GRAPH_ENV_PREFIX.startswith("QK_")
        assert constants.GRAPH_ENV_PREFIX.endswith("__")


class TestVersion:
    """Tests for version constant."""

    def test_version_is_string(self) -> None:
        """Test __version__ is a string."""
        assert isinstance(constants.__version__, str)

    def test_version_format(self) -> None:
        """Test __version__ follows semver-like format."""
        parts = constants.__version__.split(".")
        assert len(parts) >= 3


class TestAllExports:
    """Tests for __all__ exports."""

    def test_all_exports_contains_expected_names(self) -> None:
        """Test __all__ contains all expected constant names."""
        expected = [
            "DEFAULT_BULK_BATCH_SIZE",
            "DEFAULT_BULK_CONCURRENCY",
            "DEFAULT_BULK_TIMEOUT",
            "DEFAULT_GRAPH_MAX_ITERATIONS",
            "DEFAULT_GRAPH_NODE_TIMEOUT",
            "DEFAULT_PIPELINE_TIMEOUT",
            "GRAPH_ENV_PREFIX",
        ]
        for name in expected:
            assert name in constants.__all__

    def test_all_exports_count(self) -> None:
        """Test __all__ contains expected number of entries."""
        assert len(constants.__all__) == 7