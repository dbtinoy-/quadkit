"""Pipes decorators for Quadkit Framework.

Provides @use_pipes for applying pipes to controllers and handlers.
"""

from __future__ import annotations

from collections.abc import Callable
import inspect
from typing import Any, TypeVar, cast

from quadkit.web.protocols import PipeProtocol

T = TypeVar("T")


def use_pipes(*pipe_instances: PipeProtocol) -> Callable[[T], T]:
    """Decorator to apply pipes to a class or method.

    Stores pipe metadata on the target for runtime resolution by the ParameterBinder.
    Pipes applied at the class level are inherited by all handler methods.

    Example::

        @use_pipes(ValidationPipe())
        class UserController(Controller):
            @post("/users")
            async def create(self, user: User):
                ...

    Args:
        *pipe_instances: PipeProtocol instances to apply.

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
                if not name.startswith("_"):  # Skip private methods
                    existing: list[PipeProtocol] = (
                        getattr(method, "_quadkit_pipes", None) or []
                    )
                    # Prepend class-level pipes so they run before method-level ones
                    cast("Any", method)._quadkit_pipes = list(pipe_instances) + existing
            return target

        # Apply to a single function/method
        existing_pipes: list[PipeProtocol] = (
            getattr(target, "_quadkit_pipes", None) or []
        )
        cast("Any", target)._quadkit_pipes = existing_pipes + list(pipe_instances)
        return target

    return decorator


__all__ = ["use_pipes"]
