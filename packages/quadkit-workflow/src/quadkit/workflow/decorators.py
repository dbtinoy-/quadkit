"""Consumer-facing decorators for workflow and saga step registration."""

from __future__ import annotations

from collections.abc import Callable
import functools
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def workflow(
    name: str | None = None,
    *,
    timeout: float | None = None,
    retries: int = 0,
) -> Callable[[F], F]:
    """Mark an async function as a workflow definition.

    Attaches workflow metadata used by the execution engine for
    registration, timeout enforcement, and retry policy.

    Args:
        name: Optional workflow name override. Defaults to the function name.
        timeout: Maximum execution time in seconds. None means no limit.
        retries: Number of retry attempts on failure.

    Returns:
        Decorator that attaches workflow metadata to the function.

    Example:
        @workflow(name="onboarding", timeout=300.0, retries=1)
        async def onboarding_workflow(ctx: WorkflowContext) -> None:
            ...
    """

    def decorator(func: F) -> F:
        func.__workflow__ = True  # type: ignore[attr-defined]
        func.__workflow_name__ = name or func.__name__  # type: ignore[attr-defined]
        func.__workflow_timeout__ = timeout  # type: ignore[attr-defined]
        func.__workflow_retries__ = retries  # type: ignore[attr-defined]

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        # functools.wraps only copies __wrapped__, so propagate the metadata
        # to the wrapper that callers (and the registration engine) inspect.
        for attr in (
            "__workflow__",
            "__workflow_name__",
            "__workflow_timeout__",
            "__workflow_retries__",
        ):
            if hasattr(func, attr):
                setattr(wrapper, attr, getattr(func, attr))

        return wrapper  # type: ignore[return-value]

    return decorator


def saga_step(
    name: str | None = None,
    *,
    compensation: Callable[..., Any] | None = None,
) -> Callable[[F], F]:
    """Mark an async function as a saga step with optional compensation.

    A saga step participates in distributed transaction management. If the
    step fails and a compensation handler is provided, it will be invoked
    during rollback.

    Args:
        name: Optional step name override. Defaults to the function name.
        compensation: Async callable to invoke for rollback on failure.

    Returns:
        Decorator that attaches saga metadata to the function.

    Example:
        @saga_step(name="reserve_inventory", compensation=release_inventory)
        async def reserve_inventory(ctx: SagaContext) -> None:
            ...
    """

    def decorator(func: F) -> F:
        func.__saga_step__ = True  # type: ignore[attr-defined]
        func.__saga_step_name__ = name or func.__name__  # type: ignore[attr-defined]
        func.__saga_compensation__ = compensation  # type: ignore[attr-defined]

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        for attr in ("__saga_step__", "__saga_step_name__", "__saga_compensation__"):
            if hasattr(func, attr):
                setattr(wrapper, attr, getattr(func, attr))

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "saga_step",
    "workflow",
]
