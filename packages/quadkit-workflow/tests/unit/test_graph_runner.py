"""Unit tests for WorkflowRunner retry harness."""

from __future__ import annotations

from typing import Any

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.workflow.exceptions import GraphExecutionError, HumanInputRequiredError
from quadkit.workflow.execution.runner import WorkflowRunner
from quadkit.workflow.graph.state import WorkflowState
from quadkit.workflow.types import GraphResult
from quadkit.result import Err, Ok

from graph_helpers import AppendNode, EchoNode
from quadkit.workflow.graph.engine import WorkflowEngine
from quadkit.workflow.graph.edge import WorkflowEdge
from quadkit.workflow.graph.node import AbstractWorkflowNode
from quadkit.workflow.nodes.human_node import HumanNode


def _make_simple_engine() -> WorkflowEngine:
    return WorkflowEngine(
        name="simple",
        nodes={"n": EchoNode("n")},
        edges=[],
        entry_node="n",
        terminal_conditions={"n": None},
    )


def _make_mock_result(output: str = "ok") -> GraphResult:
    return GraphResult(
        final_state={"output": output},
        iterations=1,
        duration_ms=1.0,
        terminated_at="n",
    )


class TestWorkflowRunnerSuccess:
    @pytest.mark.asyncio
    async def test_run_returns_ok_on_success(self) -> None:
        engine = _make_simple_engine()
        runner = WorkflowRunner(engine=engine, max_retries=0, retry_delay=0.0)
        result = await runner.run("test")
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_run_result_has_expected_output(self) -> None:
        engine = WorkflowEngine(
            name="echo",
            nodes={"e": EchoNode("e")},
            edges=[],
            entry_node="e",
            terminal_conditions={"e": None},
        )
        runner = WorkflowRunner(engine=engine, max_retries=0, retry_delay=0.0)
        result = await runner.run("hello")
        assert result.is_ok()
        assert result.unwrap().final_state["input"] == "hello"

    @pytest.mark.asyncio
    async def test_run_propagates_workflow_result(self) -> None:
        engine = WorkflowEngine(
            name="linear",
            nodes={"a": AppendNode("a"), "b": AppendNode("b")},
            edges=[WorkflowEdge(source="a", target="b")],
            entry_node="a",
            terminal_conditions={"b": None},
        )
        runner = WorkflowRunner(engine=engine, max_retries=0, retry_delay=0.0)
        result = await runner.run("test")
        assert result.is_ok()
        assert result.unwrap().final_state["path"] == ["a", "b"]


class TestWorkflowRunnerRetry:
    @pytest.mark.asyncio
    async def test_runner_retries_on_err_result(self) -> None:
        mock_engine = MagicMock()
        mock_engine.name = "mock"
        error_result = GraphExecutionError("temporary failure")
        mock_engine.execute = AsyncMock(
            side_effect=[
                Err(error_result),
                Ok(_make_mock_result("success")),
            ]
        )
        runner = WorkflowRunner(engine=mock_engine, max_retries=1, retry_delay=0.0)
        result = await runner.run("test")
        assert result.is_ok()
        assert mock_engine.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_runner_returns_err_when_all_retries_exhausted(self) -> None:
        mock_engine = MagicMock()
        mock_engine.name = "mock"
        error = GraphExecutionError("persistent failure")
        mock_engine.execute = AsyncMock(return_value=Err(error))
        runner = WorkflowRunner(engine=mock_engine, max_retries=2, retry_delay=0.0)
        result = await runner.run("test")
        assert result.is_err()
        assert mock_engine.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_runner_no_retries_returns_err_immediately(self) -> None:
        mock_engine = MagicMock()
        mock_engine.name = "mock"
        mock_engine.execute = AsyncMock(return_value=Err(GraphExecutionError("fail")))
        runner = WorkflowRunner(engine=mock_engine, max_retries=0, retry_delay=0.0)
        result = await runner.run("test")
        assert result.is_err()
        assert mock_engine.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_runner_succeeds_on_first_ok_without_retry(self) -> None:
        mock_engine = MagicMock()
        mock_engine.name = "mock"
        mock_engine.execute = AsyncMock(return_value=Ok(_make_mock_result()))
        runner = WorkflowRunner(engine=mock_engine, max_retries=3, retry_delay=0.0)
        result = await runner.run("test")
        assert result.is_ok()
        assert mock_engine.execute.call_count == 1


