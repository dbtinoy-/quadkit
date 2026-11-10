"""Linear, conditional, parallel, and cycle-detection flow tests."""

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



class TestLinearWorkflow:
    @pytest.mark.asyncio
    async def test_linear_executes_all_three_nodes(
        self, linear_engine: WorkflowEngine
    ) -> None:
        result = await linear_engine.execute("start")
        assert result.is_ok()
        wf = result.unwrap()
        assert wf.final_state["path"] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_linear_node_results_ordered(
        self, linear_engine: WorkflowEngine
    ) -> None:
        result = await linear_engine.execute("start")
        assert result.is_ok()
        wf = result.unwrap()
        names = [r.node_name for r in wf.node_results]
        assert names == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_linear_all_node_results_succeeded(
        self, linear_engine: WorkflowEngine
    ) -> None:
        result = await linear_engine.execute("start")
        assert result.is_ok()
        wf = result.unwrap()
        assert all(r.succeeded for r in wf.node_results)

    @pytest.mark.asyncio
    async def test_linear_iterations_equals_node_count(
        self, linear_engine: WorkflowEngine
    ) -> None:
        result = await linear_engine.execute("start")
        assert result.is_ok()
        wf = result.unwrap()
        assert wf.iterations == 3

    @pytest.mark.asyncio
    async def test_linear_terminated_at_last_node(
        self, linear_engine: WorkflowEngine
    ) -> None:
        result = await linear_engine.execute("start")
        assert result.is_ok()
        assert result.unwrap().terminated_at == "c"

    @pytest.mark.asyncio
    async def test_linear_input_available_in_state(
        self, linear_engine: WorkflowEngine
    ) -> None:
        result = await linear_engine.execute("my_input")
        assert result.is_ok()
        assert result.unwrap().final_state["input"] == "my_input"

    @pytest.mark.asyncio
    async def test_linear_initial_state_passed_in(
        self, linear_engine: WorkflowEngine
    ) -> None:
        result = await linear_engine.execute("x", state={"extra": "data"})
        assert result.is_ok()
        assert result.unwrap().final_state["extra"] == "data"


# ---------------------------------------------------------------------------
# Conditional branching
# ---------------------------------------------------------------------------


class TestConditionalBranching:
    @pytest.mark.asyncio
    async def test_routes_to_b_when_route_equals_b(
        self, conditional_engine: WorkflowEngine
    ) -> None:
        result = await conditional_engine.execute("test")
        assert result.is_ok()
        wf = result.unwrap()
        names = [r.node_name for r in wf.node_results]
        assert "b" in names
        assert "c" not in names

    @pytest.mark.asyncio
    async def test_does_not_visit_inactive_branch(
        self, conditional_engine: WorkflowEngine
    ) -> None:
        result = await conditional_engine.execute("test")
        assert result.is_ok()
        assert result.unwrap().final_state.get("result") == "branch_b"

    @pytest.mark.asyncio
    async def test_routes_to_c_when_preset_route_is_c(self) -> None:
        nodes = {
            "a": ConstantNode("a", route="c", output="a_done"),
            "b": ConstantNode("b", result="branch_b", output="b_done"),
            "c": ConstantNode("c", result="branch_c", output="c_done"),
        }
        edges = [
            WorkflowEdge(source="a", target="b", condition=lambda s: s.get("route") == "b"),
            WorkflowEdge(source="a", target="c", condition=lambda s: s.get("route") == "c"),
        ]
        engine = WorkflowEngine(
            name="cond_c",
            nodes=nodes,
            edges=edges,
            entry_node="a",
            terminal_conditions={"b": None, "c": None},
        )
        result = await engine.execute("test")
        assert result.is_ok()
        wf = result.unwrap()
        names = [r.node_name for r in wf.node_results]
        assert "c" in names
        assert "b" not in names

    @pytest.mark.asyncio
    async def test_no_active_edge_stops_at_implicit_terminal(self) -> None:
        nodes = {
            "a": ConstantNode("a", route="unknown", output="a"),
            "b": ConstantNode("b", output="b"),
        }
        edges = [
            WorkflowEdge(source="a", target="b", condition=lambda s: s.get("route") == "b"),
        ]
        engine = WorkflowEngine(
            name="no_active_edge",
            nodes=nodes,
            edges=edges,
            entry_node="a",
            terminal_conditions={"b": None},
        )
        result = await engine.execute("test")
        assert result.is_ok()
        names = [r.node_name for r in result.unwrap().node_results]
        assert names == ["a"]


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------


