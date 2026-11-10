"""Unit tests for individual workflow node implementations."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.workflow.exceptions import HumanInputRequiredError
from graph_helpers import ConstantNode

from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType
from quadkit.workflow.nodes.gate_node import GateNode
from quadkit.workflow.nodes.human_node import HumanNode
from quadkit.workflow.graph.edge import WorkflowEdge
from quadkit.workflow.graph.engine import WorkflowEngine
from quadkit.workflow.nodes.subworkflow_node import SubworkflowNode


class TestAbstractNodeProperties:
    def test_name_property_returns_name(self) -> None:
        class MyNode(AbstractWorkflowNode):
            async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
                return {}

        node = MyNode("test_node")
        assert node.name == "test_node"

    def test_node_type_defaults_to_custom(self) -> None:
        class MyNode(AbstractWorkflowNode):
            async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
                return {}

        node = MyNode("n")
        assert node.node_type == NodeType.CUSTOM

    def test_node_type_stored_when_provided(self) -> None:
        class MyNode(AbstractWorkflowNode):
            async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
                return {}

        node = MyNode("n", NodeType.AGENT)
        assert node.node_type == NodeType.AGENT


class TestHumanNode:
    @pytest.mark.asyncio
    async def test_raises_human_input_required_when_no_response_in_state(self) -> None:
        node = HumanNode("ask", prompt="Please confirm.")
        with pytest.raises(HumanInputRequiredError) as exc_info:
            await node.execute({"input": "test"})
        assert exc_info.value.node == "ask"

    @pytest.mark.asyncio
    async def test_prompt_rendered_with_state_values(self) -> None:
        node = HumanNode("ask", prompt="Hello {user}, please confirm {action}.")
        with pytest.raises(HumanInputRequiredError) as exc_info:
            await node.execute({"user": "Alice", "action": "delete", "input": "test"})
        assert "Alice" in exc_info.value.prompt
        assert "delete" in exc_info.value.prompt

    @pytest.mark.asyncio
    async def test_returns_response_when_resume_key_present(self) -> None:
        node = HumanNode("ask", prompt="Confirm?", output_key="answer")
        result = await node.execute({"answer": "yes", "input": "test"})
        assert result == {"answer": "yes"}

    @pytest.mark.asyncio
    async def test_returns_none_response_does_not_bypass_pause(self) -> None:
        node = HumanNode("ask", prompt="Confirm?")
        with pytest.raises(HumanInputRequiredError):
            await node.execute({"human_response": None, "input": "test"})

    @pytest.mark.asyncio
    async def test_custom_resume_key_used_for_resume_detection(self) -> None:
        node = HumanNode(
            "ask",
            prompt="Confirm?",
            output_key="answer",
            resume_key="hitl_answer",
        )
        with pytest.raises(HumanInputRequiredError):
            await node.execute({"answer": "yes", "input": "test"})

        result = await node.execute({"hitl_answer": "approved", "input": "test"})
        assert result == {"answer": "approved"}

    @pytest.mark.asyncio
    async def test_node_type_is_human(self) -> None:
        node = HumanNode("ask", prompt="?")
        assert node.node_type == NodeType.HUMAN


class TestGateNode:
    @pytest.mark.asyncio
    async def test_execute_returns_empty_dict(self) -> None:
        node = GateNode(
            "router",
            routes={
                "left": lambda s: s.get("dir") == "left",
                "right": lambda s: s.get("dir") == "right",
            },
        )
        result = await node.execute({"dir": "left", "input": "test"})
        assert result == {}

    def test_routes_stored_on_instance(self) -> None:
        cond = lambda s: True  # noqa: E731
        node = GateNode("g", routes={"target": cond})
        assert node.routes["target"] is cond

    def test_node_type_is_gate(self) -> None:
        node = GateNode("g")
        assert node.node_type == NodeType.GATE

    def test_empty_routes_allowed(self) -> None:
        node = GateNode("g")
        assert node.routes == {}


class TestSubworkflowNode:
    @pytest.mark.asyncio
    async def test_executes_nested_workflow_and_stores_output(self) -> None:
        inner = WorkflowEngine(
            name="inner",
            nodes={"n": ConstantNode("n", output="inner_val")},
            edges=[],
            entry_node="n",
            terminal_conditions={"n": None},
        )
        node = SubworkflowNode("sub", workflow=inner)
        result = await node.execute({"input": "test"})
        assert result == {"output": "inner_val"}

    @pytest.mark.asyncio
    async def test_custom_output_key_used(self) -> None:
        inner = WorkflowEngine(
            name="inner",
            nodes={"n": ConstantNode("n", output="value")},
            edges=[],
            entry_node="n",
            terminal_conditions={"n": None},
        )
        node = SubworkflowNode("sub", workflow=inner, output_key="my_result")
        result = await node.execute({"input": "test"})
        assert "my_result" in result
        assert result["my_result"] == "value"

    @pytest.mark.asyncio
    async def test_inner_failure_stored_as_error_string(self) -> None:
        from quadkit.result import Err as ErrType

        class _BrokenInner:
            async def execute(self, input_: str, *, state=None) -> object:
                return ErrType(RuntimeError("inner error"))

        node = SubworkflowNode("sub", workflow=_BrokenInner())
        result = await node.execute({"input": "test"})
        assert result.get("output", "") == "Subworkflow execution failed."
        assert "inner error" not in result.get("output", "")

    @pytest.mark.asyncio
    async def test_inner_runtime_error_stored_as_error_string(self) -> None:
        class _CrashingInner:
            async def execute(self, input_: str, *, state=None) -> object:
                raise RuntimeError("boom")

        node = SubworkflowNode("sub", workflow=_CrashingInner())
        result = await node.execute({"input": "test"})
        assert result.get("output", "") == "Subworkflow execution failed."
        assert "boom" not in result.get("output", "")

    def test_node_type_is_subworkflow(self) -> None:
        node = SubworkflowNode("sub", workflow=MagicMock())
        assert node.node_type == NodeType.SUBWORKFLOW


class TestEngineResumeKeyResolution:
    """WorkflowEngine.resume must inject the response under the paused
    node's resume_key — a hardcoded key would leave custom-keyed human
    nodes paused forever."""

    @pytest.mark.asyncio
    async def test_resume_uses_paused_node_resume_key(self) -> None:
        from quadkit.workflow.graph.engine import WorkflowEngine
        from quadkit.workflow.graph.edge import WorkflowEdge
        from quadkit.result import Ok

        node = HumanNode("ask", prompt="Confirm?", output_key="answer")
        engine = WorkflowEngine(
            name="custom-key",
            nodes={"ask": node},
            edges=[],
            entry_node="ask",
            terminal_conditions={"ask": None},
        )

        checkpoint = {"input": "go", "_paused_at": "ask"}
        result = await engine.resume(checkpoint, "approved")

        assert result.is_ok()
        final_state = result.unwrap().final_state
        # Response was stored under the node's output_key.
        assert final_state.get("answer") == "approved"

    @pytest.mark.asyncio
    async def test_resume_explicit_response_key_overrides_node(self) -> None:
        from quadkit.workflow.graph.engine import WorkflowEngine

        node = HumanNode("ask", prompt="Confirm?", output_key="answer")
        engine = WorkflowEngine(
            name="explicit-key",
            nodes={"ask": node},
            edges=[],
            entry_node="ask",
            terminal_conditions={"ask": None},
        )

        # Explicit key wins: the node sees its resume_key ("answer").
        checkpoint = {"input": "go", "_paused_at": "ask", "answer": "preset"}
        result = await engine.resume(checkpoint, "new", response_key="override")
        assert result.is_ok()
        # The explicit key is present in the final state.
        assert result.unwrap().final_state.get("override") == "new"
