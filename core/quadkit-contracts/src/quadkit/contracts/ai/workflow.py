"""Workflow protocols for the Quadkit Framework.

Defines the structural contracts for the workflow graph execution
engine in ``quadkit-ai-workflow``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.ai.exceptions import WorkflowError

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result


@dataclass(frozen=True)
class WorkflowResult:
    """Final result of a workflow graph execution.

    Carries the terminal shared state, any structured output produced
    by the workflow, and an execution trace for debugging.
    """

    final_state: dict[str, Any]
    output: Any = None
    trace: list[str] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a key from the final state with an optional default."""
        return self.final_state.get(key, default)


@runtime_checkable
class AIWorkflowNodeProtocol(Protocol):
    """AI-domain graph node protocol for workflow execution.

    A workflow node represents a single unit of work in a directed graph.
    Nodes receive the current shared state, perform their work, and
    return a state update dict that is merged into the global state.
    """

    @property
    def name(self) -> str:
        """Unique node identifier within the workflow."""
        ...

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute this node with the current workflow state.

        Args:
            state: Current shared workflow state.

        Returns:
            Dict of state updates to merge into the shared state.
        """
        ...


@runtime_checkable
class WorkflowProtocol(Protocol):
    """Structural protocol for executable workflows.

    A workflow is a directed graph of :class:`AIWorkflowNodeProtocol` nodes
    connected by conditional or unconditional edges.  Execution is async,
    stateful, and supports cycles (with a max-iteration guard).
    """

    async def execute(
        self,
        input: str,
        *,
        config: Any | None = None,
        state: dict[str, Any] | None = None,
    ) -> Result[WorkflowResult, WorkflowError]:
        """Execute the workflow graph.

        Args:
            input: Initial user input injected into the workflow state.
            config: Optional workflow configuration (e.g. max_iterations).
            state: Optional pre-populated initial state.

        Returns:
            ``Ok(WorkflowResult)`` with the final state and execution trace,
            or ``Err(WorkflowError)`` on failure.
        """
        ...


__all__ = [
    "AIWorkflowNodeProtocol",
    "WorkflowProtocol",
    "WorkflowResult",
]
