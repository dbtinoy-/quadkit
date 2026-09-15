"""Decorator composition utilities.

Allows composing multiple decorators into a single unified decorator.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

F = TypeVar("F", bound=Callable)


def compose(*decorators: Callable[[F], F]) -> Callable[[F], F]:
    """Compose multiple decorators into one.

    The decorators are applied in order from last to first (like function composition).

    Usage:
        @compose(
            version("2"),
            use_guards(AuthGuard),
            use_interceptors(AuditLogInterceptor),
        )
        @post("/admin/action")
        async def perform_action(self, data: ActionDTO):
            ...
    """

    def decorator(func: F) -> F:
        result = func
        # Apply decorators in reverse order so they're applied in the correct order
        for dec in reversed(decorators):
            result = dec(result)
        return result

    return decorator


def api_controller(
    prefix: str = "",
    guards: list[Any] | None = None,
    interceptors: list[Any] | None = None,
    middleware: list[Any] | None = None,
    version: str | None = None,
) -> Callable[[type], type]:
    """Create a controller class with shared configuration.

    Usage:
        @api_controller(
            prefix="/api/v1",
            guards=[AuthGuard],
            interceptors=[LoggingInterceptor],
            version="1",
        )
        class UserController(Controller):
            ...
    """

    def decorator(cls: type) -> type:
        # Store metadata on the class using setattr to prevent mypy attr-defined errors
        if not hasattr(cls, "_controller_config"):
            cast("Any", cls)._controller_config = {}

        config = cast("Any", cls)._controller_config
        config["prefix"] = prefix
        config["guards"] = guards or []
        config["interceptors"] = interceptors or []
        config["middleware"] = middleware or []
        config["version"] = version

        return cls

    return decorator


def merge_metadata(
    *metadatas: dict[str, Any],
    priority: str = "last",
) -> dict[str, Any]:
    """Merge multiple metadata dictionaries.

    Args:
        *metadatas: Multiple metadata dicts to merge
        priority: "first" or "last" - which dict takes precedence on conflicts

    Usage:
        meta1 = {"guards": [AuthGuard], "version": "1"}
        meta2 = {"guards": [AdminGuard], "version": "2"}
        merged = merge_metadata(meta1, meta2, priority="last")
        # Result: {"guards": [AdminGuard], "version": "2"}
    """
    result: dict[str, Any] = {}

    for meta in metadatas:
        for key, value in meta.items():
            if key not in result:
                result[key] = value
            elif priority == "last":
                # Merge lists, override others
                if isinstance(value, list) and isinstance(result[key], list):
                    result[key] = result[key] + value
                else:
                    result[key] = value
            elif isinstance(result[key], list) and isinstance(value, list):
                result[key] = value + result[key]
                # Don't override existing non-list values

    return result


__all__ = [
    "api_controller",
    "compose",
    "merge_metadata",
]
