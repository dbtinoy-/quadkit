"""Handler registry for task execution.

This module provides a registry for mapping task names to handler functions.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from quadkit.primitives.registry import Registry
from quadkit.tasks.exceptions import TaskNotFoundError
from quadkit.tasks.execution._invoke import invoke_handler


class HandlerRegistry(Registry[str, Callable[..., Awaitable[Any]]]):
    """Registry for task handlers that also satisfies the TaskExecutorProtocol contract.

    Maps task names to their handler functions. Handlers can be
    registered and retrieved by name. The :meth:`execute` method dispatches
    a task to its registered handler, making this class usable wherever a
    ``TaskExecutorProtocol`` is expected.

    Extends :class:`Registry` for unified introspection and lifecycle hooks.

    Example:
        ```python
        registry = HandlerRegistry()

        @registry.register("send_email")
        async def send_email(to: str, subject: str):
            ...

        handler = registry.get("send_email")
        ```
    """

    def __init__(self) -> None:
        """Initialize handler registry."""
        super().__init__(name="task.handlers", allow_overwrite=True)

    def register(  # type: ignore[override]
        self,
        name: str,
        handler: Callable[..., Awaitable[Any]] | None = None,
    ) -> Callable[..., Any]:
        """Register a task handler.

        Can be used as a decorator or called directly.

        Args:
            name: Task name.
            handler: Handler function (if not using as decorator).

        Returns:
            Handler function or decorator.

        Example:
            ```python
            # As decorator
            @registry.register("task_name")
            async def my_handler(...):
                pass

            # Direct call
            registry.register("task_name", my_handler)
            ```
        """
        if handler is None:
            # Used as decorator
            def decorator(
                func: Callable[..., Awaitable[Any]],
            ) -> Callable[..., Awaitable[Any]]:
                super(HandlerRegistry, self).register(name, func)
                return func

            return decorator
        # Direct registration
        super().register(name, handler)
        return handler

    def register_handler(self, task_name: str, handler: Any) -> None:
        """Register a handler for a task type (``TaskExecutorProtocol`` method).

        This method satisfies the ``register_handler`` requirement defined in
        ``quadkit.contracts.infra.tasks.protocols.TaskExecutorProtocol``.  It is a
        protocol-mandated entry point that delegates directly to :meth:`register`
        so that ``HandlerRegistry`` can be used wherever a ``TaskExecutorProtocol``
        is expected without any additional adapter.  **Do not remove** — the
        protocol contract requires this exact signature.

        Args:
            task_name: Name of the task type.
            handler: Async callable to handle the task.
        """
        super().register(task_name, handler)

    def get_handler(self, task_name: str) -> Any | None:
        """Get the handler for a task type (``TaskExecutorProtocol`` method).

        This method satisfies the ``get_handler`` requirement defined in
        ``quadkit.contracts.infra.tasks.protocols.TaskExecutorProtocol``.  It is a
        protocol-mandated entry point that delegates directly to :meth:`get`
        so that ``HandlerRegistry`` can be used wherever a ``TaskExecutorProtocol``
        is expected without any additional adapter.  **Do not remove** — the
        protocol contract requires this exact signature.

        Args:
            task_name: Name of the task type.

        Returns:
            Handler if registered, ``None`` otherwise.
        """
        return self.get(task_name)

    async def execute(self, task: Any) -> Any:
        """Execute a task using the registered handler (TaskExecutorProtocol protocol).

        Resolves the handler for ``task.name``, then invokes it with
        ``task.args`` and ``task.kwargs``.  Supports both sync and async
        handlers.

        Args:
            task: Task object with ``name``, ``args``, and ``kwargs`` attributes.

        Returns:
            Result returned by the handler.

        Raises:
            TaskNotFoundError: If no handler is registered for the task name.
        """
        handler = self.get(task.name)
        if handler is None:
            raise TaskNotFoundError(
                f"No handler registered for task type: {task.name!r}",
                details={
                    "task": task.name,
                    "registered": sorted(self.keys()),
                },
                hint=f"Register a handler with @task(name={task.name!r}) or task_registry.register({task.name!r}, handler).",
            )
        return await invoke_handler(handler, *task.args, **task.kwargs)

    def remove(self, name: str) -> bool:
        """Remove handler from registry.

        Args:
            name: Task name.

        Returns:
            True if handler was removed.
        """
        return self.unregister(name) is not None

    def list_handlers(self) -> list[str]:
        """List all registered handler names.

        Returns:
            List of task names.
        """
        return list(self.keys())

    def to_dict(self) -> dict[str, Callable[..., Awaitable[Any]]]:
        """Get handlers as dictionary.

        Returns:
            Dictionary of all handlers.
        """
        return dict(self.items())
