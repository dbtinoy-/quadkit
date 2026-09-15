"""Graph store protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.data.graph.enums import EdgeDirection

if TYPE_CHECKING:
    from quadkit.contracts.core.health import HealthCheckResult
    from quadkit.contracts.data.graph.filters import PropertyFilter
    from quadkit.contracts.data.graph.types import (
        BulkEdgeResult,
        BulkNodeResult,
        ConstraintSpec,
        EdgeResult,
        EdgeSpec,
        GraphEdge,
        GraphInfo,
        GraphNode,
        GraphPath,
        IndexSpec,
        NodeResult,
        NodeSpec,
        TraversalQuery,
    )


@runtime_checkable
class GraphStoreProtocol(Protocol):
    """Top-level graph store lifecycle and database management.

    Manages connections to the graph backend and provides access to
    individual graph databases.
    """

    async def connect(self) -> None:
        """Establish connection to the graph store."""
        ...

    async def disconnect(self) -> None:
        """Close all connections and release resources."""
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check store connectivity and readiness."""
        ...

    async def get_graph(self, name: str | None = None) -> GraphProtocol:
        """Get a handle to a graph database.

        Args:
            name: Database name. ``None`` returns the default graph.

        Raises:
            GraphNotFoundError: If the named graph does not exist.
        """
        ...

    async def list_graphs(self) -> list[GraphInfo]:
        """List all available graph databases."""
        ...

    async def create_graph(self, name: str) -> None:
        """Create a new graph database.

        Raises:
            GraphAlreadyExistsError: If the graph already exists.
        """
        ...

    async def delete_graph(self, name: str) -> None:
        """Delete a graph database and all its data.

        Raises:
            GraphNotFoundError: If the graph does not exist.
        """
        ...


@runtime_checkable
class GraphProtocol(Protocol):
    """All operations on a single graph database.

    Provides CRUD for nodes and edges, traversal queries, raw query
    passthrough, bulk operations, and schema management.
    """

    # ── Node Operations ───────────────────────────────────────────

    async def create_node(
        self,
        labels: list[str],
        properties: dict[str, Any] | None = None,
        node_id: str | None = None,
    ) -> NodeResult:
        """Create a node with labels and properties."""
        ...

    async def get_node(self, node_id: str) -> GraphNode | None:
        """Retrieve a node by ID. Returns None if not found."""
        ...

    async def find_nodes(
        self,
        labels: list[str] | None = None,
        filter: PropertyFilter | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[GraphNode]:
        """Find nodes matching labels and/or property filter."""
        ...

    async def update_node(
        self,
        node_id: str,
        properties: dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """Update node properties."""
        ...

    async def delete_node(
        self,
        node_id: str,
        detach: bool = True,
    ) -> bool:
        """Delete a node."""
        ...

    async def neighbors(
        self,
        node_id: str,
        depth: int = 1,
        direction: EdgeDirection = EdgeDirection.BOTH,
        edge_types: list[str] | None = None,
    ) -> list[GraphNode]:
        """Get neighbouring nodes reachable within the given depth."""
        ...

    async def count_nodes(self) -> int:
        """Return the total number of nodes in the graph."""
        ...

    async def count_edges(self) -> int:
        """Return the total number of edges in the graph."""
        ...

    async def get_labels(self) -> list[str]:
        """Return all unique node labels in the graph."""
        ...

    async def get_edge_types(self) -> list[str]:
        """Return all unique edge types in the graph."""
        ...

    # ── Edge Operations ───────────────────────────────────────────

    async def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> EdgeResult:
        """Create a directed edge between two nodes."""
        ...

    async def get_edge(self, edge_id: str) -> GraphEdge | None:
        """Retrieve an edge by ID."""
        ...

    async def get_edges(
        self,
        node_id: str,
        direction: EdgeDirection = EdgeDirection.BOTH,
        edge_types: list[str] | None = None,
        limit: int = 100,
    ) -> list[GraphEdge]:
        """Get edges connected to a node."""
        ...

    async def update_edge(
        self,
        edge_id: str,
        properties: dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """Update edge properties."""
        ...

    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge by ID."""
        ...

    # ── Traversal ─────────────────────────────────────────────────

    async def traverse(
        self,
        query: TraversalQuery,
    ) -> list[GraphPath]:
        """Execute a traversal query and return matching paths."""
        ...

    async def shortest_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 10,
        edge_types: list[str] | None = None,
        direction: EdgeDirection = EdgeDirection.BOTH,
    ) -> GraphPath | None:
        """Find the shortest path between two nodes."""
        ...

    # ── Raw Query ─────────────────────────────────────────────────

    async def query(
        self,
        query_string: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a raw backend-specific query (Cypher, Gremlin, etc.)."""
        ...

    # ── Bulk Operations ───────────────────────────────────────────

    async def bulk_create_nodes(
        self,
        nodes: list[NodeSpec],
    ) -> BulkNodeResult:
        """Create multiple nodes in a single operation."""
        ...

    async def bulk_create_edges(
        self,
        edges: list[EdgeSpec],
    ) -> BulkEdgeResult:
        """Create multiple edges in a single operation."""
        ...

    # ── Schema ────────────────────────────────────────────────────

    async def create_index(self, spec: IndexSpec) -> None:
        """Create an index on node label + properties."""
        ...

    async def drop_index(self, name: str) -> None:
        """Drop an index by name."""
        ...

    async def create_constraint(self, spec: ConstraintSpec) -> None:
        """Create a schema constraint."""
        ...

    async def drop_constraint(self, name: str) -> None:
        """Drop a constraint by name."""
        ...


__all__ = [
    "GraphProtocol",
    "GraphStoreProtocol",
]
