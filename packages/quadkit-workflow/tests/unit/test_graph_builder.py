"""Unit tests for WorkflowBuilder fluent API and validation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.workflow.config import GraphConfig
from quadkit.workflow.exceptions import GraphValidationError
from quadkit.workflow.graph.builder import WorkflowBuilder
from quadkit.workflow.graph.engine import WorkflowEngine
from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType

from graph_helpers import AppendNode, ConstantNode, EchoNode


class TestWorkflowBuilderValidBuilds:
    def test_build_linear_workflow(self) -> None:
        engine = (
            WorkflowBuilder("linear_test")
            .add_node("a", node=EchoNode("a"))
            .add_node("b", node=EchoNode("b"))
            .add_edge("a", "b")
            .set_entry("a")
            .set_terminal("b")
            .build()
        )
        assert isinstance(engine, WorkflowEngine)

    def test_build_single_node_workflow(self) -> None:
        engine = (
            WorkflowBuilder("solo")
            .add_node("only", node=EchoNode("only"))
            .set_entry("only")
            .set_terminal("only")
            .build()
        )
        assert engine.name == "solo"

    def test_workflow_name_stored_on_engine(self) -> None:
        engine = (
            WorkflowBuilder("my_workflow")
            .add_node("n", node=EchoNode("n"))
            .set_entry("n")
            .set_terminal("n")
            .build()
        )
        assert engine.name == "my_workflow"

    def test_configure_replaces_config(self) -> None:
        custom_config = GraphConfig(max_iterations=42)
        engine = (
            WorkflowBuilder("cfg_test")
            .add_node("n", node=EchoNode("n"))
            .configure(custom_config)
            .set_entry("n")
            .set_terminal("n")
            .build()
        )
        assert isinstance(engine, WorkflowEngine)

    def test_builder_returns_self_for_all_methods(self) -> None:
        builder = WorkflowBuilder("chain_test")
        result = builder.add_node("a", node=EchoNode("a"))
        assert result is builder
        result = builder.add_edge("a", "a")
        assert result is builder
        result = builder.set_entry("a")
        assert result is builder
        result = builder.set_terminal("a")
        assert result is builder


class TestWorkflowBuilderAddNode:
    def test_add_node_with_pre_built_node_instance(self) -> None:
        node = EchoNode("custom")
        engine = (
            WorkflowBuilder("custom_node")
            .add_node("custom", node=node)
            .set_entry("custom")
            .set_terminal("custom")
            .build()
        )
        assert isinstance(engine, WorkflowEngine)

    def test_add_node_with_llm_client_creates_llm_node(self) -> None:
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="response")
        engine = (
            WorkflowBuilder("llm_test")
            .add_node("llm_node", llm=mock_llm, prompt="Process: {input}")
            .set_entry("llm_node")
            .set_terminal("llm_node")
            .build()
        )
        assert isinstance(engine, WorkflowEngine)

    def test_add_node_with_human_prompt_creates_human_node(self) -> None:
        engine = (
            WorkflowBuilder("human_test")
            .add_node("ask", human_prompt="What is your name?")
            .set_entry("ask")
            .set_terminal("ask")
            .build()
        )
        assert isinstance(engine, WorkflowEngine)

    def test_add_node_duplicate_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="already registered"):
            (
                WorkflowBuilder("duplicate_test")
                .add_node("a", node=EchoNode("a"))
                .add_node("a", node=EchoNode("a"))
            )

    def test_add_node_without_type_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            (WorkflowBuilder("no_type").add_node("node_x"))


class TestWorkflowBuilderAddGate:
    def test_add_gate_creates_conditional_edges(self) -> None:
        engine = (
            WorkflowBuilder("gate_test")
            .add_node("start", node=ConstantNode("start", route="b", output="x"))
            .add_node("b", node=EchoNode("b"))
            .add_node("c", node=EchoNode("c"))
            .add_gate(
                "router",
                routes={
                    "b": lambda s: s.get("route") == "b",
                    "c": lambda s: s.get("route") == "c",
                },
            )
            .add_edge("start", "router")
            .set_entry("start")
            .set_terminal("b")
            .set_terminal("c")
            .build()
        )
        assert isinstance(engine, WorkflowEngine)

    @pytest.mark.asyncio
    async def test_gate_routes_to_correct_branch(self) -> None:
        engine = (
            WorkflowBuilder("gate_routing")
            .add_node("start", node=ConstantNode("start", go="left", output="start"))
            .add_node("left", node=ConstantNode("left", output="went_left"))
            .add_node("right", node=ConstantNode("right", output="went_right"))
            .add_gate(
                "gate",
                routes={
                    "left": lambda s: s.get("go") == "left",
                    "right": lambda s: s.get("go") == "right",
                },
            )
            .add_edge("start", "gate")
            .set_entry("start")
            .set_terminal("left")
            .set_terminal("right")
            .build()
        )
        result = await engine.execute("test")
        assert result.is_ok()
        names = [r.node_name for r in result.unwrap().node_results]
        assert "left" in names
        assert "right" not in names


class TestWorkflowBuilderEdges:
    def test_add_edge_with_condition(self) -> None:
        engine = (
            WorkflowBuilder("edge_cond")
            .add_node("a", node=ConstantNode("a", flag=True, output="a"))
            .add_node("b", node=EchoNode("b"))
            .add_edge("a", "b", condition=lambda s: s.get("flag") is True)
            .set_entry("a")
            .set_terminal("b")
            .build()
        )
        assert isinstance(engine, WorkflowEngine)

    def test_add_edge_with_label(self) -> None:
        engine = (
            WorkflowBuilder("label_test")
            .add_node("a", node=EchoNode("a"))
            .add_node("b", node=EchoNode("b"))
            .add_edge("a", "b", label="success_path")
            .set_entry("a")
            .set_terminal("b")
            .build()
        )
        assert isinstance(engine, WorkflowEngine)


class TestWorkflowBuilderTerminals:
    def test_conditional_terminal_only_stops_when_condition_met(self) -> None:
        engine = (
            WorkflowBuilder("cond_terminal")
            .add_node("a", node=ConstantNode("a", done=True, output="a"))
            .set_entry("a")
            .set_terminal("a", condition=lambda s: s.get("done") is True)
            .build()
        )
        assert isinstance(engine, WorkflowEngine)


class TestWorkflowBuilderValidationErrors:
    def test_build_without_entry_raises_validation_error(self) -> None:
        with pytest.raises(GraphValidationError, match="no entry node"):
            (
                WorkflowBuilder("no_entry")
                .add_node("a", node=EchoNode("a"))
                .set_terminal("a")
                .build()
            )

    def test_build_without_terminal_raises_validation_error(self) -> None:
        with pytest.raises(GraphValidationError, match="no terminal"):
            (
                WorkflowBuilder("no_terminal")
                .add_node("a", node=EchoNode("a"))
                .set_entry("a")
                .build()
            )

    def test_build_with_edge_pointing_to_unregistered_node_raises(self) -> None:
        with pytest.raises(GraphValidationError):
            (
                WorkflowBuilder("bad_edge")
                .add_node("a", node=EchoNode("a"))
                .add_edge("a", "ghost_node")
                .set_entry("a")
                .set_terminal("a")
                .build()
            )

    def test_build_with_terminal_pointing_to_unregistered_node_raises(self) -> None:
        with pytest.raises(GraphValidationError):
            (
                WorkflowBuilder("ghost_terminal")
                .add_node("a", node=EchoNode("a"))
                .set_entry("a")
                .set_terminal("ghost")
                .build()
            )


class TestWorkflowBuilderEndToEnd:
    @pytest.mark.asyncio
    async def test_builder_linear_workflow_executes(self) -> None:
        engine = (
            WorkflowBuilder("e2e_linear")
            .add_node("a", node=AppendNode("a"))
            .add_node("b", node=AppendNode("b"))
            .add_node("c", node=AppendNode("c"))
            .add_edge("a", "b")
            .add_edge("b", "c")
            .set_entry("a")
            .set_terminal("c")
            .build()
        )
        result = await engine.execute("test")
        assert result.is_ok()
        assert result.unwrap().final_state["path"] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_builder_conditional_workflow_executes(self) -> None:
        engine = (
            WorkflowBuilder("e2e_conditional")
            .add_node("start", node=ConstantNode("start", route="yes", output="s"))
            .add_node("yes_branch", node=ConstantNode("yes_branch", branch="yes", output="y"))
            .add_node("no_branch", node=ConstantNode("no_branch", branch="no", output="n"))
            .add_edge("start", "yes_branch", condition=lambda s: s.get("route") == "yes")
            .add_edge("start", "no_branch", condition=lambda s: s.get("route") == "no")
            .set_entry("start")
            .set_terminal("yes_branch")
            .set_terminal("no_branch")
            .build()
        )
        result = await engine.execute("test")
        assert result.is_ok()
        wf = result.unwrap()
        assert wf.final_state.get("branch") == "yes"
