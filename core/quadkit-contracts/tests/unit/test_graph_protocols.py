"""Tests for graph protocol definitions."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.data.graph.protocols import (
    GraphProtocol,
    GraphStoreProtocol,
)


class TestGraphStoreProtocol:
    """Tests for GraphStoreProtocol."""

    @pytest.mark.asyncio
    async def test_has_connect_method(self) -> None:
        """Test protocol has connect async method."""

        class Store:
            async def connect(self) -> None:
                pass

        store = Store()
        await store.connect()

    @pytest.mark.asyncio
    async def test_has_disconnect_method(self) -> None:
        """Test protocol has disconnect async method."""

        class Store:
            async def disconnect(self) -> None:
                pass

        store = Store()
        await store.disconnect()

    @pytest.mark.asyncio
    async def test_has_health_check_method(self) -> None:
        """Test protocol has health_check async method."""

        class Store:
            async def health_check(self, timeout: float = 5.0) -> Any:
                return {"status": "healthy"}

        store = Store()
        result = await store.health_check()
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_has_get_graph_method(self) -> None:
        """Test protocol has get_graph async method."""

        class Store:
            async def get_graph(self, name: str | None = None) -> Any:
                return {}

        store = Store()
        result = await store.get_graph("test")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_has_list_graphs_method(self) -> None:
        """Test protocol has list_graphs async method."""

        class Store:
            async def list_graphs(self) -> list[Any]:
                return []

        store = Store()
        result = await store.list_graphs()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_has_create_graph_method(self) -> None:
        """Test protocol has create_graph async method."""

        class Store:
            async def create_graph(self, name: str) -> None:
                pass

        store = Store()
        await store.create_graph("test")

    @pytest.mark.asyncio
    async def test_has_delete_graph_method(self) -> None:
        """Test protocol has delete_graph async method."""

        class Store:
            async def delete_graph(self, name: str) -> None:
                pass

        store = Store()
        await store.delete_graph("test")

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Store:
            async def connect(self) -> None:
                pass

            async def disconnect(self) -> None:
                pass

            async def health_check(self, timeout: float = 5.0) -> Any:
                return {}

            async def get_graph(self, name: str | None = None) -> Any:
                return {}

            async def list_graphs(self) -> list:
                return []

            async def create_graph(self, name: str) -> None:
                pass

            async def delete_graph(self, name: str) -> None:
                pass

        assert isinstance(Store(), GraphStoreProtocol)


class TestGraphProtocol:
    """Tests for GraphProtocol."""

    @pytest.mark.asyncio
    async def test_has_create_node_method(self) -> None:
        """Test protocol has create_node async method."""

        class Graph:
            async def create_node(
                self,
                labels: list[str],
                properties: dict[str, Any] | None = None,
                node_id: str | None = None,
            ) -> Any:
                return {"id": "node-1"}

        graph = Graph()
        result = await graph.create_node(["Person"], {"name": "John"})
        assert result["id"] == "node-1"

    @pytest.mark.asyncio
    async def test_has_get_node_method(self) -> None:
        """Test protocol has get_node async method."""

        class Graph:
            async def get_node(self, node_id: str) -> Any | None:
                return {"id": node_id}

        graph = Graph()
        result = await graph.get_node("node-1")
        assert result["id"] == "node-1"

    @pytest.mark.asyncio
    async def test_has_find_nodes_method(self) -> None:
        """Test protocol has find_nodes async method."""

        class Graph:
            async def find_nodes(
                self,
                labels: list[str] | None = None,
                filter: Any = None,
                limit: int = 100,
                skip: int = 0,
            ) -> list[Any]:
                return []

        graph = Graph()
        result = await graph.find_nodes(["Person"])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_has_update_node_method(self) -> None:
        """Test protocol has update_node async method."""

        class Graph:
            async def update_node(
                self,
                node_id: str,
                properties: dict[str, Any],
                merge: bool = True,
            ) -> bool:
                return True

        graph = Graph()
        result = await graph.update_node("node-1", {"name": "John"})
        assert result is True

    @pytest.mark.asyncio
    async def test_has_delete_node_method(self) -> None:
        """Test protocol has delete_node async method."""

        class Graph:
            async def delete_node(
                self,
                node_id: str,
                detach: bool = True,
            ) -> bool:
                return True

        graph = Graph()
        result = await graph.delete_node("node-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_create_edge_method(self) -> None:
        """Test protocol has create_edge async method."""

        class Graph:
            async def create_edge(
                self,
                source_id: str,
                target_id: str,
                edge_type: str,
                properties: dict[str, Any] | None = None,
            ) -> Any:
                return {"id": "edge-1"}

        graph = Graph()
        result = await graph.create_edge("node-1", "node-2", "KNOWS")
        assert result["id"] == "edge-1"

    @pytest.mark.asyncio
    async def test_has_get_edge_method(self) -> None:
        """Test protocol has get_edge async method."""

        class Graph:
            async def get_edge(self, edge_id: str) -> Any | None:
                return {"id": edge_id}

        graph = Graph()
        result = await graph.get_edge("edge-1")
        assert result["id"] == "edge-1"

    @pytest.mark.asyncio
    async def test_has_get_edges_method(self) -> None:
        """Test protocol has get_edges async method."""

        from quadkit.contracts.data.graph.enums import EdgeDirection

        class Graph:
            async def get_edges(
                self,
                node_id: str,
                direction: EdgeDirection = EdgeDirection.BOTH,
                edge_types: list[str] | None = None,
                limit: int = 100,
            ) -> list[Any]:
                return []

        graph = Graph()
        result = await graph.get_edges("node-1")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_has_update_edge_method(self) -> None:
        """Test protocol has update_edge async method."""

        class Graph:
            async def update_edge(
                self,
                edge_id: str,
                properties: dict[str, Any],
                merge: bool = True,
            ) -> bool:
                return True

        graph = Graph()
        result = await graph.update_edge("edge-1", {"weight": 1.0})
        assert result is True

    @pytest.mark.asyncio
    async def test_has_delete_edge_method(self) -> None:
        """Test protocol has delete_edge async method."""

        class Graph:
            async def delete_edge(self, edge_id: str) -> bool:
                return True

        graph = Graph()
        result = await graph.delete_edge("edge-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_traverse_method(self) -> None:
        """Test protocol has traverse async method."""

        class Graph:
            async def traverse(self, query: Any) -> list[Any]:
                return []

        graph = Graph()
        result = await graph.traverse({})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_has_shortest_path_method(self) -> None:
        """Test protocol has shortest_path async method."""

        from quadkit.contracts.data.graph.enums import EdgeDirection

        class Graph:
            async def shortest_path(
                self,
                from_id: str,
                to_id: str,
                max_depth: int = 10,
                edge_types: list[str] | None = None,
                direction: EdgeDirection = EdgeDirection.BOTH,
            ) -> Any | None:
                return {"from": from_id, "to": to_id}

        graph = Graph()
        result = await graph.shortest_path("node-1", "node-2")
        assert result is not None

    @pytest.mark.asyncio
    async def test_has_query_method(self) -> None:
        """Test protocol has query async method."""

        class Graph:
            async def query(
                self,
                query_string: str,
                parameters: dict[str, Any] | None = None,
            ) -> list[dict[str, Any]]:
                return []

        graph = Graph()
        result = await graph.query("MATCH (n) RETURN n")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_has_bulk_create_nodes_method(self) -> None:
        """Test protocol has bulk_create_nodes async method."""

        class Graph:
            async def bulk_create_nodes(self, nodes: list[Any]) -> Any:
                return {"created": len(nodes)}

        graph = Graph()
        result = await graph.bulk_create_nodes([{"labels": ["Person"]}])
        assert result["created"] == 1

    @pytest.mark.asyncio
    async def test_has_bulk_create_edges_method(self) -> None:
        """Test protocol has bulk_create_edges async method."""

        class Graph:
            async def bulk_create_edges(self, edges: list[Any]) -> Any:
                return {"created": len(edges)}

        graph = Graph()
        result = await graph.bulk_create_edges([{"type": "KNOWS"}])
        assert result["created"] == 1

    @pytest.mark.asyncio
    async def test_has_create_index_method(self) -> None:
        """Test protocol has create_index async method."""

        class Graph:
            async def create_index(self, spec: Any) -> None:
                pass

        graph = Graph()
        await graph.create_index({})

    @pytest.mark.asyncio
    async def test_has_drop_index_method(self) -> None:
        """Test protocol has drop_index async method."""

        class Graph:
            async def drop_index(self, name: str) -> None:
                pass

        graph = Graph()
        await graph.drop_index("idx-1")

    @pytest.mark.asyncio
    async def test_has_create_constraint_method(self) -> None:
        """Test protocol has create_constraint async method."""

        class Graph:
            async def create_constraint(self, spec: Any) -> None:
                pass

        graph = Graph()
        await graph.create_constraint({})

    @pytest.mark.asyncio
    async def test_has_drop_constraint_method(self) -> None:
        """Test protocol has drop_constraint async method."""

        class Graph:
            async def drop_constraint(self, name: str) -> None:
                pass

        graph = Graph()
        await graph.drop_constraint("constraint-1")

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Graph:
            async def create_node(self, **kwargs: Any) -> Any:
                return {}

            async def get_node(self, node_id: str) -> Any | None:
                return None

            async def find_nodes(self, **kwargs: Any) -> list:
                return []

            async def update_node(self, node_id: str, **kwargs: Any) -> bool:
                return False

            async def delete_node(self, node_id: str, **kwargs: Any) -> bool:
                return False

            async def create_edge(self, **kwargs: Any) -> Any:
                return {}

            async def get_edge(self, edge_id: str) -> Any | None:
                return None

            async def get_edges(self, **kwargs: Any) -> list:
                return []

            async def update_edge(self, edge_id: str, **kwargs: Any) -> bool:
                return False

            async def delete_edge(self, edge_id: str) -> bool:
                return False

            async def traverse(self, query: Any) -> list:
                return []

            async def shortest_path(self, **kwargs: Any) -> Any | None:
                return None

            async def query(self, query_string: str, **kwargs: Any) -> list:
                return []

            async def bulk_create_nodes(self, nodes: list) -> Any:
                return {}

            async def bulk_create_edges(self, edges: list) -> Any:
                return {}

            async def create_index(self, spec: Any) -> None:
                pass

            async def drop_index(self, name: str) -> None:
                pass

            async def create_constraint(self, spec: Any) -> None:
                pass

            async def drop_constraint(self, name: str) -> None:
                pass

            async def neighbors(
                self, node_id: str, depth: int = 1, **kwargs: Any
            ) -> list:
                return []

            async def count_nodes(self) -> int:
                return 0

            async def count_edges(self) -> int:
                return 0

            async def get_labels(self) -> list[str]:
                return []

            async def get_edge_types(self) -> list[str]:
                return []

        assert isinstance(Graph(), GraphProtocol)