class TestParallelExecution:
    @pytest.mark.asyncio
    async def test_parallel_executes_both_branches(
        self, parallel_engine: WorkflowEngine
    ) -> None:
        result = await parallel_engine.execute("test")
        assert result.is_ok()
        names = [r.node_name for r in result.unwrap().node_results]
        assert "branch_a" in names
        assert "branch_b" in names

    @pytest.mark.asyncio
    async def test_parallel_executes_start_node_first(
        self, parallel_engine: WorkflowEngine
    ) -> None:
        result = await parallel_engine.execute("test")
        assert result.is_ok()
        names = [r.node_name for r in result.unwrap().node_results]
        assert names[0] == "start"

    @pytest.mark.asyncio
    async def test_parallel_branch_a_state_merged(
        self, parallel_engine: WorkflowEngine
    ) -> None:
        result = await parallel_engine.execute("test")
        assert result.is_ok()
        final_state = result.unwrap().final_state
        assert final_state.get("branch_a") is True

    @pytest.mark.asyncio
    async def test_parallel_branch_b_state_merged(
        self, parallel_engine: WorkflowEngine
    ) -> None:
        result = await parallel_engine.execute("test")
        assert result.is_ok()
        final_state = result.unwrap().final_state
        assert final_state.get("branch_b") is True

    @pytest.mark.asyncio
    async def test_parallel_total_node_count(
        self, parallel_engine: WorkflowEngine
    ) -> None:
        result = await parallel_engine.execute("test")
        assert result.is_ok()
        assert len(result.unwrap().node_results) == 3


# ---------------------------------------------------------------------------
# Cycle detection / max_iterations guard
# ---------------------------------------------------------------------------


class TestCycleDetection:
    @pytest.mark.asyncio
    async def test_cyclic_workflow_raises_cycle_detected_error(
        self, cyclic_engine: WorkflowEngine
    ) -> None:
        with pytest.raises(CycleDetectedError):
            await cyclic_engine.execute("test")

    @pytest.mark.asyncio
    async def test_cycle_error_carries_iteration_count(
        self, cyclic_engine: WorkflowEngine
    ) -> None:
        with pytest.raises(CycleDetectedError) as exc_info:
            await cyclic_engine.execute("test")
        assert exc_info.value.iterations == 3

    @pytest.mark.asyncio
    async def test_cycle_error_carries_node_name(
        self, cyclic_engine: WorkflowEngine
    ) -> None:
        with pytest.raises(CycleDetectedError) as exc_info:
            await cyclic_engine.execute("test")
        assert exc_info.value.node is not None

    @pytest.mark.asyncio
    async def test_custom_max_iterations_respected(self) -> None:
        nodes = {
            "a": CounterNode("a"),
            "b": EchoNode("b"),
        }
        edges = [
            WorkflowEdge(source="a", target="b"),
            WorkflowEdge(source="b", target="a"),
        ]
        engine = WorkflowEngine(
            name="custom_cycle",
            nodes=nodes,
            edges=edges,
            entry_node="a",
            terminal_conditions={},
            config=GraphConfig(max_iterations=5),
        )
        with pytest.raises(CycleDetectedError) as exc_info:
            await engine.execute("test")
        assert exc_info.value.iterations == 5

    @pytest.mark.asyncio
    async def test_cycle_with_conditional_exit_terminates_normally(self) -> None:
        nodes = {
            "counter": CounterNode("counter"),
            "check": ConstantNode("check", output="check"),
            "done": ConstantNode("done", finished=True, output="done"),
        }
        edges = [
            WorkflowEdge(source="counter", target="check"),
            WorkflowEdge(
                source="check",
                target="counter",
                condition=lambda s: s.get("count", 0) < 3,
            ),
            WorkflowEdge(
                source="check",
                target="done",
                condition=lambda s: s.get("count", 0) >= 3,
            ),
        ]
        engine = WorkflowEngine(
            name="conditional_cycle",
            nodes=nodes,
            edges=edges,
            entry_node="counter",
            terminal_conditions={"done": None},
            config=GraphConfig(max_iterations=20),
        )
        result = await engine.execute("test")
        assert result.is_ok()
        wf = result.unwrap()
        assert wf.final_state["count"] >= 3
        assert wf.terminated_at == "done"


# ---------------------------------------------------------------------------
# Human-in-the-loop
# ---------------------------------------------------------------------------


