"""Unit tests for NodeResult and GraphResult value objects."""

from __future__ import annotations

import pytest

from quadkit.workflow.types import GraphResult, NodeResult


class TestNodeResult:
    def test_succeeded_true_when_no_error_and_not_skipped(self) -> None:
        result = NodeResult(node_name="a", output={"out": "val"})
        assert result.succeeded is True

    def test_succeeded_false_when_error_set(self) -> None:
        result = NodeResult(node_name="a", output={}, error="something failed")
        assert result.succeeded is False

    def test_succeeded_false_when_skipped(self) -> None:
        result = NodeResult(node_name="a", output={}, skipped=True)
        assert result.succeeded is False

    def test_error_is_none_by_default(self) -> None:
        result = NodeResult(node_name="a", output={})
        assert result.error is None

    def test_duration_ms_defaults_to_zero(self) -> None:
        result = NodeResult(node_name="a", output={})
        assert result.duration_ms == 0.0

    def test_duration_ms_stored(self) -> None:
        result = NodeResult(node_name="a", output={}, duration_ms=123.45)
        assert result.duration_ms == 123.45

    def test_node_name_stored(self) -> None:
        result = NodeResult(node_name="my_node", output={})
        assert result.node_name == "my_node"

    def test_output_stored(self) -> None:
        result = NodeResult(node_name="a", output={"key": "value"})
        assert result.output["key"] == "value"

    def test_is_frozen(self) -> None:
        result = NodeResult(node_name="a", output={})
        with pytest.raises((AttributeError, TypeError)):
            result.node_name = "mutated"  # type: ignore[misc]


class TestGraphResult:
    def test_output_returns_final_state_output_key(self) -> None:
        result = GraphResult(
            final_state={"output": "my_output"},
            iterations=1,
        )
        assert result.output == "my_output"

    def test_output_returns_none_when_not_in_state(self) -> None:
        result = GraphResult(final_state={})
        assert result.output is None

    def test_succeeded_true_when_all_nodes_succeeded(self) -> None:
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(node_name="a", output={}),
                NodeResult(node_name="b", output={}),
            ],
        )
        assert result.succeeded is True

    def test_succeeded_false_when_any_node_has_error(self) -> None:
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(node_name="a", output={}),
                NodeResult(node_name="b", output={}, error="failed"),
            ],
        )
        assert result.succeeded is False

    def test_succeeded_true_with_skipped_nodes(self) -> None:
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(node_name="a", output={}),
                NodeResult(node_name="b", output={}, skipped=True),
            ],
        )
        assert result.succeeded is True

    def test_iterations_stored(self) -> None:
        result = GraphResult(final_state={}, iterations=5)
        assert result.iterations == 5

    def test_duration_ms_stored(self) -> None:
        result = GraphResult(final_state={}, duration_ms=250.0)
        assert result.duration_ms == 250.0

    def test_terminated_at_stored(self) -> None:
        result = GraphResult(final_state={}, terminated_at="final_node")
        assert result.terminated_at == "final_node"

    def test_node_results_default_empty(self) -> None:
        result = GraphResult(final_state={})
        assert result.node_results == []

    def test_final_state_accessible(self) -> None:
        result = GraphResult(final_state={"a": 1, "b": 2})
        assert result.final_state["a"] == 1
        assert result.final_state["b"] == 2
