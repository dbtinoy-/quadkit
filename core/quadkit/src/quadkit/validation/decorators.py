"""Validation decorator for automatic input validation.

Applies a :class:`~quadkit.validation.validator.ValidatorImpl` to function
arguments before the function body executes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import functools
import inspect
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from quadkit.validation.engine.validator import ValidatorImpl

F = TypeVar("F", bound=Callable[..., Any])


def validate_input(validator: ValidatorImpl[Any]) -> Callable[[F], F]:
    """Decorator that validates function args/kwargs before execution.

    If the first positional argument is a dict it is validated directly;
    otherwise keyword arguments are validated as a dict.  On validation
    failure a :class:`~quadkit.contracts.validation.ValidationError` is
    raised **before** the wrapped function runs.

    Example::

        @validate_input(
            ValidatorImpl()
            .rule("name", required(), min_length(2))
            .rule("email", required(), email_format())
        )
        async def create_user(name: str, email: str) -> User: ...
    """

    def decorator(func: F) -> F:
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            data = _extract_data(param_names, args, kwargs)
            result = validator.validate(data)
            if result.is_err():
                raise result.unwrap_err()
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            data = _extract_data(param_names, args, kwargs)
            result = validator.validate(data)
            if result.is_err():
                raise result.unwrap_err()
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _extract_data(
    param_names: list[str],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Build a validation dict from positional + keyword arguments.

    If the first positional arg is already a dict it is used directly so
    that ``create_user({"name": "Jo", "email": "jo@x.com"})`` works too.
    """
    if args and isinstance(args[0], dict):
        return args[0]

    data = dict(kwargs)
    # Map positional args to their parameter names (skip ``self``/``cls``)
    start = 0
    if param_names and param_names[0] in ("self", "cls"):
        start = 1
    for idx, value in enumerate(args[start:], start=start):
        if idx < len(param_names):
            data[param_names[idx]] = value
    return data
