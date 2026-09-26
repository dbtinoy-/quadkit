"""Task-specific exception hierarchy for the quadkit-tasks package."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions import QuadkitError
from quadkit.contracts.infra.tasks.exceptions import TaskQueueError


class QueueFullError(TaskQueueError):
    """The queue has reached its maximum capacity and cannot accept new tasks.

    The caller should back off and retry after a delay, or apply backpressure.
    """

    _code: str = "QK_ERR_TASK_002"

    def __init__(
        self,
        message: str = "Task queue is full",
        *,
        queue_name: str | None = None,
        capacity: int | None = None,
        **kwargs: Any,
    ) -> None:
        details: dict[str, Any] = {**kwargs.pop("details", {})}
        if queue_name is not None:
            details["queue_name"] = queue_name
        if capacity is not None:
            details["capacity"] = capacity
        super().__init__(message, details=details, **kwargs)


class TaskError(TaskQueueError):
    """Base exception for all task-related errors"""

    _code: str = "QK_ERR_TASK_003"


class TaskNotFoundError(TaskError):
    """Raised when a task cannot be found"""

    _code: str = "QK_ERR_TASK_004"


class TaskTimeoutError(TaskError):
    """Raised when a task execution exceeds timeout"""

    _code: str = "QK_ERR_TASK_005"


class TaskCancelledError(TaskError):
    """Raised when a task is cancelled"""

    _code: str = "QK_ERR_TASK_006"


class TaskExecutionError(TaskError):
    """Raised when a task execution fails"""

    _code: str = "QK_ERR_TASK_007"

    def __init__(
        self,
        message: str,
        original_error: Exception | None = None,
        details: dict[str, Any] | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message, cause=original_error, details=details, hint=hint)
        self.original_error = original_error


class TaskValidationError(TaskError):
    """Raised when task parameters are invalid"""

    _code: str = "QK_ERR_TASK_008"


class DuplicateTaskError(TaskError):
    """Raised when a duplicate task is detected"""

    _code: str = "QK_ERR_TASK_009"


class TaskLockHeldError(TaskError):
    """Raised when an in-memory task lock is already held.

    Raised by the :func:`distributed_lock` context manager when the
    requested key cannot be acquired; yielding a "held" lock that is
    not actually held would silently run supposedly exclusive code.
    """

    _code: str = "QK_ERR_TASK_012"


class TaskDependencyCycleError(TaskError):
    """Raised at registration time when a dependency cycle is detected.

    The scheduler validates the dependency graph upon each :meth:`schedule_job`
    call.  If adding the new job's :attr:`~quadkit.tasks.models.job.JobProtocol.depends_on`
    edges would create a cycle, this exception is raised before the job is stored,
    preventing a runtime deadlock.

    Attributes:
        cycle: Ordered list of job IDs/names that form the cycle
            (e.g. ``["A", "B", "C", "A"]``).
    """

    _code: str = "QK_ERR_TASK_010"

    def __init__(
        self,
        cycle: list[str],
        details: dict[str, Any] | None = None,
        hint: str | None = None,
    ) -> None:
        """Initialise with the detected cycle path.

        Args:
            cycle: Ordered node IDs/names forming the cycle, where the first
                and last elements are the same node that closes the loop.
            details: Optional structured metadata.
            hint: Optional human-readable remediation hint.
        """
        self.cycle = cycle
        cycle_str = " → ".join(cycle)
        super().__init__(
            f"Task dependency cycle detected: {cycle_str}",
            details=details,
            hint=hint or "Remove one of the dependency edges to break the cycle.",
        )


class TaskRegistrationError(QuadkitError):
    """Raised when a scheduled or handler task fails to register."""

    _code: str = "QK_ERR_TASK_011"


__all__ = [
    "DuplicateTaskError",
    "QueueFullError",
    "TaskCancelledError",
    "TaskDependencyCycleError",
    "TaskError",
    "TaskExecutionError",
    "TaskLockHeldError",
    "TaskNotFoundError",
    "TaskRegistrationError",
    "TaskTimeoutError",
    "TaskValidationError",
]
