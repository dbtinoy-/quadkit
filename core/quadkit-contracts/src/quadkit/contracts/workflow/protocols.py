"""Workflow orchestration protocols for Quadkit Framework.

Defines protocols for pipeline execution, bulk processing, and saga
coordination. These are the contracts that quadkit-workflow implements.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, TypeVar, runtime_checkable

from quadkit.contracts.workflow.types import (
    StateTransitionRecord as StateTransitionRecord,
)

StepResult = TypeVar("StepResult")


@runtime_checkable
class WorkflowGraphProtocol(Protocol):
    """Protocol for workflow DAG/graph representations."""

    def add_node(self, node_id: str, node: Any) -> None: ...
    def add_edge(self, from_id: str, to_id: str) -> None: ...
    def get_node(self, node_id: str) -> Any | None: ...
    def topological_order(self) -> list[str]: ...


@runtime_checkable
class WorkflowNodeProtocol(Protocol):
    """Protocol for individual workflow step nodes.

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
class ApprovalProtocol(Protocol):
    """Protocol for human-in-the-loop approval gates."""

    async def request_approval(
        self,
        workflow_id: str,
        step_id: str,
        context: Any,
    ) -> bool: ...

    async def cancel_approval(self, approval_id: str) -> None: ...


@runtime_checkable
class ExecutionProtocol(Protocol):
    """Protocol for workflow execution engines."""

    async def execute(self, workflow_id: str, context: Any) -> Any: ...
    async def resume(self, execution_id: str, result: Any) -> Any: ...
    async def cancel(self, execution_id: str) -> None: ...


__all__ = [
    "ApprovalProtocol",
    "BulkProcessorProtocol",
    "ExecutionProtocol",
    "PipelineContextProtocol",
    "PipelineProtocol",
    "PipelineStepProtocol",
    "SagaManagerProtocol",
    "SagaProtocol",
    "SagaState",
    "SagaStoreProtocol",
    "StateMachineProtocol",
    "StatePersistenceProtocol",
    "StateTransitionRecord",
    "StepResult",
    "WorkflowGraphProtocol",
    "WorkflowNodeProtocol",
]


class SagaState(StrEnum):
    """Lifecycle states for an orchestration saga.

    Transitions:
        PENDING → RUNNING → COMPLETED
        PENDING → RUNNING → COMPENSATING → FAILED
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPENSATING = "compensating"
    COMPLETED = "completed"
    FAILED = "failed"


@runtime_checkable
class SagaStoreProtocol(Protocol):
    """Protocol for durable saga state persistence.

    Implementations back the store with a database or cache so that
    saga state survives process restarts and multi-worker deployments.
    """

    async def save(
        self,
        saga_id: str,
        state: SagaState,
        data: dict[str, Any],
    ) -> None:
        """Persist the current saga state and its associated data.

        Args:
            saga_id: Stable identifier for the saga instance.
            state: Current lifecycle state.
            data: Arbitrary saga-specific payload (must be JSON-serialisable).
        """
        ...

    async def load(
        self,
        saga_id: str,
    ) -> tuple[SagaState, dict[str, Any]] | None:
        """Load persisted saga state.

        Args:
            saga_id: Stable identifier for the saga instance.

        Returns:
            A ``(state, data)`` tuple, or ``None`` if no record exists.
        """
        ...

    async def delete(self, saga_id: str) -> None:
        """Remove a completed or failed saga record.

        Args:
            saga_id: Stable identifier for the saga instance.
        """
        ...


@runtime_checkable
class PipelineContextProtocol(Protocol):
    """Protocol for step-to-step data passing within a pipeline.

    Provides typed access to intermediate results and shared metadata
    accumulated as the pipeline executes each step.
    """

    def get_result(
        self, step_name: str
    ) -> Any:  # Intentional: step results are heterogeneous by design
        """Return the result stored for the named step.

        Args:
            step_name: Unique name of the step whose result to retrieve.

        Returns:
            The stored result value, or ``None`` if the step has not run.
        """
        ...

    def set_result(
        self, step_name: str, value: Any
    ) -> None:  # Intentional: stores any step output
        """Store a result value for the named step.

        Args:
            step_name: Unique name of the step producing the result.
            value: Result value to store.
        """
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Arbitrary metadata shared across all steps in the pipeline."""
        ...


@runtime_checkable
class PipelineStepProtocol(Protocol):
    """Protocol for a single executable step within a pipeline.

    Each step receives the shared context, performs its work, and stores
    its output via ``context.set_result``.
    """

    @property
    def name(self) -> str:
        """Unique name identifying this step within its pipeline."""
        ...

    async def execute(self, context: PipelineContextProtocol) -> StepResult:
        """Execute the step using the shared pipeline context.

        Args:
            context: Shared context supplying previous step results.

        Returns:
            The step's output value.
        """
        ...


