"""Pipeline step types, saga orchestration types, and graph result types.

Combines pipeline step results (from quadkit.primitives) with saga-specific types
defined in this package, and graph engine result value objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Re-export from contracts — the canonical SagaStep definition lives there so
# that quadkit-events can import SagaStep without depending on quadkit-workflow.
from quadkit.contracts.workflow.steps import SagaStep

# Re-export core step types
from quadkit.primitives.pipeline import StepExecutionResult, StepStatus


@dataclass(frozen=True)
class NodeResult:
    """Result produced by a single workflow graph node execution.

    Attributes:
        node_name: Name of the node that produced this result.
        output: State update dict returned by the node.
        duration_ms: Wall-clock duration of the node execution.
        error: Error message if the node raised; None on success.
        skipped: True when the node was bypassed by conditional routing.
    """

    node_name: str
    output: dict[str, Any]
    duration_ms: float = 0.0
    error: str | None = None
    skipped: bool = False

    @property
    def succeeded(self) -> bool:
        """True when the node completed without error and was not skipped."""
        return self.error is None and not self.skipped


@dataclass
class GraphResult:
    """Aggregate result of a complete graph workflow execution.

    Attributes:
        final_state: The workflow state after all nodes have executed.
        node_results: Ordered list of per-node results.
        iterations: Total graph traversal steps taken.
        duration_ms: Total wall-clock execution time.
        terminated_at: Name of the terminal node that ended execution.
    """

    final_state: dict[str, Any]
    node_results: list[NodeResult] = field(default_factory=list)
    iterations: int = 0
    duration_ms: float = 0.0
    terminated_at: str | None = None

    @property
    def output(self) -> Any:
        """Return the ``output`` key from :attr:`final_state`, or ``None``."""
        return self.final_state.get("output")

    @property
    def succeeded(self) -> bool:
        """True when all executed nodes succeeded."""
        return all(r.succeeded for r in self.node_results if not r.skipped)


__all__ = [
    "GraphResult",
    "NodeResult",
    "SagaStep",
    "StepExecutionResult",
    "StepStatus",
]
