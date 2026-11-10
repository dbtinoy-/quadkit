"""Task decorator for simplified task definition.

Provides convenient decorators for defining tasks and scheduled tasks with
queue metadata plus a lightweight discovery registry.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import update_wrapper
import inspect
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast, overload

from quadkit.tasks.models.job import JobProtocol
from quadkit.tasks.types import Priority

_ClsT = TypeVar("_ClsT", bound=type[Any])

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
) -> Callable[[Any], Any]:
    """Decorator to define a task.

    Supports both async/sync functions and class-based tasks defining an
    ``execute(self, ...)`` method (such as :class:`ScheduledTask` subclasses).

    Args:
        name: Task name (defaults to function/class name)
        priority: Task priority (HIGH, NORMAL, LOW)
        max_retries: Maximum retry attempts on failure
        timeout: Execution timeout in seconds
        queue: Queue name for this task
        idempotency_key: Optional key for idempotent execution

    Returns:
        Decorated class (preserving class identity) or ``TaskFunction`` wrapper.
    """
    resolved_priority = (
        priority if isinstance(priority, int) else cast("Priority", priority).value
    )

    @overload
    def decorator(func: _ClsT) -> _ClsT: ...

    @overload
    def decorator(func: Callable[..., Any]) -> TaskFunction: ...

    def decorator(func: Any) -> Any:
        task_name = name or func.__name__
        module_name = func.__module__

        def _make_signature(*args: Any, **kwargs: Any) -> JobProtocol:
            return JobProtocol(
                id="",
                name=task_name,
                args=args,
                kwargs=kwargs,
                priority=resolved_priority,
                max_retries=max_retries,
                idempotency_key=idempotency_key,
                timeout=timeout,
            )

        async def _delay(*args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError(
                "Use TaskProvider.enqueue_job() or apply_async(queue, ...)",
            )

        async def _apply_async(
            task_queue: TaskQueueProtocol,
            *args: Any,
            priority: int | None = None,
            max_retries: int | None = None,
            timeout: float | None = None,
            idempotency_key: str | None = None,
            **kwargs: Any,
        ) -> JobProtocol:
            from quadkit.tasks.models import JobProtocol as _JobProtocol

            job = _JobProtocol(
                id="",
                name=task_name,
                args=args,
                kwargs=kwargs,
                priority=priority if priority is not None else resolved_priority,
                max_retries=(
                    max_retries if max_retries is not None else func_max_retries
                ),
                timeout=timeout if timeout is not None else func_timeout,
                idempotency_key=(
                    idempotency_key
                    if idempotency_key is not None
                    else func_idempotency_key
                ),
            )
            await task_queue.enqueue(job)
            return job

        func_max_retries = max_retries
        func_timeout = timeout
        func_idempotency_key = idempotency_key

        if inspect.isclass(func) and callable(getattr(func, "execute", None)):
            cls_target: Any = func
            cls_target._task_name = task_name
            cls_target._task_module = module_name
            cls_target._priority = resolved_priority
            cls_target._max_retries = max_retries
            cls_target._timeout = timeout
            cls_target._queue = queue
            cls_target._idempotency_key = idempotency_key
            if not hasattr(cls_target, "signature"):
                cls_target.signature = staticmethod(_make_signature)
            if not hasattr(cls_target, "s"):
                cls_target.s = staticmethod(_make_signature)
            if not hasattr(cls_target, "delay"):
                cls_target.delay = staticmethod(_delay)
            if not hasattr(cls_target, "apply_async"):
                cls_target.apply_async = staticmethod(_apply_async)

            _store_registered_task(
                cls_target,
                module_name=module_name,
                task_name=task_name,
            )
            return cls_target

        class TaskFunction:
            """Wrapped task function with queue methods."""

            __module__ = module_name
            _func = staticmethod(func)
            _task_name = task_name
            _task_module = module_name
            _priority = resolved_priority
            _max_retries = max_retries
            _timeout = timeout
            _queue = queue
            _idempotency_key = idempotency_key

            def __call__(self, *args: Any, **kwargs: Any) -> Any:
                """Direct function call."""
                return func(*args, **kwargs)

            @classmethod
            def signature(cls, *args: Any, **kwargs: Any) -> JobProtocol:
                """Create task signature without executing."""
                return _make_signature(*args, **kwargs)

            @classmethod
            def s(cls, *args: Any, **kwargs: Any) -> JobProtocol:
                """Shorthand for signature()."""
                return cls.signature(*args, **kwargs)

            @classmethod
            async def delay(cls, *args: Any, **kwargs: Any) -> Any:
                """Enqueue task for execution (simplified interface)."""
                return await _delay(*args, **kwargs)

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
                return await _apply_async(
                    queue,
                    *args,
                    priority=priority,
                    max_retries=max_retries,
                    timeout=timeout,
                    idempotency_key=idempotency_key,
                    **kwargs,
                )

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
    queue: str = "default",
) -> Callable[[Any], Any]:
    """Decorator to define a scheduled task (function or ``ScheduledTask`` class).

    Args:
        cron: Cron expression (e.g., "0 9 * * *")
        name: Task name
        priority: Task priority
        max_retries: Maximum retry attempts
        timeout: Execution timeout
        queue: Queue name for this task

    Returns:
        Decorated class or task wrapper with scheduling metadata.
    """

    @overload
    def decorator(func: _ClsT) -> _ClsT: ...

    @overload
    def decorator(func: Callable[..., Any]) -> Any: ...

    def decorator(func: Any) -> Any:
        task_wrapper = task(
            name=name,
            priority=priority,
            max_retries=max_retries,
            timeout=timeout,
            queue=queue,
        )(func)
        task_wrapper._cron = cron
        return task_wrapper

    return decorator


__all__ = ["scheduled", "task"]
