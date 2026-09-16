"""Graph store value types — all immutable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quadkit.contracts.data.graph.enums import (
    ConstraintKind,
    EdgeDirection,
    IndexKind,
    ReturnType,
)

if TYPE_CHECKING:
    from quadkit.contracts.data.graph.filters import PropertyFilter


@dataclass(frozen=True, slots=True)
class GraphNode:
    """A node (vertex) in the graph."""

    id: str
    labels: tuple[str, ...]
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """A directed edge (relationship) in the graph."""

    id: str
    type: str
    source_id: str
    target_id: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphPath:
    """An ordered alternating sequence of nodes and edges.

    ``nodes[0] --edges[0]--> nodes[1] --edges[1]--> nodes[2] ...``
    """

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]

    @property
    def length(self) -> int:
        """Number of edges (hops) in the path."""
        return len(self.edges)

    @property
    def start_node(self) -> GraphNode:
        """First node in the path."""
        return self.nodes[0]

    @property
    def end_node(self) -> GraphNode:
        """Last node in the path."""
        return self.nodes[-1]


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """Specification for creating a node."""

    labels: tuple[str, ...]
    properties: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


@dataclass(frozen=True, slots=True)
class EdgeSpec:
    """Specification for creating an edge."""

    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NodeResult:
    """Result of a node creation or update."""

    id: str
    created: bool = True


@dataclass(frozen=True, slots=True)
class EdgeResult:
    """Result of an edge creation or update."""

    id: str
    created: bool = True


@dataclass(frozen=True, slots=True)
class BulkNodeResult:
    """Result of a bulk node operation."""

    created_count: int
    ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BulkEdgeResult:
    """Result of a bulk edge operation."""

    created_count: int
    ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphInfo:
    """Metadata about a graph database."""

    name: str
    node_count: int = 0
    edge_count: int = 0
    label_count: int = 0
    edge_type_count: int = 0


@dataclass(frozen=True, slots=True)
class StartSpec:
    """How to find traversal start nodes."""

    node_ids: tuple[str, ...] | None = None
    labels: tuple[str, ...] | None = None
    properties: dict[str, Any] | None = None
    filter: PropertyFilter | None = None


@dataclass(frozen=True, slots=True)
class TraversalStep:
    """A single hop definition in a traversal."""

    edge_types: tuple[str, ...] | None = None
    direction: EdgeDirection = EdgeDirection.OUTGOING
    min_depth: int = 1
    max_depth: int = 1
    node_labels: tuple[str, ...] | None = None
    node_filter: PropertyFilter | None = None
    edge_filter: PropertyFilter | None = None


@dataclass(frozen=True, slots=True)
class TraversalQuery:
    """Compiled traversal specification."""

    start: StartSpec
    steps: tuple[TraversalStep, ...]
    return_type: ReturnType = ReturnType.PATHS
    result_filter: PropertyFilter | None = None
    result_labels: tuple[str, ...] | None = None
    order_by: tuple[tuple[str, bool], ...] | None = None
    limit: int | None = None
    skip: int | None = None
    unique_nodes: bool = True


@dataclass(frozen=True, slots=True)
class IndexSpec:
    """Specification for creating a graph index."""

    name: str
    label: str
    properties: tuple[str, ...]
    kind: IndexKind = IndexKind.BTREE


@dataclass(frozen=True, slots=True)
class ConstraintSpec:
    """Specification for creating a graph constraint."""

    name: str
    label: str
    properties: tuple[str, ...]
    kind: ConstraintKind = ConstraintKind.UNIQUE


__all__ = [
    "BulkEdgeResult",
    "BulkNodeResult",
    "ConstraintSpec",
    "EdgeResult",
    "EdgeSpec",
    "GraphEdge",
    "GraphInfo",
    "GraphNode",
    "GraphPath",
    "IndexSpec",
    "NodeResult",
    "NodeSpec",
    "StartSpec",
    "TraversalQuery",
    "TraversalStep",
]
