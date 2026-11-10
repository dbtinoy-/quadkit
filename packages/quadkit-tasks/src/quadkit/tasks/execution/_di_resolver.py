"""DI container dependency resolution for task handlers.

Extracted from ``worker.py`` to keep that module under the 500-LOC limit.
"""

from __future__ import annotations

import inspect
import types
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from quadkit.logging import get_logger, safe_error_type

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

_PRIMITIVE_JOB_ARG_TYPES: tuple[type[Any], ...] = (
    str,
    int,
    float,
    bool,
    bytes,
    dict,
    list,
    tuple,
    set,
    frozenset,
)


def _is_service_annotation(annotation: Any) -> bool:
    """Return True if *annotation* names a DI-resolvable class or ``Annotated`` binding."""
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        return bool(
            args
            and inspect.isclass(args[0])
            and args[0] not in _PRIMITIVE_JOB_ARG_TYPES
        )
    return inspect.isclass(annotation) and annotation not in _PRIMITIVE_JOB_ARG_TYPES


def _extract_optional_service_type(annotation: Any) -> Any:
    """Return the service annotation inside ``Svc | None`` / ``Optional[Svc]``, or None."""
    if get_origin(annotation) not in (Union, types.UnionType):
        return None
    non_none = [arg for arg in get_args(annotation) if arg is not type(None)]
    if len(non_none) != 1:
        return None
    candidate = non_none[0]
    if _is_service_annotation(candidate):
        return candidate
    return None


async def resolve_handler_dependencies(
    handler: Callable[..., Any],
    provided_args: tuple[Any, ...],
    provided_kwargs: dict[str, Any],
    container: Any,
    *,
    logger_instance: Any | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    """Resolve handler dependencies from DI container.

    Uses inspection to determine handler parameters, then resolves
    any missing parameters from the container.

    Args:
        handler: Handler function to inspect.
        provided_args: Arguments already provided by the job.
        provided_kwargs: Keyword arguments already provided by the job.
        container: DI container instance for resolution.
        logger_instance: Optional bound logger. Falls back to module logger.

    Returns:
        Tuple of (resolved_args, resolved_kwargs) to pass to handler.
    """
    _log = logger_instance or logger

    # Unwrap handler to get the original function (needed for @task/@scheduled decorators)
    original_handler = handler
    while hasattr(handler, "_func"):
        inner = handler._func
        # Unwrap staticmethod if present
        if hasattr(inner, "__func__"):
            inner = inner.__func__
        if inner is handler:
            break
        handler = inner

    cls_handler: Any = handler
    is_class_task = inspect.isclass(handler) and callable(
        getattr(handler, "execute", None)
    )
    signature_target: Any = cls_handler.execute if is_class_task else handler

    if container is None:
        _log.debug(
            "No DI container available for handler %s", original_handler.__name__
        )
        return list(provided_args), provided_kwargs

    _log.debug(
        "DI container available for handler %s: %s",
        original_handler.__name__,
        type(container).__name__,
    )

    try:
        sig = inspect.signature(signature_target)
        _log.debug("Handler %s signature: %s", original_handler.__name__, sig)
    except (ValueError, TypeError) as e:
        _log.error(
            "task_handler_signature_unavailable",
            error_type=safe_error_type(e),
        )
        return list(provided_args), provided_kwargs

    params = [
        (param_name, param)
        for idx, (param_name, param) in enumerate(sig.parameters.items())
        if not (is_class_task and idx == 0 and param_name == "self")
    ]

    # Build a set of parameter names that are already provided
    provided_param_names = set()
    for param_name, _ in params[: len(provided_args)]:
        provided_param_names.add(param_name)
    provided_param_names.update(provided_kwargs.keys())

    # Carry job-provided positional args through unchanged (mirrors the
    # no-container path); only missing annotated params are DI-resolved.
    resolved_args: list[Any] = list(provided_args)
    resolved_kwargs: dict[str, Any] = dict(provided_kwargs)

    _log.debug(
        "Handler %s has %d parameters, provided args: %d, provided kwargs: %s",
        original_handler.__name__,
        len(params),
        len(provided_args),
        list(provided_kwargs.keys()),
    )

    # Iterate through parameters and resolve missing ones from container
    for param_name, param in params:
        if param_name in provided_param_names:
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        # Get annotation - handle forward references
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            _log.debug("Skipping param %s - no type annotation", param_name)
            continue

        # Handle string annotations (forward references)
        if isinstance(annotation, str):
            # Try to resolve the string to an actual type using get_type_hints.
            # Pass include_extras=True so Annotated[..., Named("...")] markers
            # survive PEP 563 forward-reference evaluation.
            try:
                hints = get_type_hints(signature_target, include_extras=True)
                if param_name in hints:
                    annotation = hints[param_name]
                else:
                    _log.debug("Could not find type hint for %s", param_name)
                    continue
            except Exception as e:
                # Not a debug line: the handler will be called without this
                # argument and dead-letter with "missing N required positional
                # arguments" on every tick. The usual cause is the type being
                # imported under ``TYPE_CHECKING`` together with
                # ``from __future__ import annotations``.
                _log.warning(
                    "task_dependency_annotation_unresolvable",
                    error_type=safe_error_type(e),
                )
                continue

        # A parameter with a default whose annotation is not a service — an
        # ``Optional[str]`` job argument, a ``list[int] | None`` — is the
        # job's to pass, not the container's to resolve. However, an optional
        # service dependency ``Svc | None = None`` unwraps cleanly to ``Svc``.
        optional_service = _extract_optional_service_type(annotation)
        if optional_service is not None:
            annotation = optional_service
        elif (
            param.default is not inspect.Parameter.empty
            and not _is_service_annotation(annotation)
        ):
            _log.debug(
                "Skipping param %s - job argument with a default, not a service",
                param_name,
            )
            continue

        # Try to resolve the type annotation
        _log.debug(
            "Attempting to resolve dependency for handler %s: %s (type: %s)",
            original_handler.__name__,
            param_name,
            annotation,
        )

        try:
            resolved = await container.resolve(annotation)
            if resolved is not None:
                resolved_kwargs[param_name] = resolved
                _log.debug(
                    "Resolved dependency for handler %s: %s=%s",
                    original_handler.__name__,
                    param_name,
                    type(resolved).__name__,
                )
        except Exception as e:
            # A required service the container cannot provide will dead-letter
            # the job; an optional one is a quiet default. Log only static
            # events and the exception category to avoid exposing job context.
            if param.default is inspect.Parameter.empty:
                _log.warning(
                    "task_dependency_unresolved param=%s error_type=%s",
                    param_name,
                    safe_error_type(e),
                )
            else:
                _log.debug(
                    "task_optional_dependency_unresolved",
                    error_type=safe_error_type(e),
                )

    return resolved_args, resolved_kwargs