@runtime_checkable
class PipelineProtocol(Protocol):
    """Protocol for a composable, sequential pipeline of steps.

    A pipeline collects named steps and executes them in registration
    order, passing a shared context between them.
    """

    def add_step(self, step: PipelineStepProtocol) -> None:
        """Register a step to be executed as part of this pipeline.

        Args:
            step: Step to append to the execution sequence.
        """
        ...

    async def execute(
        self, initial_context: dict[str, Any] | None = None
    ) -> StepResult:
        """Execute all registered steps in order.

        Args:
            initial_context: Optional seed data for the pipeline context.

        Returns:
            The result produced by the final step.
        """
        ...


@runtime_checkable
class BulkProcessorProtocol(Protocol):
    """Protocol for processing a batch of items through a pipeline.

    Implementations receive a homogeneous list of items and return a
    list of processed results in the same order.
    """

    async def process_batch(self, items: list[Any]) -> list[Any]:
        """Process a batch of items.

        Args:
            items: Input items to process.

        Returns:
            Processed results, one entry per input item.
        """
        ...


@runtime_checkable
class SagaProtocol(Protocol):
    """Protocol for saga / process-manager implementations.

    Sagas coordinate long-running business processes that span multiple
    aggregates by reacting to domain events and dispatching commands.
    """

    async def handle(
        self, event: Any
    ) -> list[Any]:  # Intentional: domain events and commands are heterogeneous
        """Handle a domain event and produce commands.

        Args:
            event: Domain event to handle.

        Returns:
            List of commands to dispatch to the command bus.
        """
        ...


@runtime_checkable
class SagaManagerProtocol(Protocol):
    """Protocol for saga lifecycle management.

    The manager routes incoming events to all registered sagas and
    coordinates their execution.
    """

    async def process(
        self, event: Any
    ) -> None:  # Intentional: domain events are heterogeneous
        """Process an event through all relevant sagas.

        Args:
            event: Domain event to route and process.
        """
        ...


@runtime_checkable
class StateMachineProtocol(Protocol):
    """Protocol for finite state machine implementations.

    A state machine manages transitions between named states according to
    a defined set of allowed transitions.  Callers check
    :meth:`can_transition` before calling :meth:`transition` to avoid
    raising :exc:`~quadkit.contracts.workflow.StateError`.
    """

    @property
    def current_state(self) -> str:
        """The name of the current state.

        Returns:
            String name of the active state.
        """
        ...

    @property
    def version(self) -> int:
        """Current state version for optimistic concurrency control.

        Returns:
            Monotonic transition version starting at ``0``.
        """
        ...

    def can_transition(self, event: str) -> bool:
        """Return whether *event* is a valid trigger from the current state.

        Args:
            event: The event name to check.

        Returns:
            ``True`` when the transition is permitted; ``False`` otherwise.
        """
        ...

    async def transition(self, event: str) -> str:
        """Trigger *event*, advancing to the next state.

        Args:
            event: The event name that triggers the transition.

        Returns:
            The name of the new current state.

        Raises:
            StateError: When *event* is not permitted from the current state.
        """
        ...

    async def recover(self, machine_id: str | None = None) -> str:
        """Recover current state from persisted transitions.

        Args:
            machine_id: Optional machine identifier override. Implementations
                may use the configured default when omitted.

        Returns:
            Recovered current state name.
        """
        ...


@runtime_checkable
class StatePersistenceProtocol(Protocol):
    """Protocol for durable state transition persistence.

    Implementations persist each transition as an append-only event stream so
    a state machine can recover after process restarts and enforce optimistic
    concurrency via transition versions.
    """

    async def append_transition(
        self,
        machine_id: str,
        from_state: str,
        event: str,
        to_state: str,
        expected_version: int,
    ) -> int:
        """Persist a transition with optimistic version check.

        Args:
            machine_id: Stable state machine identifier.
            from_state: Previous state.
            event: Transition trigger.
            to_state: New state.
            expected_version: Version caller believes is current.

        Returns:
            Newly persisted version.

        Raises:
            RuntimeError: When optimistic locking fails.
        """
        ...

    async def load_transitions(self, machine_id: str) -> list[StateTransitionRecord]:
        """Load persisted transitions ordered by ascending version.

        Args:
            machine_id: Stable state machine identifier.

        Returns:
            List of transition records in order.
        """
        ...

    async def get_current_version(self, machine_id: str) -> int:
        """Return current persisted version for *machine_id*.

        Args:
            machine_id: Stable state machine identifier.

        Returns:
            Latest transition version, or ``0`` when no transitions exist.
        """
        ...
