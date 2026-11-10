"""Unit tests for graph exception hierarchy."""

from __future__ import annotations

import pytest

from quadkit.workflow.exceptions import (
    CycleDetectedError,
    GraphExecutionError,
    GraphTimeoutError,
    GraphValidationError,
    HumanInputRequiredError,
    NodeExecutionError,
)


class TestGraphExecutionErrorHierarchy:
    def test_node_execution_error_is_graph_execution_error(self) -> None:
        err = NodeExecutionError("failed", node="some_node")
        assert isinstance(err, GraphExecutionError)

    def test_cycle_detected_error_is_graph_execution_error(self) -> None:
        err = CycleDetectedError(10, node="loop_node")
        assert isinstance(err, GraphExecutionError)

    def test_graph_timeout_error_is_graph_execution_error(self) -> None:
        err = GraphTimeoutError(30.0)
        assert isinstance(err, GraphExecutionError)

    def test_graph_validation_error_is_graph_execution_error(self) -> None:
        err = GraphValidationError("no entry node")
        assert isinstance(err, GraphExecutionError)

    def test_human_input_required_is_graph_execution_error(self) -> None:
        err = HumanInputRequiredError("Please confirm.", node="ask")
        assert isinstance(err, GraphExecutionError)

    def test_all_errors_are_exceptions(self) -> None:
        for exc_class in (
            GraphExecutionError,
            NodeExecutionError,
            CycleDetectedError,
            GraphTimeoutError,
            GraphValidationError,
            HumanInputRequiredError,
        ):
            assert issubclass(exc_class, Exception)


class TestGraphExecutionError:
    def test_message_stored(self) -> None:
        err = GraphExecutionError("test message")
        assert err.message == "test message"

    def test_node_attribute_defaults_to_none(self) -> None:
        err = GraphExecutionError("test")
        assert err.node is None

    def test_node_attribute_stored_when_provided(self) -> None:
        err = GraphExecutionError("test", node="my_node")
        assert err.node == "my_node"


class TestNodeExecutionError:
    def test_message_and_node_stored(self) -> None:
        err = NodeExecutionError("execution failed", node="worker")
        assert "execution failed" in str(err)
        assert err.node == "worker"

    def test_cause_stored(self) -> None:
        original = ValueError("db error")
        err = NodeExecutionError("wrapped", node="n", cause=original)
        assert err.__cause__ is original

    def test_cause_defaults_to_none(self) -> None:
        err = NodeExecutionError("msg")
        assert err.__cause__ is None


class TestCycleDetectedError:
    def test_iterations_attribute_stored(self) -> None:
        err = CycleDetectedError(7, node="loop")
        assert err.iterations == 7

    def test_node_attribute_stored(self) -> None:
        err = CycleDetectedError(7, node="loop")
        assert err.node == "loop"

    def test_message_omits_iteration_and_node_details(self) -> None:
        err = CycleDetectedError(12, node="private-cycle-node")
        assert err.message == "Workflow exceeded the maximum iteration limit."
        assert "12" not in err.message
        assert "private-cycle-node" not in err.message

    def test_node_defaults_to_none(self) -> None:
        err = CycleDetectedError(5)
        assert err.node is None


class TestGraphTimeoutError:
    def test_timeout_stored(self) -> None:
        err = GraphTimeoutError(60.0)
        assert err.timeout == 60.0

    def test_message_contains_timeout_value(self) -> None:
        err = GraphTimeoutError(45.0)
        assert "45" in str(err)


class TestHumanInputRequiredError:
    def test_prompt_stored(self) -> None:
        err = HumanInputRequiredError("Please review this request.", node="review")
        assert err.prompt == "Please review this request."

    def test_node_stored(self) -> None:
        err = HumanInputRequiredError("prompt", node="approver")
        assert err.node == "approver"

    def test_checkpoint_id_stored(self) -> None:
        err = HumanInputRequiredError("prompt", node="n", checkpoint_id="cp-123")
        assert err.checkpoint_id == "cp-123"

    def test_checkpoint_id_defaults_to_none(self) -> None:
        err = HumanInputRequiredError("prompt", node="n")
        assert err.checkpoint_id is None

    def test_message_omits_prompt_and_node(self) -> None:
        err = HumanInputRequiredError("private prompt", node="private_node")
        assert err.message == "Human input is required."
        assert "private prompt" not in err.message
        assert "private_node" not in err.message


class TestGraphValidationError:
    def test_message_stored(self) -> None:
        err = GraphValidationError("Entry node missing")
        assert "Entry node missing" in str(err)

    def test_node_attribute_optional(self) -> None:
        err = GraphValidationError("bad graph", node="bad_node")
        assert err.node == "bad_node"
