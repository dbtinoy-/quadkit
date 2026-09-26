"""Root event surface for quadkit-tasks.

Defines domain events emitted by the task processing system.  Consumers
subscribe via :class:`~quadkit.contracts.events.protocols.EventBusProtocol`.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent

__all__ = [
    "TaskCompletedEvent",
    "TaskFailedEvent",
    "TaskQueuedEvent",
]


@dataclass(frozen=True, kw_only=True)
class TaskQueuedEvent(DomainEvent):
    """Emitted when a task is accepted into a processing queue.

    Attributes:
        task_id: Unique identifier of the queued task.
        queue_name: Name of the queue that accepted the task.
    """

    task_id: str
    queue_name: str


@dataclass(frozen=True, kw_only=True)
class TaskCompletedEvent(DomainEvent):
    """Emitted when a task finishes successfully.

    Attributes:
        task_id: Unique identifier of the completed task.
        worker_id: Identifier of the worker that executed the task.
    """

    task_id: str
    worker_id: str


@dataclass(frozen=True, kw_only=True)
class TaskFailedEvent(DomainEvent):
    """Emitted when a task fails after all retry attempts are exhausted.

    Attributes:
        task_id: Unique identifier of the failed task.
        error: Human-readable description of the failure reason.
    """

    task_id: str
    error: str