class TestWorkflowRunnerHumanInTheLoop:
    @pytest.mark.asyncio
    async def test_runner_propagates_human_input_required(self) -> None:
        from quadkit.workflow.nodes.human_node import HumanNode

        nodes = {"ask": HumanNode("ask", prompt="Please answer.")}
        engine = WorkflowEngine(
            name="hitl",
            nodes=nodes,
            edges=[],
            entry_node="ask",
            terminal_conditions={"ask": None},
        )
        runner = WorkflowRunner(engine=engine, max_retries=0, retry_delay=0.0)
        with pytest.raises(HumanInputRequiredError):
            await runner.run("test")

    @pytest.mark.asyncio
    async def test_runner_does_not_retry_human_input_required(self) -> None:
        mock_engine = MagicMock()
        mock_engine.name = "mock"
        mock_engine.execute = AsyncMock(
            side_effect=HumanInputRequiredError("Please answer.", node="ask")
        )
        runner = WorkflowRunner(engine=mock_engine, max_retries=3, retry_delay=0.0)
        with pytest.raises(HumanInputRequiredError):
            await runner.run("test")
        assert mock_engine.execute.call_count == 1


class TestWorkflowRunnerResume:
    @pytest.mark.asyncio
    async def test_resume_delegates_to_engine_without_mutating_state(self) -> None:
        """runner.resume must go through engine.resume (version guard +
        resume-from-paused-node) and must not mutate the caller's state."""
        mock_engine = MagicMock()
        mock_engine.name = "mock"
        mock_engine.resume = AsyncMock(return_value=Ok(_make_mock_result()))
        runner = WorkflowRunner(engine=mock_engine, max_retries=0, retry_delay=0.0)
        state = WorkflowState(input="orig")
        state["_paused_at"] = "ask"

        result = await runner.resume("operator_answer", state=state)

        assert result.is_ok()
        mock_engine.resume.assert_awaited_once()
        args, kwargs = mock_engine.resume.await_args
        # Passes a snapshot of the state, not the live object.
        assert args[0] is not state
        assert args[0].get("_paused_at") == "ask"
        assert args[0].get("input") == "orig"
        assert args[1] == "operator_answer"
        # No mutation of the caller's state.
        assert state.get("human_response") is None

    @pytest.mark.asyncio
    async def test_resume_forwards_explicit_response_key(self) -> None:
        mock_engine = MagicMock()
        mock_engine.name = "mock"
        mock_engine.resume = AsyncMock(return_value=Ok(_make_mock_result()))
        runner = WorkflowRunner(engine=mock_engine, max_retries=0, retry_delay=0.0)
        state = WorkflowState(input="orig")

        await runner.resume("my_answer", state=state, response_key="custom_key")

        _, kwargs = mock_engine.resume.await_args
        assert kwargs["response_key"] == "custom_key"

    @pytest.mark.asyncio
    async def test_resume_continues_from_paused_node(self) -> None:
        """End-to-end: a paused human node is resumed without re-running
        earlier steps (which would repeat their side effects)."""
        side_effects: list[str] = []

        class SideEffectNode(AbstractWorkflowNode):
            async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
                side_effects.append(self.name)
                return {"ran": self.name}

        nodes = {
            "first": SideEffectNode("first"),
            "ask": HumanNode("ask", prompt="Answer?"),
            "done": SideEffectNode("done"),
        }
        edges = [WorkflowEdge(source="first", target="ask"), WorkflowEdge(source="ask", target="done")]
        engine = WorkflowEngine(
            name="hitl-resume",
            nodes=nodes,
            edges=edges,
            entry_node="first",
            terminal_conditions={"done": None},
        )
        runner = WorkflowRunner(engine=engine, max_retries=0, retry_delay=0.0)

        # First run pauses at "ask" after "first" executed once.
        with pytest.raises(HumanInputRequiredError):
            await runner.run("go")
        assert side_effects == ["first"]

        # Rebuild state as the checkpoint would have stored it.
        paused_state = WorkflowState(input="go")
        paused_state["_paused_at"] = "ask"

        result = await runner.resume("yes", state=paused_state)
        assert result.is_ok()

        # "first" must NOT have re-run; "done" completed after "ask".
        assert side_effects == ["first", "done"]
