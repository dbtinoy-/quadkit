"""Task and job queue protocols."""

from __future__ import annotations

from quadkit.contracts.infra.tasks.enums import JobStatus, OnErrorPolicy
from quadkit.contracts.infra.tasks.exceptions import TaskQueueError
from quadkit.contracts.infra.tasks.idempotency import (
    IdempotencyResult,
    IdempotencyResultStatus,
)
from quadkit.contracts.infra.tasks.progress import (
    ProgressSnapshot,
    ProgressStatus,
    ProgressTrackerProtocol,
)
from quadkit.contracts.infra.tasks.protocols import (
    DLQProtocol,
    IdempotencyManagerProtocol,
    IdempotentTaskManagerProtocol,
    JobProtocol,
    JobTemplateProtocol,
    TaskExecutorProtocol,
    TaskManagerProtocol,
    TaskProviderProtocol,
    TaskQueueProtocol,
    TaskWorkerProtocol,
)

__all__ = [
    "DLQProtocol",
    "IdempotencyManagerProtocol",
    "IdempotencyResult",
    "IdempotencyResultStatus",
    "IdempotentTaskManagerProtocol",
    "JobProtocol",
    "JobStatus",
    "JobTemplateProtocol",
    "OnErrorPolicy",
    "ProgressSnapshot",
    "ProgressStatus",
    "ProgressTrackerProtocol",
    "TaskExecutorProtocol",
    "TaskManagerProtocol",
    "TaskProviderProtocol",
    "TaskQueueError",
    "TaskQueueProtocol",
    "TaskWorkerProtocol",
]
