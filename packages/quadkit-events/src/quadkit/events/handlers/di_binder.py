"""DI dependency binding helpers for function-based event handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace
import functools
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

from quadkit.contracts.exceptions.base import QuadkitError
from quadkit.events.decorators.handlers import get_handler_info, set_handler_info
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.events import EventBusProtocol

logger = get_logger(__name__)


def _is_resolvable_service_type(annotation: Any) -> bool:
    """Return True when *annotation* is a class or ``Annotated[Cls, ...]`` binding."""
    if isinstance(annotation, type) and annotation is not types.NoneType:
        return True
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        return bool(
            args and isinstance(args[0], type) and args[0] is not types.NoneType
        )
    return False


def _unwrap_service_type(annotation: Any) -> tuple[Any, bool]:
    """Return ``(service_type, is_optional_union)`` for a parameter type hint."""
    if _is_resolvable_service_type(annotation):
        return annotation, False

    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        non_none = [arg for arg in get_args(annotation) if arg is not types.NoneType]
        has_none = len(non_none) != len(get_args(annotation))
        if len(non_none) == 1 and _is_resolvable_service_type(non_none[0]):
            return non_none[0], has_none

    return None, False


async def _resolve_dependency(
    container: Any,
    service_type: Any,
    *,
    allow_missing: bool,
) -> Any:
    """Resolve *service_type* from *container*, bypassing module visibility when supported."""
    resolver = getattr(container, "resolve", None)
    supports_bypass = False
    if resolver is not None:
        try:
            params = inspect.signature(resolver).parameters.values()
            supports_bypass = any(
                p.name == "bypass_visibility" or p.kind is inspect.Parameter.VAR_KEYWORD
                for p in params
            )
        except (TypeError, ValueError):
            supports_bypass = False

    try:
        if resolver is not None and supports_bypass:
            return await resolver(service_type, bypass_visibility=True)
        if allow_missing and hasattr(container, "resolve_optional"):
            return await container.resolve_optional(service_type)
        if resolver is not None:
            return await resolver(service_type)
    except (
        LookupError,
        RuntimeError,
        ValueError,
        OSError,
        TypeError,
        QuadkitError,
    ):
        if allow_missing:
            return None
        raise
    return None


async def bind_event_handler(
    handler: Callable[..., Awaitable[Any]],
    container: Any,
    *,
    skip_if_missing_deps: bool = True,
) -> Callable[[Any], Awaitable[Any]] | None:
    """Bind extra DI-injected parameters on an async ``@event_handler`` function.

    Parameters after the leading ``event`` argument are resolved from
    *container* using their type annotations:
    - Parameters typed ``Svc | None`` or carrying a default value receive
      ``None`` / their default when ``Svc`` is not registered.
    - Required parameters missing from *container* return ``None`` (skipping
      subscription) when ``skip_if_missing_deps=True``, or raise when ``False``.
    - Handlers taking only ``(event)`` are returned unchanged with zero wrapper
      allocation.
    """
    sig = inspect.signature(handler)
    extra_params = [
        p
        for p in list(sig.parameters.values())[1:]
        if p.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]
    if not extra_params:
        return handler

    try:
        hints = get_type_hints(handler, include_extras=True)
    except Exception:  # noqa: BLE001
        hints = {}

    bound_kwargs: dict[str, Any] = {}
    for param in extra_params:
        raw_hint = hints.get(param.name, param.annotation)
        service_type, is_optional_union = _unwrap_service_type(raw_hint)
        has_default = param.default is not inspect.Parameter.empty
        is_optional = is_optional_union or has_default

        if service_type is None:
            if has_default:
                bound_kwargs[param.name] = param.default
                continue
            if skip_if_missing_deps:
                logger.debug(
                    "event_handler_skipped_untyped_dependency",
                    handler=getattr(handler, "__qualname__", repr(handler)),
                    parameter=param.name,
                )
                return None
            msg = (
                f"Event handler {getattr(handler, '__qualname__', handler)!r} "
                f"parameter {param.name!r} requires a resolvable type annotation"
            )
            raise TypeError(msg)

        resolved = await _resolve_dependency(
            container,
            service_type,
            allow_missing=is_optional or skip_if_missing_deps,
        )
        if resolved is None:
            if is_optional:
                bound_kwargs[param.name] = param.default if has_default else None
                continue
            logger.debug(
                "event_handler_skipped_missing_dependency",
                handler=getattr(handler, "__qualname__", repr(handler)),
                dependency=getattr(service_type, "__name__", repr(service_type)),
            )
            return None

        bound_kwargs[param.name] = resolved

    @functools.wraps(handler)
    async def _bound(event: Any) -> Any:
        return await handler(event, **bound_kwargs)

    info = get_handler_info(handler)
    if info is not None:
        set_handler_info(
            _bound,
            replace(
                info,
                handler=_bound,
                is_async=True,
            ),
        )

    return _bound


async def subscribe_event_handlers(
    event_bus: EventBusProtocol,
    container: Any,
    handlers: Sequence[Callable[..., Awaitable[Any]]],
    *,
    skip_if_missing_deps: bool = True,
) -> list[tuple[type, Callable[[Any], Awaitable[Any]]]]:
    """Bind DI dependencies for *handlers* and subscribe them onto *event_bus*.

    Returns the list of ``(event_type, subscribed_callable)`` pairs so callers
    can unsubscribe cleanly during provider shutdown.
    """
    subscriptions: list[tuple[type, Callable[[Any], Awaitable[Any]]]] = []
    for handler in handlers:
        info = get_handler_info(handler)
        event_types: list[type] = list(info.message_types) if info is not None else []
        if not event_types:
            event_types = list(getattr(handler, "_handles_events", ()) or ())
        if not event_types:
            logger.warning(
                "event_handler_missing_event_types",
                handler=getattr(handler, "__qualname__", repr(handler)),
            )
            continue

        bound = await bind_event_handler(
            handler,
            container,
            skip_if_missing_deps=skip_if_missing_deps,
        )
        if bound is None:
            continue

        for event_type in event_types:
            event_bus.subscribe(event_type, bound)
            subscriptions.append((event_type, bound))

    return subscriptions


__all__ = ["bind_event_handler", "subscribe_event_handlers"]
