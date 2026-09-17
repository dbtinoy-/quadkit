"""Task queue error types.

These are the expected, recoverable failure types that task queue operations
can return as ``Err`` values inside ``Result[…, TaskQueueError]``.

Infrastructure failures (broker connection lost, authentication broken)
must still be raised as exceptions — do not wrap them in ``Result``.

Error hierarchy
---------------
::

    TaskQueueError         Base for all expected task queue failures
    ├── QueueFullError     Queue has reached its capacity limit
    └── TaskNotFoundError  (defined in the optional provider; extends TaskQueueError)
"""

from __future__ import annotations

from quadkit.contracts.exceptions.domain import DomainError


class TaskQueueError(DomainError):
    """Base class for expected, recoverable task queue failures.

    All subtypes indicate situations the caller is expected to handle
    gracefully (e.g. retry later, notify the user, fall back).
    """

    _code: str = "QK_ERR_TASK_001"


__all__ = [
    "TaskQueueError",
]
