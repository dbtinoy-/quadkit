"""Gate workflow node — routing-only node."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging.factory import get_logger
from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class GateNode(AbstractWorkflowNode):
    """Routing node that forces the graph to branch on state values.

    Args:
        name: Node identifier.
        routes: Mapping of target-node-name to a (state) -> bool predicate.
    """

    def __init__(
        self,
        name: str,
        *,
        routes: dict[str, Callable[[dict[str, Any]], bool]] | None = None,
    ) -> None:
        super().__init__(name, NodeType.GATE)
        self.routes: dict[str, Callable[[dict[str, Any]], bool]] = routes or {}

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return empty dict — routing is handled by WorkflowEdge conditions.

        Args:
            state: Current workflow state (not mutated here).

        Returns:
            Empty dict — gate nodes produce no output.
        """
        logger.debug("gate_node_execute")
        return {}


__all__ = ["GateNode"]
