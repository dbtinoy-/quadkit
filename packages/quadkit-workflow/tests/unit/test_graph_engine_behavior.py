"""Engine validation, properties, failure, and timeout tests."""

from __future__ import annotations

import pytest

from quadkit.workflow.config import GraphConfig
from quadkit.workflow.exceptions import (
    CycleDetectedError,
    GraphValidationError,
    HumanInputRequiredError,
    NodeExecutionError,
)
from quadkit.workflow.graph.edge import WorkflowEdge
from quadkit.workflow.graph.engine import WorkflowEngine
from quadkit.workflow.nodes.human_node import HumanNode
from quadkit.workflow.nodes.subworkflow_node import SubworkflowNode

from graph_helpers import AppendNode, ConstantNode, CounterNode, EchoNode, SlowNode

# ---------------------------------------------------------------------------
# Linear execution
# ---------------------------------------------------------------------------



class TestWorkflowEngineValidation:
    def test_validate_raises_when_entry_node_not_registered(self) -> None:
        engine = WorkflowEngine(
            name="invalid",
            nodes={"a": EchoNode("a")},
            edges=[],
            entry_node="nonexistent",
            terminal_conditions={"a": None},
        )
        with pytest.raises(GraphValidationError):
            engine.validate()

    def test_validate_raises_when_terminal_node_not_registered(self) -> None:
        engine = WorkflowEngine(
            name="invalid",
            nodes={"a": EchoNode("a")},
            edges=[],
            entry_node="a",
            terminal_conditions={"ghost": None},
        )
        with pytest.raises(GraphValidationError):
            engine.validate()

    def test_validate_raises_when_edge_source_not_registered(self) -> None:
        engine = WorkflowEngine(
            name="invalid",
            nodes={"b": EchoNode("b")},
            edges=[WorkflowEdge(source="missing", target="b")],
            entry_node="b",
            terminal_conditions={"b": None},
        )
        with pytest.raises(GraphValidationError):
            engine.validate()

    def test_validate_raises_when_edge_target_not_registered(self) -> None:
        engine = WorkflowEngine(
            name="invalid",
            nodes={"a": EchoNode("a")},
            edges=[WorkflowEdge(source="a", target="missing")],
            entry_node="a",
            terminal_conditions={"a": None},
        )
        with pytest.raises(GraphValidationError):
            engine.validate()

    def test_validate_passes_for_valid_single_node_workflow(self) -> None:
        engine = WorkflowEngine(
            name="solo",
            nodes={"only": EchoNode("only")},
            edges=[],
            entry_node="only",
            terminal_conditions={"only": None},
        )
        engine.validate()  # must not raise


# ---------------------------------------------------------------------------
# Engine properties
# ---------------------------------------------------------------------------


class TestWorkflowEngineProperties:
    def test_name_property_returns_engine_name(self) -> None:
        engine = WorkflowEngine(
            name="my_workflow",
            nodes={"a": EchoNode("a")},
            edges=[],
            entry_node="a",
            terminal_conditions={"a": None},
        )
        assert engine.name == "my_workflow"


# ---------------------------------------------------------------------------
# Node execution failures
# ---------------------------------------------------------------------------


class TestNodeExecutionFailure:
    @pytest.mark.asyncio
    async def test_failing_node_raises_node_execution_error(self) -> None:
        from graph_helpers import FailingNode

        nodes = {"bad": FailingNode("bad", message="test failure")}
        engine = WorkflowEngine(
            name="fail_test",
            nodes=nodes,
            edges=[],
            entry_node="bad",
            terminal_conditions={"bad": None},
        )
        with pytest.raises(NodeExecutionError) as exc_info:
            await engine.execute("test")
        assert exc_info.value.message == "Workflow node execution failed."
        assert "test failure" not in exc_info.value.message

    @pytest.mark.asyncio
    async def test_node_execution_error_carries_node_name(self) -> None:
        from graph_helpers import FailingNode

        nodes = {"broken": FailingNode("broken")}
        engine = WorkflowEngine(
            name="broken_workflow",
            nodes=nodes,
            edges=[],
            entry_node="broken",
            terminal_conditions={"broken": None},
        )
        with pytest.raises(NodeExecutionError) as exc_info:
            await engine.execute("test")
        assert exc_info.value.node == "broken"


# ---------------------------------------------------------------------------
# Node timeout
# ---------------------------------------------------------------------------


class TestNodeTimeout:
    @pytest.mark.asyncio
    async def test_slow_node_returns_err_when_node_timeout_exceeded(self) -> None:
        nodes = {"slow": SlowNode("slow", delay=5.0)}
        engine = WorkflowEngine(
            name="timeout_test",
            nodes=nodes,
            edges=[],
            entry_node="slow",
            terminal_conditions={"slow": None},
            config=GraphConfig(node_timeout=0.01),
        )
        with pytest.raises(NodeExecutionError) as exc_info:
            await engine.execute("test")
        assert "timed out" in str(exc_info.value).lower()
