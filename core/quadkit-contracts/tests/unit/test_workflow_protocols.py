"""Tests for workflow protocol definitions."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.workflow.protocols import (
    ApprovalProtocol,
    ExecutionProtocol,
    WorkflowGraphProtocol,
    WorkflowNodeProtocol,
)


class TestWorkflowGraphProtocol:
    """Tests for WorkflowGraphProtocol."""

    def test_has_add_node_method(self) -> None:
        """Test protocol has add_node method."""

        class Graph:
            def add_node(self, node_id: str, node: Any) -> None:
                pass

        graph = Graph()
        graph.add_node("node1", {})

    def test_has_add_edge_method(self) -> None:
        """Test protocol has add_edge method."""

        class Graph:
            def add_edge(self, from_id: str, to_id: str) -> None:
                pass

        graph = Graph()
        graph.add_edge("node1", "node2")

    def test_has_get_node_method(self) -> None:
        """Test protocol has get_node method."""

        class Graph:
            def get_node(self, node_id: str) -> Any | None:
                return None

        graph = Graph()
        result = graph.get_node("node1")
        assert result is None

    def test_has_topological_order_method(self) -> None:
        """Test protocol has topological_order method."""

        class Graph:
            def topological_order(self) -> list[str]:
                return ["node1", "node2"]

        graph = Graph()
        result = graph.topological_order()
        assert len(result) == 2

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Graph:
            def add_node(self, node_id: str, node: Any) -> None:
                pass

            def add_edge(self, from_id: str, to_id: str) -> None:
                pass

            def get_node(self, node_id: str) -> Any | None:
                return None

            def topological_order(self) -> list[str]:
                return []

        assert isinstance(Graph(), WorkflowGraphProtocol)


class TestWorkflowNodeProtocol:
    """Tests for WorkflowNodeProtocol."""

    def test_has_node_id_property(self) -> None:
        """Test protocol has node_id property."""

        class Node:
            @property
            def node_id(self) -> str:
                return "node-1"

        node = Node()
        assert node.node_id == "node-1"

    def test_has_name_property(self) -> None:
        """Test protocol has name property."""

        class Node:
            @property
            def name(self) -> str:
                return "test-node"

        node = Node()
        assert node.name == "test-node"

    @pytest.mark.asyncio
    async def test_has_execute_method(self) -> None:
        """Test protocol has execute async method."""

        class Node:
            @property
            def node_id(self) -> str:
                return "node-1"

            @property
            def name(self) -> str:
                return "test"

            async def execute(self, context: Any) -> Any:
                return {"result": "test"}

        node = Node()
        result = await node.execute({})
        assert result["result"] == "test"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Node:
            @property
            def node_id(self) -> str:
                return ""

            @property
            def name(self) -> str:
                return ""

            async def execute(self, context: Any) -> Any:
                return {}

        assert isinstance(Node(), WorkflowNodeProtocol)


class TestApprovalProtocol:
    """Tests for ApprovalProtocol."""

    @pytest.mark.asyncio
    async def test_has_request_approval_method(self) -> None:
        """Test protocol has request_approval async method."""

        class Approval:
            async def request_approval(
                self,
                workflow_id: str,
                step_id: str,
                context: Any,
            ) -> bool:
                return True

        approval = Approval()
        result = await approval.request_approval("wf-1", "step-1", {})
        assert result is True

    @pytest.mark.asyncio
    async def test_has_cancel_approval_method(self) -> None:
        """Test protocol has cancel_approval async method."""

        class Approval:
            async def cancel_approval(self, approval_id: str) -> None:
                pass

        approval = Approval()
        await approval.cancel_approval("approval-1")

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Approval:
            async def request_approval(
                self,
                workflow_id: str,
                step_id: str,
                context: Any,
            ) -> bool:
                return False

            async def cancel_approval(self, approval_id: str) -> None:
                pass

        assert isinstance(Approval(), ApprovalProtocol)


class TestExecutionProtocol:
    """Tests for ExecutionProtocol."""

    @pytest.mark.asyncio
    async def test_has_execute_method(self) -> None:
        """Test protocol has execute async method."""

        class Execution:
            async def execute(self, workflow_id: str, context: Any) -> Any:
                return {"status": "completed"}

        execution = Execution()
        result = await execution.execute("wf-1", {})
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_has_resume_method(self) -> None:
        """Test protocol has resume async method."""

        class Execution:
            async def resume(self, execution_id: str, result: Any) -> Any:
                return {"status": "resumed"}

        execution = Execution()
        result = await execution.resume("exec-1", {})
        assert result["status"] == "resumed"

    @pytest.mark.asyncio
    async def test_has_cancel_method(self) -> None:
        """Test protocol has cancel async method."""

        class Execution:
            async def cancel(self, execution_id: str) -> None:
                pass

        execution = Execution()
        await execution.cancel("exec-1")

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Execution:
            async def execute(self, workflow_id: str, context: Any) -> Any:
                return {}

            async def resume(self, execution_id: str, result: Any) -> Any:
                return {}

            async def cancel(self, execution_id: str) -> None:
                pass

        assert isinstance(Execution(), ExecutionProtocol)
