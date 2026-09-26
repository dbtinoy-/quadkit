"""Root hook payload surface for quadkit-tasks.

Defines canonical payload dataclasses for background-task lifecycle hook points.
Actual hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "TaskCompletedHook",
    "TaskEnqueuedHook",
    "TaskFailedHook",
    "TaskStartedHook",
]


@dataclass(frozen=True, kw_only=True)
class TaskEnqueuedHook:
    """Payload fired when a task is placed on the queue.

    Attributes:
        task_name: Name or type label of the enqueued task.
        queue_name: Name of the queue the task was added to.
    """

    task_name: str
    queue_name: str


@dataclass(frozen=True, kw_only=True)
class TaskStartedHook:
    """Payload fired when a worker picks up and begins executing a task.

    Attributes:
        task_name: Name or type label of the task being executed.
        task_id: Unique identifier of the task instance.
    """

    task_name: str
    task_id: str


@dataclass(frozen=True, kw_only=True)
class TaskCompletedHook:
    """Payload fired when a task finishes successfully.

    Attributes:
        task_name: Name or type label of the completed task.
        task_id: Unique identifier of the task instance.
    """

    task_name: str
    task_id: str


@dataclass(frozen=True, kw_only=True)
class TaskFailedHook:
    """Payload fired when a task raises an unhandled exception.

    Attributes:
        task_name: Name or type label of the failed task.
        task_id: Unique identifier of the task instance.
        reason: Short description or exception message.
    """

    task_name: str
    task_id: str
    reason: str
