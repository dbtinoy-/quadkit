"""Quadkit Tasks - Background Processing and Task Scheduling.

A comprehensive background task processing system for the Quadkit Framework,
providing task scheduling, job queues, worker management, and monitoring capabilities.

This package follows the Root File Pattern for consistent structure:
- protocols.py: TaskQueueProtocol protocol and abstractions
- types.py: Shared type definitions (Priority)
- config.py: Task configuration settings
- exceptions.py: Task-specific exceptions
- provider.py: Framework integration via provider pattern

Subpackages:
- models/: JobProtocol and Task data models
- backends/: Task queue implementations (memory, Redis, RabbitMQ)
- execution/: Worker pool management, task execution, and health monitoring
- scheduling/: Cron-based job scheduling and templates
- concurrency/: Rate limiting and distributed locking
- workflows/: Task chaining, groups, chords, and conditionals
- middleware/: Pre/post execution hooks and middleware
- progress/: Real-time task progress tracking
- dlq/: Dead letter queue management
- results/: Task result store with async wait
- observability/: Dashboard metrics and execution history
"""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING, Any

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from quadkit.tasks.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.contracts.infra.tasks import TaskExecutorProtocol, TaskQueueProtocol
    from quadkit.tasks.backends import (
        MemoryTaskQueue,
        RabbitMQTaskQueue,
        RedisTaskQueue,
    )
    from quadkit.tasks.background_task_manager import BackgroundTaskManager
    from quadkit.tasks.concurrency import (
        DistributedLockProtocol,
        GlobalRateLimiter,
        QueueRateLimiter,
        UniqueTask,
        distributed_lock,
    )
    from quadkit.tasks.config import (
        NamedTaskConfig,
        TaskBackendConfig,
        TaskConfig,
        TaskRateLimitConfig,
        TaskSchedulerConfig,
        TaskTimeoutConfig,
        TaskWorkerConfig,
    )
    from quadkit.tasks.decorators import scheduled, task
    from quadkit.tasks.di.factories import (
        create_memory_task_provider,
        create_provider_from_config,
        create_rabbitmq_task_provider,
        create_redis_task_provider,
    )
    from quadkit.tasks.di.provider import TaskProvider
    from quadkit.tasks.dispatch import delay
    from quadkit.tasks.dlq import DeadLetterQueue, FailureRecord
    from quadkit.tasks.exceptions import (
        TaskCancelledError,
        TaskError,
        TaskExecutionError,
        TaskNotFoundError,
        TaskTimeoutError,
        TaskValidationError,
    )
    from quadkit.tasks.execution import (
        HandlerRegistry,
        TaskHealth,
        TaskWorker,
        TaskWorkerServices,
        WorkerJobStats,
        WorkerPool,
    )
    from quadkit.tasks.middleware import (
        LoggingMiddleware,
        MetricsMiddleware,
        TaskExecutionContext,
        TaskMiddleware,
        TaskMiddlewarePipeline,
        TimeoutMiddleware,
    )
    from quadkit.tasks.models import JobProtocol, JobResult, JobStatus
    from quadkit.tasks.observability import ExecutionRecord, TaskDashboard
    from quadkit.tasks.progress import (
        CacheBackendProgressStore,
        InMemoryProgressStore,
        InMemoryProgressTracker,
        ProgressInfo,
        ProgressSnapshot,
        ProgressStatus,
        ProgressStore,
        ProgressTracker,
        ProgressTrackerProtocol,
    )
    from quadkit.tasks.results import (
        CacheBackendResultStore,
        InMemoryResultStore,
        ResultStore,
    )
    from quadkit.tasks.scheduled_worker import OnErrorPolicy, ScheduledWorker
    from quadkit.tasks.scheduling import (
        CronExpression,
        JobTemplateProtocol,
        ScheduledJob,
        TaskScheduler,
    )
    from quadkit.tasks.types import Priority
    from quadkit.tasks.workflows import (
        BranchStep,
        StepResult,
        TaskChain,
        TaskChord,
        TaskGroup,
        TaskStep,
        WorkflowResult,
        WorkflowStatus,
        chain,
    )

