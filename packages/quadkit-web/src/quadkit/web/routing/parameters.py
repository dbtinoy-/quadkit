"""Parameter decorators for request binding"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quadkit.web.routing.types import RoutableProtocol


def _create_param_decorator(
    param_type: str,
    name: str | None = None,
    default: Any = ...,
    alias: str | None = None,
    validation: Callable[..., Any] | None = None,
    pipes: list[Any] | None = None,
) -> Any:
    """Create a parameter decorator that properly attaches metadata to parameters"""

    metadata = {
        "type": param_type,
        "name": name,
        "default": default,
        "alias": alias,
        "validation": validation,
        "pipes": pipes,
    }

    def decorator(
        param_annotation: Any = None,
    ) -> RoutableProtocol | Callable[[RoutableProtocol], RoutableProtocol]:
        # If used as @path, @query, etc. without parentheses
        if callable(param_annotation):
            # This is the function being decorated
            func: RoutableProtocol = param_annotation
            # For now, we'll store metadata on the function and match by position
            # A more sophisticated implementation would use AST parsing
            func_metadata = getattr(func, "_param_metadata", None)
            if func_metadata is None:
                func_metadata = []
                func._param_metadata = func_metadata
            func_metadata.append(metadata)
            return func

        # If used as @path(), @query(), etc. with parentheses
        def param_decorator(func: RoutableProtocol) -> RoutableProtocol:
            func_metadata = getattr(func, "_param_metadata", None)
            if func_metadata is None:
                func_metadata = []
                func._param_metadata = func_metadata
            # Merge annotation into metadata for this usage
            usage_metadata = metadata.copy()
            usage_metadata["annotation"] = param_annotation
            func_metadata.append(usage_metadata)
            return func

        # Attach metadata to param_decorator as well
        param_decorator._quadkit_param_info = metadata  # type: ignore[attr-defined]
        return param_decorator

    # Attach metadata to the decorator function itself
    decorator._quadkit_param_info = metadata  # type: ignore[attr-defined]
    return decorator


def path(
    alias: str | None = None,
    validation: Callable[..., Any] | None = None,
    pipes: list[Any] | None = None,
) -> Any:
    """Path parameter decorator."""
    return _create_param_decorator(
        "path",
        alias=alias,
        validation=validation,
        pipes=pipes,
    )


# Query Parameters
def query(
    default: Any = ...,
    alias: str | None = None,
    validation: Callable[..., Any] | None = None,
    pipes: list[Any] | None = None,
) -> Any:
    """Query parameter decorator."""
    return _create_param_decorator(
        "query",
        default=default,
        alias=alias,
        validation=validation,
        pipes=pipes,
    )


# Body Parameters
def body(
    default: Any = ...,
    validation: Callable[..., Any] | None = None,
    pipes: list[Any] | None = None,
) -> Any:
    """Request body parameter decorator."""
    return _create_param_decorator(
        "body", default=default, validation=validation, pipes=pipes
    )


# Header Parameters
def header(
    default: Any = ...,
    alias: str | None = None,
    validation: Callable[..., Any] | None = None,
    pipes: list[Any] | None = None,
) -> Any:
    """Header parameter decorator."""
    return _create_param_decorator(
        "header",
        default=default,
        alias=alias,
        validation=validation,
        pipes=pipes,
    )


# Cookie Parameters
def cookie(
    default: Any = ...,
    alias: str | None = None,
    validation: Callable[..., Any] | None = None,
    pipes: list[Any] | None = None,
) -> Any:
    """Cookie parameter decorator."""
    return _create_param_decorator(
        "cookie",
        default=default,
        alias=alias,
        validation=validation,
        pipes=pipes,
    )


# Form Parameters
def form(
    default: Any = ...,
    alias: str | None = None,
    validation: Callable[..., Any] | None = None,
    pipes: list[Any] | None = None,
) -> Any:
    """Form parameter decorator."""
    return _create_param_decorator(
        "form",
        default=default,
        alias=alias,
        validation=validation,
        pipes=pipes,
    )


# File Parameters
def file(
    default: Any = ...,
    validation: Callable[..., Any] | None = None,
    pipes: list[Any] | None = None,
) -> Any:
    """File upload parameter decorator."""
    return _create_param_decorator(
        "file", default=default, validation=validation, pipes=pipes
    )
