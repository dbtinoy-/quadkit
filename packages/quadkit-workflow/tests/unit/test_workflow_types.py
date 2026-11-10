"""Unit tests for quadkit.workflow.types module."""

from __future__ import annotations

import pytest

from quadkit.workflow.types import (
    GraphResult,
    NodeResult,
    SagaStep,
    StepExecutionResult,
    StepStatus,
)


class TestNodeResult:
    """Tests for NodeResult dataclass."""

    def test_node_result_basic_attributes(self) -> None:
        """Test NodeResult creates with required attributes."""
        result = NodeResult(node_name="test_node", output={"key": "value"})
        assert result.node_name == "test_node"
        assert result.output == {"key": "value"}
        assert result.duration_ms == 0.0
        assert result.error is None
        assert result.skipped is False

    def test_node_result_all_attributes(self) -> None:
        """Test NodeResult creates with all attributes."""
        result = NodeResult(
            node_name="test_node",
            output={"data": 42},
            duration_ms=150.5,
            error="some error",
            skipped=True,
        )
        assert result.node_name == "test_node"
        assert result.output == {"data": 42}
        assert result.duration_ms == 150.5
        assert result.error == "some error"
        assert result.skipped is True

    def test_node_result_succeeded_true(self) -> None:
        """Test succeeded property returns True when node succeeds."""
        result = NodeResult(node_name="ok_node", output={})
        assert result.succeeded is True

    def test_node_result_succeeded_false_error(self) -> None:
        """Test succeeded property returns False when error present."""
        result = NodeResult(node_name="fail_node", output={}, error="failed")
        assert result.succeeded is False

    def test_node_result_succeeded_false_skipped(self) -> None:
        """Test succeeded property returns False when skipped."""
        result = NodeResult(node_name="skip_node", output={}, skipped=True)
        assert result.succeeded is False

    def test_node_result_frozen(self) -> None:
        """Test NodeResult is frozen (immutable)."""
        result = NodeResult(node_name="test", output={})
        with pytest.raises(AttributeError):
            result.node_name = "changed"


class TestGraphResult:
    """Tests for GraphResult dataclass."""

    def test_graph_result_basic_attributes(self) -> None:
        """Test GraphResult creates with required attributes."""
        result = GraphResult(final_state={"output": "done"})
        assert result.final_state == {"output": "done"}
        assert result.node_results == []
        assert result.iterations == 0
        assert result.duration_ms == 0.0
        assert result.terminated_at is None

    def test_graph_result_all_attributes(self) -> None:
        """Test GraphResult creates with all attributes."""
        node_results = [
            NodeResult(node_name="a", output={"a": 1}),
            NodeResult(node_name="b", output={"b": 2}),
        ]
        result = GraphResult(
            final_state={"result": "ok"},
            node_results=node_results,
            iterations=5,
            duration_ms=500.0,
            terminated_at="b",
        )
        assert result.final_state == {"result": "ok"}
        assert len(result.node_results) == 2
        assert result.iterations == 5
        assert result.duration_ms == 500.0
        assert result.terminated_at == "b"

    def test_graph_result_output_property(self) -> None:
        """Test output property returns output key from final_state."""
        result = GraphResult(final_state={"output": "my_output", "extra": 1})
        assert result.output == "my_output"

    def test_graph_result_output_property_none(self) -> None:
        """Test output property returns None when output key missing."""
        result = GraphResult(final_state={})
        assert result.output is None

    def test_graph_result_succeeded_true(self) -> None:
        """Test succeeded property returns True when all nodes succeed."""
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(node_name="a", output={}),
                NodeResult(node_name="b", output={}),
            ],
        )
        assert result.succeeded is True

    def test_graph_result_succeeded_false(self) -> None:
        """Test succeeded property returns False when nodes fail."""
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(node_name="a", output={}),
                NodeResult(node_name="b", output={}, error="failed"),
            ],
        )
        assert result.succeeded is False

    def test_graph_result_succeeded_skipped_not_counted(self) -> None:
        """Test succeeded ignores skipped nodes (only counts executed)."""
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(node_name="a", output={}),
                NodeResult(node_name="b", output={}, skipped=True),
            ],
        )
        assert result.succeeded is True


class TestReExports:
    """Tests for re-exported types from contracts and primitives."""

    def test_saga_step_re_exported(self) -> None:
        """Test SagaStep is re-exported from contracts."""
        assert SagaStep is not None

    def test_step_execution_result_re_exported(self) -> None:
        """Test StepExecutionResult is re-exported from primitives."""
        assert StepExecutionResult is not None

    def test_step_status_re_exported(self) -> None:
        """Test StepStatus is re-exported from primitives."""
        assert StepStatus is not None


class TestStepStatus:
    """Tests for StepStatus enum."""

    def test_step_status_values(self) -> None:
        """Test StepStatus enum has expected values."""
        assert StepStatus.PENDING == "pending"
        assert StepStatus.RUNNING == "running"
        assert StepStatus.COMPLETED == "completed"
        assert StepStatus.FAILED == "failed"
        assert StepStatus.SKIPPED == "skipped"

    def test_step_status_from_string(self) -> None:
        """Test StepStatus can be constructed from string."""
        assert StepStatus("completed") == StepStatus.COMPLETED