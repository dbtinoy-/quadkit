"""Workflow node types and base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any


class NodeType(StrEnum):
    """Enumeration of built-in workflow node types."""

    AGENT = "agent"
    """Executes an ``AgentProtocol``."""

    TOOL = "tool"
    """Executes a ``ToolProtocol``."""

    LLM = "llm"
    """Executes a raw LLM call with a prompt template."""

    GATE = "gate"
    """Routing node that does not execute logic — decides the next node."""

    HUMAN = "human"
    """Pauses execution and waits for human input."""

    SUBWORKFLOW = "subworkflow"
    """Executes a nested :class:`~quadkit.workflow.graph.engine.WorkflowEngine`."""

    CUSTOM = "custom"
    """User-defined node type."""


class AbstractWorkflowNode(ABC):
    """Abstract base class for all workflow nodes.

    All built-in and custom nodes inherit from this class.  The only
    required override is :meth:`execute`.

    Args:
        name: Unique node identifier within the workflow graph.
        node_type: The :class:`NodeType` label for this node.
    """

    def __init__(self, name: str, node_type: NodeType = NodeType.CUSTOM) -> None:
        self._name = name
        self._node_type = node_type

    @property
    def name(self) -> str:
        """Unique node identifier."""
        return self._name

    @property
    def node_type(self) -> NodeType:
        """Type label for this node."""
        return self._node_type

    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute this node and return a state-update dict.

        Args:
            state: Current shared workflow state (read-only reference;
                mutations are applied via the returned dict).

        Returns:
            Dict of key-value pairs to merge into the shared state.
            Return an empty dict if no state updates are needed.
        """


__all__ = ["AbstractWorkflowNode", "NodeType"]