_LAZY_SUBMODULES = {
    "concurrency": "quadkit.tasks.concurrency",
    "execution": "quadkit.tasks.execution",
    "scheduling": "quadkit.tasks.scheduling",
    "models": "quadkit.tasks.models",
    "backends": "quadkit.tasks.backends",
    "workflows": "quadkit.tasks.workflows",
    "middleware": "quadkit.tasks.middleware",
    "progress": "quadkit.tasks.progress",
    "dlq": "quadkit.tasks.dlq",
    "results": "quadkit.tasks.results",
    "observability": "quadkit.tasks.observability",
}

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # BackgroundTaskManager + ScheduledWorker (QK-006 / QK-005)
    "BackgroundTaskManager": (
        "quadkit.tasks.background_task_manager",
        "BackgroundTaskManager",
    ),
    "ScheduledWorker": ("quadkit.tasks.scheduled_worker", "ScheduledWorker"),
    "OnErrorPolicy": ("quadkit.tasks.scheduled_worker", "OnErrorPolicy"),
    # Module
    "TasksModule": ("quadkit.tasks.module", "TasksModule"),
    "JobProtocol": ("quadkit.tasks.models", "JobProtocol"),
    "JobStatus": ("quadkit.tasks.models", "JobStatus"),
    "JobResult": ("quadkit.tasks.models", "JobResult"),
    "Priority": ("quadkit.tasks.types", "Priority"),
    "TaskError": ("quadkit.tasks.exceptions", "TaskError"),
    "QueueFullError": ("quadkit.tasks.exceptions", "QueueFullError"),
    "TaskNotFoundError": ("quadkit.tasks.exceptions", "TaskNotFoundError"),
    "TaskTimeoutError": ("quadkit.tasks.exceptions", "TaskTimeoutError"),
    "TaskCancelledError": ("quadkit.tasks.exceptions", "TaskCancelledError"),
    "TaskExecutionError": ("quadkit.tasks.exceptions", "TaskExecutionError"),
    "TaskValidationError": ("quadkit.tasks.exceptions", "TaskValidationError"),
    "TaskConfig": ("quadkit.tasks.config", "TaskConfig"),
    "NamedTaskConfig": ("quadkit.tasks.config", "NamedTaskConfig"),
    "TaskBackendConfig": ("quadkit.tasks.config", "TaskBackendConfig"),
    "TaskWorkerConfig": ("quadkit.tasks.config", "TaskWorkerConfig"),
    "TaskSchedulerConfig": ("quadkit.tasks.config", "TaskSchedulerConfig"),
    "TaskRateLimitConfig": ("quadkit.tasks.config", "TaskRateLimitConfig"),
    "TaskTimeoutConfig": ("quadkit.tasks.config", "TaskTimeoutConfig"),
    "TaskQueueProtocol": ("quadkit.contracts.infra.tasks", "TaskQueueProtocol"),
    "TaskExecutorProtocol": ("quadkit.contracts.infra.tasks", "TaskExecutorProtocol"),
    "MemoryTaskQueue": ("quadkit.tasks.backends", "MemoryTaskQueue"),
    "RedisTaskQueue": ("quadkit.tasks.backends", "RedisTaskQueue"),
    "RabbitMQTaskQueue": ("quadkit.tasks.backends", "RabbitMQTaskQueue"),
    "TaskWorker": ("quadkit.tasks.execution", "TaskWorker"),
    "TaskWorkerServices": ("quadkit.tasks.execution", "TaskWorkerServices"),
    "WorkerJobStats": ("quadkit.tasks.execution", "WorkerJobStats"),
    "WorkerPool": ("quadkit.tasks.execution", "WorkerPool"),
    "HandlerRegistry": ("quadkit.tasks.execution", "HandlerRegistry"),
    "TaskHealth": ("quadkit.tasks.execution", "TaskHealth"),
    "TaskScheduler": ("quadkit.tasks.scheduling", "TaskScheduler"),
    "ScheduledJob": ("quadkit.tasks.scheduling", "ScheduledJob"),
    "CronExpression": ("quadkit.tasks.scheduling", "CronExpression"),
    "JobTemplateProtocol": ("quadkit.tasks.scheduling", "JobTemplateProtocol"),
    "TaskProvider": ("quadkit.tasks.di.provider", "TaskProvider"),
    "create_provider_from_config": (
        "quadkit.tasks.di.factories",
        "create_provider_from_config",
    ),
    "create_memory_task_provider": (
        "quadkit.tasks.di.factories",
        "create_memory_task_provider",
    ),
    "create_redis_task_provider": (
        "quadkit.tasks.di.factories",
        "create_redis_task_provider",
    ),
    "create_rabbitmq_task_provider": (
        "quadkit.tasks.di.factories",
        "create_rabbitmq_task_provider",
    ),
    "QueueRateLimiter": ("quadkit.tasks.concurrency", "QueueRateLimiter"),
    "GlobalRateLimiter": ("quadkit.tasks.concurrency", "GlobalRateLimiter"),
    "DistributedLockProtocol": (
        "quadkit.tasks.concurrency",
        "DistributedLockProtocol",
    ),
    "UniqueTask": ("quadkit.tasks.concurrency", "UniqueTask"),
    "distributed_lock": ("quadkit.tasks.concurrency", "distributed_lock"),
    "task": ("quadkit.tasks.decorators", "task"),
    "scheduled": ("quadkit.tasks.decorators", "scheduled"),
    # Dispatch
    "delay": ("quadkit.tasks.dispatch", "delay"),
    # Workflows
    "TaskChain": ("quadkit.tasks.workflows", "TaskChain"),
    "TaskGroup": ("quadkit.tasks.workflows", "TaskGroup"),
    "TaskChord": ("quadkit.tasks.workflows", "TaskChord"),
    "TaskStep": ("quadkit.tasks.workflows", "TaskStep"),
    "BranchStep": ("quadkit.tasks.workflows", "BranchStep"),
    "WorkflowResult": ("quadkit.tasks.workflows", "WorkflowResult"),
    "WorkflowStatus": ("quadkit.tasks.workflows", "WorkflowStatus"),
    "StepResult": ("quadkit.tasks.workflows", "StepResult"),
    "chain": ("quadkit.tasks.workflows", "chain"),
    # Middleware
    "TaskMiddlewarePipeline": (
        "quadkit.tasks.middleware",
        "TaskMiddlewarePipeline",
    ),
    "TaskMiddleware": ("quadkit.tasks.middleware", "TaskMiddleware"),
    "TaskExecutionContext": (
        "quadkit.tasks.middleware",
        "TaskExecutionContext",
    ),
    "LoggingMiddleware": ("quadkit.tasks.middleware", "LoggingMiddleware"),
    "MetricsMiddleware": ("quadkit.tasks.middleware", "MetricsMiddleware"),
    "TimeoutMiddleware": ("quadkit.tasks.middleware", "TimeoutMiddleware"),
    # Progress
    "ProgressTracker": ("quadkit.tasks.progress", "ProgressTracker"),
    "ProgressStore": ("quadkit.tasks.progress", "ProgressStore"),
    "InMemoryProgressStore": ("quadkit.tasks.progress", "InMemoryProgressStore"),
    "InMemoryProgressTracker": ("quadkit.tasks.progress", "InMemoryProgressTracker"),
    "ProgressInfo": ("quadkit.tasks.progress", "ProgressInfo"),
    "ProgressSnapshot": ("quadkit.tasks.progress", "ProgressSnapshot"),
    "ProgressStatus": ("quadkit.tasks.progress", "ProgressStatus"),
    "ProgressTrackerProtocol": ("quadkit.tasks.progress", "ProgressTrackerProtocol"),
    "CacheBackendProgressStore": (
        "quadkit.tasks.progress",
        "CacheBackendProgressStore",
    ),
    # DLQ
    "DeadLetterQueue": ("quadkit.tasks.dlq", "DeadLetterQueue"),
    "FailureRecord": ("quadkit.tasks.dlq", "FailureRecord"),
    # Results
    "ResultStore": ("quadkit.tasks.results", "ResultStore"),
    "InMemoryResultStore": ("quadkit.tasks.results", "InMemoryResultStore"),
    "CacheBackendResultStore": ("quadkit.tasks.results", "CacheBackendResultStore"),
    # Observability
    "TaskDashboard": ("quadkit.tasks.observability", "TaskDashboard"),
    "ExecutionRecord": ("quadkit.tasks.observability", "ExecutionRecord"),
    # Events
    "TaskQueuedEvent": ("quadkit.tasks.events", "TaskQueuedEvent"),
    "TaskCompletedEvent": ("quadkit.tasks.events", "TaskCompletedEvent"),
    "TaskFailedEvent": ("quadkit.tasks.events", "TaskFailedEvent"),
    # Hooks
    "TaskCompletedHook": ("quadkit.tasks.hooks", "TaskCompletedHook"),
    "TaskEnqueuedHook": ("quadkit.tasks.hooks", "TaskEnqueuedHook"),
    "TaskFailedHook": ("quadkit.tasks.hooks", "TaskFailedHook"),
    "TaskStartedHook": ("quadkit.tasks.hooks", "TaskStartedHook"),
}


def __getattr__(name: str) -> Any:
    """Lazy load attributes to avoid circular imports."""
    import importlib

    # Check if it's a lazy class first
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value

    # Check if it's a submodule request
    if name in _LAZY_SUBMODULES:
        return importlib.import_module(_LAZY_SUBMODULES[name])

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """List available attributes for IDE support."""
    return sorted(
        set(__all__) | set(_LAZY_SUBMODULES.keys()) | set(_LAZY_IMPORTS.keys())
    )


__all__ = list(_LAZY_SUBMODULES.keys()) + list(_LAZY_IMPORTS.keys())
