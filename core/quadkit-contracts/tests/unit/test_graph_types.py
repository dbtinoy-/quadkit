"""Tests for contracts/data/graph/types.py — graph value types."""

from __future__ import annotations

import pytest

from quadkit.contracts.data.graph.types import (
    EdgeResult,
    EdgeSpec,
    GraphEdge,
    GraphNode,
    GraphPath,
    NodeResult,
    NodeSpec,
    StartSpec,
    TraversalQuery,
    TraversalStep,
)


class TestGraphNode:
    """Tests for GraphNode dataclass."""

    def test_graph_node_creation(self) -> None:
        """GraphNode creates with required fields."""
        node = GraphNode(id="n1", labels=("Person",))
        assert node.id == "n1"
        assert node.labels == ("Person",)

    def test_graph_node_with_properties(self) -> None:
        """GraphNode accepts properties."""
        node = GraphNode(
            id="n1",
            labels=("User",),
            properties={"name": "Alice", "age": 30},
        )
        assert node.properties["name"] == "Alice"
        assert node.properties["age"] == 30

    def test_graph_node_default_properties(self) -> None:
        """GraphNode defaults to empty properties."""
        node = GraphNode(id="n1", labels=("Test",))
        assert node.properties == {}

    def test_graph_node_is_frozen(self) -> None:
        """GraphNode is frozen (immutable)."""
        node = GraphNode(id="n1", labels=("T",))
        with pytest.raises(AttributeError):
            node.id = "n2"


class TestGraphEdge:
    """Tests for GraphEdge dataclass."""

    def test_graph_edge_creation(self) -> None:
        """GraphEdge creates with required fields."""
        edge = GraphEdge(
            id="e1",
            type="KNOWS",
            source_id="n1",
            target_id="n2",
        )
        assert edge.id == "e1"
        assert edge.type == "KNOWS"
        assert edge.source_id == "n1"
        assert edge.target_id == "n2"

    def test_graph_edge_with_properties(self) -> None:
        """GraphEdge accepts properties."""
        edge = GraphEdge(
            id="e1",
            type="OWNS",
            source_id="n1",
            target_id="n2",
            properties={"since": 2020},
        )
        assert edge.properties["since"] == 2020

    def test_graph_edge_default_properties(self) -> None:
        """GraphEdge defaults to empty properties."""
        edge = GraphEdge(id="e1", type="X", source_id="a", target_id="b")
        assert edge.properties == {}

    def test_graph_edge_is_frozen(self) -> None:
        """GraphEdge is frozen."""
        edge = GraphEdge(id="e1", type="X", source_id="a", target_id="b")
        with pytest.raises(AttributeError):
            edge.type = "Y"


class TestGraphPath:
    """Tests for GraphPath dataclass."""

    def test_graph_path_creation(self) -> None:
        """GraphPath creates with nodes and edges."""
        node1 = GraphNode(id="n1", labels=("A",))
        node2 = GraphNode(id="n2", labels=("B",))
        edge = GraphEdge(id="e1", type="X", source_id="n1", target_id="n2")

        path = GraphPath(nodes=(node1, node2), edges=(edge,))
        assert len(path.nodes) == 2
        assert len(path.edges) == 1

    def test_graph_path_length_property(self) -> None:
        """GraphPath length returns number of edges."""
        node1 = GraphNode(id="n1", labels=("A",))
        node2 = GraphNode(id="n2", labels=("B",))
        node3 = GraphNode(id="n3", labels=("C",))
        edge1 = GraphEdge(id="e1", type="X", source_id="n1", target_id="n2")
        edge2 = GraphEdge(id="e2", type="Y", source_id="n2", target_id="n3")

        path = GraphPath(nodes=(node1, node2, node3), edges=(edge1, edge2))
        assert path.length == 2

    def test_graph_path_length_zero_for_single_node(self) -> None:
        """GraphPath length is 0 for single node (no edges)."""
        node = GraphNode(id="n1", labels=("A",))
        path = GraphPath(nodes=(node,), edges=())
        assert path.length == 0

    def test_graph_path_start_node_property(self) -> None:
        """GraphPath start_node returns first node."""
        node1 = GraphNode(id="start", labels=("A",))
        node2 = GraphNode(id="end", labels=("B",))
        edge = GraphEdge(id="e1", type="X", source_id="start", target_id="end")

        path = GraphPath(nodes=(node1, node2), edges=(edge,))
        assert path.start_node.id == "start"

    def test_graph_path_end_node_property(self) -> None:
        """GraphPath end_node returns last node."""
        node1 = GraphNode(id="start", labels=("A",))
        node2 = GraphNode(id="end", labels=("B",))
        edge = GraphEdge(id="e1", type="X", source_id="start", target_id="end")

        path = GraphPath(nodes=(node1, node2), edges=(edge,))
        assert path.end_node.id == "end"

    def test_graph_path_is_frozen(self) -> None:
        """GraphPath is frozen."""
        node = GraphNode(id="n1", labels=("A",))
        path = GraphPath(nodes=(node,), edges=())
        with pytest.raises(AttributeError):
            path.nodes = ()


