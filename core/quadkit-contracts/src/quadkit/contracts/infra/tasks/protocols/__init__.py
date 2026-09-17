"""Task and job queue protocol class definitions."""

from __future__ import annotations

from quadkit.contracts.infra.tasks.protocols.idempotency import (
    IdempotencyManagerProtocol as IdempotencyManagerProtocol,
)
from quadkit.contracts.infra.tasks.protocols.idempotency import (
    IdempotentTaskManagerProtocol as IdempotentTaskManagerProtocol,
)
from quadkit.contracts.infra.tasks.protocols.queue import DLQProtocol as DLQProtocol
from quadkit.contracts.infra.tasks.protocols.queue import JobProtocol as JobProtocol
from quadkit.contracts.infra.tasks.protocols.queue import (
    JobTemplateProtocol as JobTemplateProtocol,
)
from quadkit.contracts.infra.tasks.protocols.queue import (
    TaskExecutorProtocol as TaskExecutorProtocol,
)
from quadkit.contracts.infra.tasks.protocols.queue import (
    TaskManagerProtocol as TaskManagerProtocol,
)
from quadkit.contracts.infra.tasks.protocols.queue import (
    TaskProviderProtocol as TaskProviderProtocol,
)
from quadkit.contracts.infra.tasks.protocols.queue import (
    TaskQueueProtocol as TaskQueueProtocol,
)
from quadkit.contracts.infra.tasks.protocols.queue import (
    TaskWorkerProtocol as TaskWorkerProtocol,
)

__all__ = [
    "DLQProtocol",
    "IdempotencyManagerProtocol",
    "IdempotentTaskManagerProtocol",
    "JobProtocol",
    "JobTemplateProtocol",
    "TaskExecutorProtocol",
    "TaskProviderProtocol",
    "TaskQueueProtocol",
    "TaskWorkerProtocol",
]
