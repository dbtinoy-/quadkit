"""Task decorator for simplified task definition.

Provides convenient decorators for defining tasks and scheduled tasks with
queue metadata plus a lightweight discovery registry.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import update_wrapper
from typing import TYPE_CHECKING, Any, Protocol, cast

from quadkit.tasks.models.job import JobProtocol
from quadkit.tasks.types import Priority

if TYPE_CHECKING:
    from quadkit.contracts.infra.tasks import TaskQueueProtocol

    class TaskFunction(Protocol):
        def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

        @classmethod
        def signature(cls, *args: Any, **kwargs: Any) -> JobProtocol: ...

        @classmethod
        async def apply_async(
            cls,
            queue: TaskQueueProtocol,
            *args: Any,
            **kwargs: Any,
        ) -> Any: ...


_REGISTERED_TASKS: dict[str, dict[str, Any]] = {}


def _store_registered_task(
    task_wrapper: Any,
    *,
    module_name: str,
    task_name: str,
) -> None:
    """Store a decorated task wrapper in the module-level registry."""
    _REGISTERED_TASKS.setdefault(module_name, {})[task_name] = task_wrapper


def iter_registered_tasks(module_filters: tuple[str, ...] | None = None) -> list[Any]:
    """Return registered task wrappers, optionally filtered by module roots."""
    if not module_filters:
        return [
            task_wrapper
            for tasks_by_name in _REGISTERED_TASKS.values()
            for task_wrapper in tasks_by_name.values()
        ]

    def _matches(module_name: str) -> bool:
        return any(
            module_name == module_filter or module_name.startswith(f"{module_filter}.")
            for module_filter in module_filters
        )

    matches: list[Any] = []
    for module_name, tasks_by_name in _REGISTERED_TASKS.items():
        if _matches(module_name):
            matches.extend(tasks_by_name.values())
    return matches


def unwrap_task_handler(handler: Callable[..., Any] | Any) -> Callable[..., Any]:
    """Unwrap a decorated task wrapper to its original callable."""
    unwrapped = getattr(handler, "_func", handler)
    if hasattr(unwrapped, "__func__"):
        return cast("Callable[..., Any]", unwrapped.__func__)
    return cast("Callable[..., Any]", unwrapped)


def _clear_registered_tasks(module_filters: tuple[str, ...] | None = None) -> None:
    """Clear the module-level task registry.

    This helper exists for tests that create ephemeral import roots.
    """
    if not module_filters:
        _REGISTERED_TASKS.clear()
        return

    for module_name in list(_REGISTERED_TASKS):
        if any(
            module_name == module_filter or module_name.startswith(f"{module_filter}.")
            for module_filter in module_filters
        ):
            del _REGISTERED_TASKS[module_name]


def task(
    name: str | None = None,
    priority: Priority | int = Priority.NORMAL,
    max_retries: int = 3,
    timeout: float | None = None,
    queue: str = "default",
    idempotency_key: str | None = None,
) -> Callable[[Callable[..., Any]], Any]:
    """Decorator to define a task.

    Converts a regular function into a task that can be enqueued and executed
    by workers.

    Args:
        name: Task name (defaults to function name)
        priority: Task priority (HIGH, NORMAL, LOW)
        max_retries: Maximum retry attempts on failure
        timeout: Execution timeout in seconds
        queue: Queue name for this task
        idempotency_key: Optional key for idempotent execution

    Returns:
        Decorated function with .delay() and .apply_async() methods
    """

    def decorator(func: Callable[..., Any]) -> TaskFunction:
        task_name = name or func.__name__
        module_name = func.__module__

        class TaskFunction:
            """Wrapped task function with queue methods."""

            __module__ = module_name
            _func = staticmethod(func)
            _task_name = task_name
            _task_module = module_name
            _priority = (
                priority
                if isinstance(priority, int)
                else cast("Priority", priority).value
            )
            _max_retries = max_retries
            _timeout = timeout
            _queue = queue
            _idempotency_key = idempotency_key

            def __call__(self, *args: Any, **kwargs: Any) -> Any:
                """Direct function call."""
                return func(*args, **kwargs)

            @classmethod
            def signature(cls, *args: Any, **kwargs: Any) -> JobProtocol:
                """Create task signature without executing.

                Returns:
                    JobProtocol instance ready to be enqueued
                """
                return JobProtocol(
                    id="",
                    name=cls._task_name,
                    args=args,
                    kwargs=kwargs,
                    priority=cls._priority,
                    max_retries=cls._max_retries,
                    idempotency_key=cls._idempotency_key,
                    timeout=cls._timeout,
                )

            @classmethod
            def s(cls, *args: Any, **kwargs: Any) -> JobProtocol:
                """Shorthand for signature().

                Returns:
                    JobProtocol instance ready to be enqueued
                """
                return cls.signature(*args, **kwargs)

            @classmethod
            async def delay(cls, *args: Any, **kwargs: Any) -> Any:
                """Enqueue task for execution (simplified interface)."""
                raise NotImplementedError(
                    "Use TaskProvider.enqueue_job() or apply_async(queue, ...)",
                )

            @classmethod
            async def apply_async(
                cls,
                queue: TaskQueueProtocol,
                *args: Any,
                priority: int | None = None,
                max_retries: int | None = None,
                timeout: float | None = None,
                idempotency_key: str | None = None,
                **kwargs: Any,
            ) -> JobProtocol:
                """Enqueue task for asynchronous execution."""
                from quadkit.tasks.models import JobProtocol

                job = JobProtocol(
                    id="",
                    name=cls._task_name,
                    args=args,
                    kwargs=kwargs,
                    priority=priority if priority is not None else cls._priority,
                    max_retries=(
                        max_retries if max_retries is not None else cls._max_retries
                    ),
                    timeout=timeout if timeout is not None else cls._timeout,
                    idempotency_key=idempotency_key
                    if idempotency_key is not None
                    else cls._idempotency_key,
                )

                await queue.enqueue(job)

                return job

        task_wrapper = TaskFunction()
        update_wrapper(task_wrapper, func)
        _store_registered_task(
            task_wrapper,
            module_name=module_name,
            task_name=task_name,
        )
        return task_wrapper

    return decorator


def scheduled(
    cron: str,
    name: str | None = None,
    priority: Priority | int = Priority.NORMAL,
    max_retries: int = 3,
    timeout: float | None = None,
) -> Callable[[Callable[..., Any]], Any]:
    """Decorator to define a scheduled task.

    Args:
        cron: Cron expression (e.g., "0 9 * * *")
        name: Task name
        priority: Task priority
        max_retries: Maximum retry attempts
        timeout: Execution timeout

    Returns:
        Decorated task function with scheduling metadata
    """

    def decorator(func: Callable[..., Any]) -> Any:
        task_wrapper = task(
            name=name,
            priority=priority,
            max_retries=max_retries,
            timeout=timeout,
        )(func)
        task_wrapper._cron = cron
        return task_wrapper

    return decorator


__all__ = ["scheduled", "task"]