class TestNodeSpec:
    """Tests for NodeSpec dataclass."""

    def test_node_spec_creation(self) -> None:
        """NodeSpec creates correctly."""
        spec = NodeSpec(labels=("Person",), properties={"name": "Bob"})
        assert spec.labels == ("Person",)
        assert spec.properties["name"] == "Bob"

    def test_node_spec_with_id(self) -> None:
        """NodeSpec accepts optional id."""
        spec = NodeSpec(labels=("User",), id="custom-id")
        assert spec.id == "custom-id"

    def test_node_spec_id_default_none(self) -> None:
        """NodeSpec defaults id to None."""
        spec = NodeSpec(labels=("User",))
        assert spec.id is None

    def test_node_spec_is_frozen(self) -> None:
        """NodeSpec is frozen."""
        spec = NodeSpec(labels=("T",))
        with pytest.raises(AttributeError):
            spec.id = "new"


class TestEdgeSpec:
    """Tests for EdgeSpec dataclass."""

    def test_edge_spec_creation(self) -> None:
        """EdgeSpec creates correctly."""
        spec = EdgeSpec(
            source_id="n1",
            target_id="n2",
            type="KNOWS",
            properties={"since": 2021},
        )
        assert spec.source_id == "n1"
        assert spec.target_id == "n2"
        assert spec.type == "KNOWS"

    def test_edge_spec_is_frozen(self) -> None:
        """EdgeSpec is frozen."""
        spec = EdgeSpec(source_id="a", target_id="b", type="X")
        with pytest.raises(AttributeError):
            spec.type = "Y"


class TestNodeResult:
    """Tests for NodeResult dataclass."""

    def test_node_result_created_true(self) -> None:
        """NodeResult default created is True."""
        result = NodeResult(id="n1")
        assert result.id == "n1"
        assert result.created is True

    def test_node_result_created_false(self) -> None:
        """NodeResult can set created to False."""
        result = NodeResult(id="n1", created=False)
        assert result.created is False

    def test_node_result_is_frozen(self) -> None:
        """NodeResult is frozen."""
        result = NodeResult(id="n1")
        with pytest.raises(AttributeError):
            result.id = "n2"


class TestEdgeResult:
    """Tests for EdgeResult dataclass."""

    def test_edge_result_created_true(self) -> None:
        """EdgeResult default created is True."""
        result = EdgeResult(id="e1")
        assert result.id == "e1"
        assert result.created is True

    def test_edge_result_created_false(self) -> None:
        """EdgeResult can set created to False."""
        result = EdgeResult(id="e1", created=False)
        assert result.created is False

    def test_edge_result_is_frozen(self) -> None:
        """EdgeResult is frozen."""
        result = EdgeResult(id="e1")
        with pytest.raises(AttributeError):
            result.id = "e2"


class TestTraversalQuery:
    """Tests for TraversalQuery dataclass."""

    def test_traversal_query_creation(self) -> None:
        """TraversalQuery creates correctly."""
        start_spec = StartSpec(node_ids=("n1",))
        step = TraversalStep()
        query = TraversalQuery(
            start=start_spec,
            steps=(step,),
        )
        assert query.start.node_ids == ("n1",)

    def test_traversal_query_default_values(self) -> None:
        """TraversalQuery has sensible defaults."""
        start_spec = StartSpec(node_ids=("n1",))
        step = TraversalStep()
        query = TraversalQuery(start=start_spec, steps=(step,))
        assert query.return_type.value == "paths"
        assert query.unique_nodes is True

    def test_traversal_query_is_frozen(self) -> None:
        """TraversalQuery is frozen."""
        start_spec = StartSpec(node_ids=("n1",))
        step = TraversalStep()
        query = TraversalQuery(start=start_spec, steps=(step,))
        with pytest.raises(AttributeError):
            query.unique_nodes = False


class TestStartSpec:
    """Tests for StartSpec dataclass."""

    def test_start_spec_with_node_ids(self) -> None:
        """StartSpec creates with node_ids."""
        spec = StartSpec(node_ids=("n1", "n2"))
        assert spec.node_ids == ("n1", "n2")

    def test_start_spec_with_labels(self) -> None:
        """StartSpec creates with labels."""
        spec = StartSpec(labels=("Person",))
        assert spec.labels == ("Person",)

    def test_start_spec_with_properties(self) -> None:
        """StartSpec creates with properties."""
        spec = StartSpec(properties={"name": "Alice"})
        assert spec.properties == {"name": "Alice"}

    def test_start_spec_all_defaults(self) -> None:
        """StartSpec defaults to None for all optional fields."""
        spec = StartSpec()
        assert spec.node_ids is None
        assert spec.labels is None
        assert spec.properties is None

    def test_start_spec_is_frozen(self) -> None:
        """StartSpec is frozen."""
        spec = StartSpec(node_ids=("n1",))
        with pytest.raises(AttributeError):
            spec.node_ids = ("n2",)


class TestTraversalStep:
    """Tests for TraversalStep dataclass."""

    def test_traversal_step_creation(self) -> None:
        """TraversalStep creates correctly."""
        step = TraversalStep()
        assert step.min_depth == 1
        assert step.max_depth == 1

    def test_traversal_step_with_edge_types(self) -> None:
        """TraversalStep accepts edge_types."""
        step = TraversalStep(edge_types=("KNOWS", "WORKS_WITH"))
        assert step.edge_types == ("KNOWS", "WORKS_WITH")

    def test_traversal_step_is_frozen(self) -> None:
        """TraversalStep is frozen."""
        step = TraversalStep()
        with pytest.raises(AttributeError):
            step.min_depth = 2
