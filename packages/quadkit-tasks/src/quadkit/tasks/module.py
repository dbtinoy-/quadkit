"""Background task processing module for dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.infra.tasks import TaskExecutorProtocol, TaskQueueProtocol
from quadkit.di.module import DynamicModule, Module, module

if TYPE_CHECKING:
    from quadkit.tasks.config import TaskConfig


@module(is_global=True)
class TasksModule(Module):
    """Background task workers, scheduling, and async job queues.

    Call :meth:`configure` to configure the task-processing subsystem.

    Usage (in-memory queue for development)::

        from quadkit.tasks.backends.memory import MemoryTaskQueue

        @module(
            imports=[TasksModule.configure(queue=MemoryTaskQueue())]
        )
        class AppModule(Module):
            pass

    Usage (Redis queue for production)::

        from quadkit.tasks.backends.redis import RedisTaskQueue

        @module(
            imports=[
                TasksModule.configure(
                    queue=RedisTaskQueue(url="redis://localhost"),
                    worker_count=4,
                )
            ]
        )
        class AppModule(Module):
            pass
    """

    @classmethod
    def configure(
        cls,
        queue: Any | None = None,
        worker_count: int = 1,
        enable_scheduler: bool = True,
        config: TaskConfig | Any | None = None,
        task_modules: list[str] | tuple[str, ...] | None = None,
        task_packages: list[str] | tuple[str, ...] | None = None,
    ) -> DynamicModule:
        """Create a TasksModule with explicit configuration.

        Args:
            queue: :class:`~quadkit.contracts.infra.tasks.TaskQueueProtocol` implementation.
                Defaults to :class:`~quadkit.tasks.backends.memory.MemoryTaskQueue`.
            worker_count: Number of concurrent task workers.
            enable_scheduler: Whether to enable the job scheduler.
            config: :class:`~quadkit.tasks.config.TaskConfig` or ``None`` to
                resolve the typed ``tasks`` yaml section at boot time.
            task_modules: Exact Python module paths to import during boot and
                scan for decorated ``@task`` / ``@scheduled`` callables.
            task_packages: Package roots to import recursively during boot and
                scan for decorated task callables.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.

        Raises:
            TypeError: If *config* is not a ``TaskConfig`` or ``None``.
        """
        from quadkit.tasks.admin.contributor import TasksAdminContributor
        from quadkit.tasks.admin.handlers.avg_duration import AvgDurationWidgetHandler
        from quadkit.tasks.admin.handlers.tasks_summary import (
            TasksSummaryWidgetHandler,
        )
        from quadkit.tasks.config import TaskConfig as _TaskConfig
        from quadkit.tasks.di.provider import TaskProvider

        if config is not None and not isinstance(config, _TaskConfig):
            raise TypeError(f"config must be TaskConfig, got {type(config).__name__}")

        if queue is None:
            from quadkit.tasks.backends.memory import MemoryTaskQueue

            queue = MemoryTaskQueue()  # type: ignore[abstract]

        return DynamicModule(
            module=cls,
            providers=[
                TaskProvider(
                    queue=queue,
                    worker_count=worker_count,
                    enable_scheduler=enable_scheduler,
                    config=config,
                    task_modules=task_modules,
                    task_packages=task_packages,
                )
            ],
            is_global=True,
            exports=[
                TaskExecutorProtocol,
                TaskQueueProtocol,
                TasksAdminContributor,
                AvgDurationWidgetHandler,
                TasksSummaryWidgetHandler,
            ],
        )

    @classmethod
    def scope(cls, *handlers: type, **kwargs: Any) -> DynamicModule:
        """Scope task handler classes into a feature module.

        Registers the given task handler classes as providers so they are
        discovered and wired by the task executor.  The parent module graph
        must already include :meth:`TasksModule.configure` — this does
        **not** create a new queue or worker pool.

        Uses the anonymous token pattern so both ``configure()`` and
        ``scope()`` can coexist in the same compiled graph without a
        ``ModuleDuplicateError``.

        Example::

            @module(
                imports=[
                    TasksModule.configure(queue=RedisTaskQueue(url=...)),
                    TasksModule.scope(SendEmailTask, GenerateReportTask),
                ]
            )
            class NotificationFeatureModule(Module):
                pass

        Args:
            *handlers: Task handler classes to register.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` scoped to this feature.
        """
        token = type(
            f"_{cls.__name__}Scope",
            (cls,),
            {"__quadkit_scope_of__": cls},
        )
        return DynamicModule(
            module=token,
            providers=list(handlers),
            exports=[],
        )

    @classmethod
    def stub(cls, config: Any = None) -> DynamicModule:
        """Return an in-memory TasksModule for unit testing.

        Uses a :class:`~quadkit.tasks.backends.memory.MemoryTaskQueue`
        with a single worker and no job scheduler.

        Returns:
            A DynamicModule backed by an in-memory task queue.
        """
        from quadkit.tasks.backends.memory import MemoryTaskQueue
        from quadkit.tasks.di.provider import TaskProvider

        return DynamicModule(
            module=cls,
            providers=[
                TaskProvider(
                    queue=MemoryTaskQueue(),  # type: ignore[abstract]
                    worker_count=1,
                    enable_scheduler=False,
                )
            ],
            exports=[TaskExecutorProtocol, TaskQueueProtocol],
        )


__all__ = ["TasksModule"]
