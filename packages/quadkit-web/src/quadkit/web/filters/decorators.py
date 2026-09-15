"""Exception filter decorators for Quadkit Framework.

Provides @use_filters for applying exception filters to controllers and handlers.
"""

from __future__ import annotations

from collections.abc import Callable
import inspect
from typing import Any, TypeVar, cast

from quadkit.contracts.web.protocols import ExceptionFilterProtocol

T = TypeVar("T")


def use_filters(*filter_instances: ExceptionFilterProtocol) -> Callable[[T], T]:
    """Decorator to apply exception filters to a class or method.

    Filters handle exceptions raised during the request lifecycle.
    Filters applied at the class level are inherited by all handler methods.

    Example::

        @use_filters(HttpExceptionFilter())
        class UserController(Controller):
            @get("/users/{id}")
            async def get(self, id: str):
                ...

    Args:
        *filter_instances: ExceptionFilterProtocol instances to apply.

    Returns:
        The decorated class or function.
    """

    def decorator(target: T) -> T:
        if inspect.isclass(target):
            # Apply to all methods of the class
            for name, method in inspect.getmembers(
                target,
                predicate=inspect.isfunction,
            ):
                if not name.startswith("_"):
                    existing: list[ExceptionFilterProtocol] = (
                        getattr(method, "__filters__", None) or []
                    )
                    cast("Any", method).__filters__ = list(filter_instances) + existing
            return cast("T", target)

        # Apply to a single function/method
        existing_filters: list[ExceptionFilterProtocol] = (
            getattr(target, "__filters__", None) or []
        )
        cast("Any", target).__filters__ = existing_filters + list(filter_instances)
        return target

    return decorator


__all__ = ["use_filters"]
