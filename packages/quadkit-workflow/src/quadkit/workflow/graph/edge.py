"""Workflow edge types connecting nodes in the graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quadkit.logging import safe_error_type

if TYPE_CHECKING:
    from collections.abc import Callable


def _logger() -> Any:
    from quadkit.logging import get_logger

    return get_logger(__name__)


@dataclass(frozen=True)
class WorkflowEdge:
    """A directed edge in the workflow graph.

    Edges connect a *source* node to a *target* node.  An optional
    *condition* callable gates the edge: if provided, the edge is
    traversed only when ``condition(state)`` is truthy.  Edges without
    a condition are always traversed (unconditional/always edges).

    For parallel branches, list multiple edges from the same source nodes;
    :class:`~quadkit.workflow.graph.engine.WorkflowEngine` will
    collect all edges whose conditions are satisfied and execute them
    concurrently when ``GraphConfig.parallel_branches`` is ``True``.

    Attributes:
        source: Name of the originating node.
        target: Name of the destination node.
        condition: Optional callable ``(state: dict) -> bool``.
            When ``None`` the edge is unconditional.
        label: Optional human-readable label for documentation/debugging.
        is_parallel: Hint that this edge should be executed concurrently
            with sibling edges from the same source.  The engine enables
            parallelism automatically when multiple conditions are satisfied;
            this flag provides an explicit override.
    """

    source: str
    target: str
    condition: Callable[[dict[str, Any]], bool] | None = field(
        default=None, compare=False
    )
    label: str = ""
    is_parallel: bool = False

    def is_active(self, state: dict[str, Any]) -> bool:
        """Return ``True`` if this edge should be traversed given *state*.

        Args:
            state: Current workflow state dict.

        Returns:
            ``True`` for unconditional edges or when the condition is met.
        """
        if self.condition is None:
            return True
        try:
            return bool(self.condition(state))
        except Exception as exc:  # noqa: BLE001 — condition error => edge inactive
            _logger().warning(
                "edge_condition_error",
                error_type=safe_error_type(exc),
            )
            return False


__all__ = ["WorkflowEdge"]
