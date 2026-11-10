"""Shared fixtures for quadkit-workflow graph engine unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure graph_helpers.py in this directory is importable regardless of pytest rootdir.
sys.path.insert(0, str(Path(__file__).parent))

import pytest

from quadkit.workflow.graph.engine import WorkflowEngine
from quadkit.workflow.graph.edge import WorkflowEdge
from quadkit.workflow.config import GraphConfig
from quadkit.workflow.nodes.human_node import HumanNode
from graph_helpers import AppendNode, ConstantNode, CounterNode, EchoNode


@pytest.fixture()
def linear_engine() -> WorkflowEngine:
    """A -> B -> C linear workflow; C is terminal."""
    nodes = {
        "a": AppendNode("a"),
        "b": AppendNode("b"),
        "c": AppendNode("c"),
    }
    edges = [
        WorkflowEdge(source="a", target="b"),
        WorkflowEdge(source="b", target="c"),
    ]
    return WorkflowEngine(
        name="linear",
        nodes=nodes,
        edges=edges,
        entry_node="a",
        terminal_conditions={"c": None},
        config=GraphConfig(max_iterations=10),
    )


@pytest.fixture()
def conditional_engine() -> WorkflowEngine:
    """A sets route; gate routes to B (route="b") or C (route="c"); both terminal."""
    nodes = {
        "a": ConstantNode("a", route="b", output="a_done"),
        "b": ConstantNode("b", result="branch_b", output="b_done"),
        "c": ConstantNode("c", result="branch_c", output="c_done"),
    }
    edges = [
        WorkflowEdge(source="a", target="b", condition=lambda s: s.get("route") == "b"),
        WorkflowEdge(source="a", target="c", condition=lambda s: s.get("route") == "c"),
    ]
    return WorkflowEngine(
        name="conditional",
        nodes=nodes,
        edges=edges,
        entry_node="a",
        terminal_conditions={"b": None, "c": None},
        config=GraphConfig(max_iterations=10),
    )


@pytest.fixture()
def parallel_engine() -> WorkflowEngine:
    """start -> [branch_a, branch_b] parallel; both branches terminal."""
    nodes = {
        "start": ConstantNode("start", started=True, output="started"),
        "branch_a": ConstantNode("branch_a", branch_a=True, output="branch_a_done"),
        "branch_b": ConstantNode("branch_b", branch_b=True, output="branch_b_done"),
    }
    edges = [
        WorkflowEdge(source="start", target="branch_a"),
        WorkflowEdge(source="start", target="branch_b"),
    ]
    return WorkflowEngine(
        name="parallel",
        nodes=nodes,
        edges=edges,
        entry_node="start",
        terminal_conditions={"branch_a": None, "branch_b": None},
        config=GraphConfig(max_iterations=10, parallel_branches=True),
    )


@pytest.fixture()
def cyclic_engine() -> WorkflowEngine:
    """A -> B -> A infinite cycle; max_iterations=3 forces CycleDetectedError."""
    nodes = {
        "a": CounterNode("a"),
        "b": EchoNode("b"),
    }
    edges = [
        WorkflowEdge(source="a", target="b"),
        WorkflowEdge(source="b", target="a"),
    ]
    return WorkflowEngine(
        name="cyclic",
        nodes=nodes,
        edges=edges,
        entry_node="a",
        terminal_conditions={},
        config=GraphConfig(max_iterations=3),
    )


@pytest.fixture()
def human_in_loop_engine() -> WorkflowEngine:
    """start -> human -> end; human node requires operator input."""
    nodes = {
        "start": ConstantNode("start", output="start_done"),
        "human": HumanNode("human", prompt="Please provide input: {input}"),
        "end": ConstantNode("end", finished=True, output="end_done"),
    }
    edges = [
        WorkflowEdge(source="start", target="human"),
        WorkflowEdge(source="human", target="end"),
    ]
    return WorkflowEngine(
        name="human_in_loop",
        nodes=nodes,
        edges=edges,
        entry_node="start",
        terminal_conditions={"end": None},
        config=GraphConfig(max_iterations=20),
    )
