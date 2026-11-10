"""Unit tests for WorkflowEdge directed edge with conditional activation."""

from __future__ import annotations

import pytest

from quadkit.workflow.graph.edge import WorkflowEdge


class TestWorkflowEdgeActivation:
    def test_unconditional_edge_is_always_active(self) -> None:
        edge = WorkflowEdge(source="a", target="b")
        assert edge.is_active({}) is True
        assert edge.is_active({"any": "state"}) is True

    def test_conditional_edge_active_when_condition_true(self) -> None:
        edge = WorkflowEdge(
            source="a",
            target="b",
            condition=lambda s: s.get("go") is True,
        )
        assert edge.is_active({"go": True}) is True

    def test_conditional_edge_inactive_when_condition_false(self) -> None:
        edge = WorkflowEdge(
            source="a",
            target="b",
            condition=lambda s: s.get("go") is True,
        )
        assert edge.is_active({"go": False}) is False
        assert edge.is_active({}) is False

    def test_condition_raising_key_error_returns_false(self) -> None:
        edge = WorkflowEdge(
            source="a",
            target="b",
            condition=lambda s: s["missing_key"] == "x",
        )
        assert edge.is_active({}) is False

    def test_condition_raising_type_error_returns_false(self) -> None:
        edge = WorkflowEdge(
            source="a",
            target="b",
            condition=lambda s: None > 0,  # type: ignore[operator]
        )
        assert edge.is_active({}) is False

    def test_condition_raising_attribute_error_returns_false(self) -> None:
        edge = WorkflowEdge(
            source="a",
            target="b",
            condition=lambda s: s.get("val").upper() == "X",  # type: ignore[union-attr]
        )
        assert edge.is_active({}) is False

    def test_condition_raising_value_error_returns_false(self) -> None:
        edge = WorkflowEdge(
            source="a",
            target="b",
            condition=lambda s: int("not-a-number") == 1,
        )
        assert edge.is_active({}) is False


class TestWorkflowEdgeImmutability:
    def test_edge_is_frozen(self) -> None:
        edge = WorkflowEdge(source="a", target="b")
        with pytest.raises((AttributeError, TypeError)):
            edge.source = "x"  # type: ignore[misc]

    def test_edge_equality_by_source_target(self) -> None:
        e1 = WorkflowEdge(source="a", target="b")
        e2 = WorkflowEdge(source="a", target="b")
        assert e1 == e2

    def test_edge_equality_ignores_condition(self) -> None:
        e1 = WorkflowEdge(source="a", target="b", condition=lambda s: True)
        e2 = WorkflowEdge(source="a", target="b", condition=lambda s: False)
        assert e1 == e2

    def test_edge_inequality_different_target(self) -> None:
        e1 = WorkflowEdge(source="a", target="b")
        e2 = WorkflowEdge(source="a", target="c")
        assert e1 != e2


class TestWorkflowEdgeAttributes:
    def test_source_and_target_stored(self) -> None:
        edge = WorkflowEdge(source="start", target="end")
        assert edge.source == "start"
        assert edge.target == "end"

    def test_label_defaults_to_empty_string(self) -> None:
        edge = WorkflowEdge(source="a", target="b")
        assert edge.label == ""

    def test_label_stored_when_provided(self) -> None:
        edge = WorkflowEdge(source="a", target="b", label="success_path")
        assert edge.label == "success_path"

    def test_is_parallel_defaults_to_false(self) -> None:
        edge = WorkflowEdge(source="a", target="b")
        assert edge.is_parallel is False

    def test_is_parallel_can_be_set(self) -> None:
        edge = WorkflowEdge(source="a", target="b", is_parallel=True)
        assert edge.is_parallel is True
