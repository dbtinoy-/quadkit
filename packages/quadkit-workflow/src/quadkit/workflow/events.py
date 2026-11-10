"""Root event surface for quadkit-workflow.

Defines domain events emitted by the workflow orchestration layer (pipeline
starts, completions, and failures).  Consumers subscribe via
:class:`~quadkit.contracts.events.protocols.EventBusProtocol`.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent

__all__ = [
    "WorkflowCompletedEvent",
    "WorkflowFailedEvent",
    "WorkflowStartedEvent",
]


@dataclass(frozen=True, init=False)
class WorkflowStartedEvent(DomainEvent):
    """Emitted when a workflow instance begins execution.

    Attributes:
        workflow_id: Unique identifier of the workflow instance.
        workflow_name: Human-readable name of the workflow definition.
    """

    workflow_id: str
    workflow_name: str


@dataclass(frozen=True, init=False)
class WorkflowCompletedEvent(DomainEvent):
    """Emitted when a workflow instance reaches a terminal success state.

    Attributes:
        workflow_id: Unique identifier of the workflow instance.
        workflow_name: Human-readable name of the workflow definition.
    """

    workflow_id: str
    workflow_name: str


@dataclass(frozen=True, init=False)
class WorkflowFailedEvent(DomainEvent):
    """Emitted when a workflow instance terminates due to an unrecoverable error.

    Attributes:
        workflow_id: Unique identifier of the workflow instance.
        workflow_name: Human-readable name of the workflow definition.
        error: Human-readable description of the failure reason.
    """

    workflow_id: str
    workflow_name: str
    error: str
