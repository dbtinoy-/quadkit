"""Human-in-the-loop and sub-workflow tests."""

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



class TestHumanInTheLoop:
    @pytest.mark.asyncio
    async def test_raises_human_input_required(
        self, human_in_loop_engine: WorkflowEngine
    ) -> None:
        with pytest.raises(HumanInputRequiredError):
            await human_in_loop_engine.execute("ask me something")

    @pytest.mark.asyncio
    async def test_human_input_required_carries_node_name(
        self, human_in_loop_engine: WorkflowEngine
    ) -> None:
        with pytest.raises(HumanInputRequiredError) as exc_info:
            await human_in_loop_engine.execute("test")
        assert exc_info.value.node == "human"

    @pytest.mark.asyncio
    async def test_human_input_required_carries_rendered_prompt(
        self, human_in_loop_engine: WorkflowEngine
    ) -> None:
        with pytest.raises(HumanInputRequiredError) as exc_info:
            await human_in_loop_engine.execute("find_something")
        assert "find_something" in exc_info.value.prompt

    @pytest.mark.asyncio
    async def test_resume_continues_to_terminal(
        self, human_in_loop_engine: WorkflowEngine
    ) -> None:
        checkpoint_state = {
            "input": "test",
            "_paused_at": "human",
            "human_response": "my answer",
        }
        result = await human_in_loop_engine.resume(checkpoint_state, "my answer")
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_resume_injects_human_response_into_state(
        self, human_in_loop_engine: WorkflowEngine
    ) -> None:
        checkpoint_state = {
            "input": "test",
            "_paused_at": "human",
        }
        result = await human_in_loop_engine.resume(checkpoint_state, "operator_answer")
        assert result.is_ok()
        wf = result.unwrap()
        assert wf.final_state.get("human_response") == "operator_answer"

    @pytest.mark.asyncio
    async def test_resume_workflow_reaches_terminal(
        self, human_in_loop_engine: WorkflowEngine
    ) -> None:
        checkpoint_state = {"input": "test", "_paused_at": "human"}
        result = await human_in_loop_engine.resume(checkpoint_state, "yes")
        assert result.is_ok()
        wf = result.unwrap()
        assert wf.terminated_at == "end"

    @pytest.mark.asyncio
    async def test_direct_execute_with_human_response_in_state_skips_pause(
        self, human_in_loop_engine: WorkflowEngine
    ) -> None:
        result = await human_in_loop_engine.execute(
            "test", state={"human_response": "pre-answered"}
        )
        assert result.is_ok()
        wf = result.unwrap()
        assert wf.final_state.get("human_response") == "pre-answered"


# ---------------------------------------------------------------------------
# Sub-workflows
# ---------------------------------------------------------------------------


class TestSubWorkflow:
    @pytest.mark.asyncio
    async def test_subworkflow_is_visited_in_outer_node_results(self) -> None:
        inner_nodes = {
            "inner_a": ConstantNode("inner_a", inner_result="done", output="inner_out"),
        }
        inner_engine = WorkflowEngine(
            name="inner",
            nodes=inner_nodes,
            edges=[],
            entry_node="inner_a",
            terminal_conditions={"inner_a": None},
        )
        outer_nodes = {
            "start": ConstantNode("start", output="outer_start"),
            "sub": SubworkflowNode("sub", workflow=inner_engine),
            "end": ConstantNode("end", output="outer_end"),
        }
        outer_edges = [
            WorkflowEdge(source="start", target="sub"),
            WorkflowEdge(source="sub", target="end"),
        ]
        outer_engine = WorkflowEngine(
            name="outer",
            nodes=outer_nodes,
            edges=outer_edges,
            entry_node="start",
            terminal_conditions={"end": None},
        )
        result = await outer_engine.execute("parent_input")
        assert result.is_ok()
        names = [r.node_name for r in result.unwrap().node_results]
        assert names == ["start", "sub", "end"]

    @pytest.mark.asyncio
    async def test_subworkflow_output_stored_in_outer_state(self) -> None:
        inner_nodes = {"calc": ConstantNode("calc", output="inner_result_value")}
        inner_engine = WorkflowEngine(
            name="inner_calc",
            nodes=inner_nodes,
            edges=[],
            entry_node="calc",
            terminal_conditions={"calc": None},
        )
        outer_nodes = {
            "sub": SubworkflowNode("sub", workflow=inner_engine, output_key="sub_out"),
            "terminal": ConstantNode("terminal", output="done"),
        }
        outer_engine = WorkflowEngine(
            name="outer_calc",
            nodes=outer_nodes,
            edges=[WorkflowEdge(source="sub", target="terminal")],
            entry_node="sub",
            terminal_conditions={"terminal": None},
        )
        result = await outer_engine.execute("test")
        assert result.is_ok()
        wf = result.unwrap()
        assert wf.final_state.get("sub_out") == "inner_result_value"

    @pytest.mark.asyncio
    async def test_nested_subworkflow_returns_ok_on_inner_failure(self) -> None:
        class _FailEngine:
            name = "fail_inner"

            async def execute(self, input_: str, *, state=None) -> object:
                from quadkit.result import Err as ErrT

                return ErrT(RuntimeError("inner boom"))

        outer_nodes = {
            "sub": SubworkflowNode("sub", workflow=_FailEngine(), output_key="sub_result"),
            "end": ConstantNode("end", output="ok"),
        }
        outer_engine = WorkflowEngine(
            name="outer_fail",
            nodes=outer_nodes,
            edges=[WorkflowEdge(source="sub", target="end")],
            entry_node="sub",
            terminal_conditions={"end": None},
        )
        result = await outer_engine.execute("test")
        assert result.is_ok()
        wf = result.unwrap()
        assert (
            wf.final_state.get("sub_result", "") == "Subworkflow execution failed."
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


