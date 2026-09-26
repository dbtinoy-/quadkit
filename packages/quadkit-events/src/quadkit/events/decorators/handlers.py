"""Handler registration decorators.

This module provides decorators for registering command, query, and event handlers
in a concise, declarative style.

Example:
    ```python
    from quadkit.events.decorators import command_handler, query_handler, event_handler

    @command_handler(CreateUserCommand)
    async def create_user_handler(command: CreateUserCommand) -> str:
        # Handle command
        return user_id

    @query_handler(GetUserQuery)
    async def get_user_handler(query: GetUserQuery) -> UserDTO:
        # Handle query
        return user_dto

    @event_handler(UserCreatedEvent)
    async def user_created_handler(event: UserCreatedEvent) -> None:
        # Handle event
        pass
    ```
"""

from __future__ import annotations

from dataclasses import dataclass, field
import functools
import itertools
from typing import (
    TYPE_CHECKING,
    Any,
    ParamSpec,
    TypeVar,
)

from quadkit.contracts.domain import DomainEvent
from quadkit.events.constants import HandlerType

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.events.messages import Command, Event, Query

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


@dataclass
class HandlerInfo:
    """Metadata about a registered handler."""

    handler_type: str  # command, query, event, saga, projection
    message_types: list[type]
    handler: Callable
    name: str
    module: str
    is_async: bool
    metadata: dict[str, Any] = field(default_factory=dict)


# Module-level; populated at import time when decorator expressions are evaluated.
# Cleared via clear_handlers() for test teardown.
_handler_registry: dict[str, list[HandlerInfo]] = {
    HandlerType.COMMAND: [],
    HandlerType.QUERY: [],
    HandlerType.EVENT: [],
    HandlerType.SAGA: [],
    HandlerType.PROJECTION: [],
}


def get_handler_info(handler: Callable) -> HandlerInfo | None:
    """Get handler info for a decorated handler.

    Args:
        handler: The handler function or class.

    Returns:
        HandlerInfo if the handler is registered, None otherwise.
    """
    # First check the global registry
    for handler_list in _handler_registry.values():
        for info in handler_list:
            if info.handler is handler:
                return info

    # Fallback to checking attached metadata (for backward compatibility)
    if hasattr(handler, "_handler_info"):
        handler_info: HandlerInfo | None = handler._handler_info
        return handler_info

    return None


def set_handler_info(handler: Callable, info: HandlerInfo) -> None:
    """Set handler info for a decorated handler.

    Args:
        handler: The handler function or class.
        info: The HandlerInfo to attach.
    """
    # Attach metadata to handler (using private attribute for internal use)
    handler._handler_info = info  # type: ignore[attr-defined]


def get_all_handlers(handler_type: str | None = None) -> list[HandlerInfo]:
    """Get all registered handlers.

    Args:
        handler_type: Optional filter by handler type
            ("command", "query", "event", "saga", "projection").

    Returns:
        List of HandlerInfo for matching handlers.
    """
    if handler_type:
        return list(_handler_registry.get(handler_type, []))
    return list(itertools.chain.from_iterable(_handler_registry.values()))


def clear_handlers(handler_type: str | None = None) -> None:
    """Clear registered handlers.

    Args:
        handler_type: Optional handler type to clear.
            If None, clears all handlers.
    """
    if handler_type:
        _handler_registry[handler_type] = []
    else:
        for key in _handler_registry:
            _handler_registry[key] = []


def _is_async_callable(func: Callable) -> bool:
    """Check if a callable is async."""
    import asyncio

    return asyncio.iscoroutinefunction(func)


def command_handler(
    command_type: type[Command],
    *,
    name: str | None = None,
    **metadata: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to register a function as a command handler.

    Args:
        command_type: The Command class this handler handles.
        name: Optional custom name for the handler.
        **metadata: Additional metadata to attach to the handler.

    Returns:
        Decorator function.

    Example:
        ```python
        @command_handler(CreateUserCommand)
        async def handle_create_user(command: CreateUserCommand) -> str:
            user = await user_service.create(command.username, command.email)
            return user.user_id
        ```
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        handler_name = name or func.__name__
        module = func.__module__

        info = HandlerInfo(
            handler_type=HandlerType.COMMAND,
            message_types=[command_type],
            handler=func,
            name=handler_name,
            module=module,
            is_async=_is_async_callable(func),
            metadata=metadata,
        )
        _handler_registry[HandlerType.COMMAND].append(info)

        # Attach metadata to function
        set_handler_info(func, info)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        set_handler_info(wrapper, info)
        return wrapper

    return decorator


def query_handler(
    query_type: type[Query],
    *,
    name: str | None = None,
    cacheable: bool = False,
    cache_ttl: int | None = None,
    **metadata: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to register a function as a query handler.

    Args:
        query_type: The Query class this handler handles.
        name: Optional custom name for the handler.
        cacheable: Whether results can be cached.
        cache_ttl: Cache time-to-live in seconds.
        **metadata: Additional metadata to attach to the handler.

    Returns:
        Decorator function.

    Example:
        ```python
        @query_handler(GetUserQuery, cacheable=True, cache_ttl=300)
        async def handle_get_user(query: GetUserQuery) -> UserDTO:
            return await user_repository.get(query.user_id)
        ```
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        handler_name = name or func.__name__
        module = func.__module__

        full_metadata = {
            "cacheable": cacheable,
            "cache_ttl": cache_ttl,
            **metadata,
        }

        info = HandlerInfo(
            handler_type=HandlerType.QUERY,
            message_types=[query_type],
            handler=func,
            name=handler_name,
            module=module,
            is_async=_is_async_callable(func),
            metadata=full_metadata,
        )
        _handler_registry[HandlerType.QUERY].append(info)

        set_handler_info(func, info)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        set_handler_info(wrapper, info)
        return wrapper

    return decorator


def event_handler(
    event_type: type[DomainEvent],
    *,
    name: str | None = None,
    priority: int = 0,
    **metadata: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to register a function as an event handler.

    Args:
        event_type: The Event class this handler handles.
        name: Optional custom name for the handler.
        priority: Handler priority (higher = executed first).
        **metadata: Additional metadata to attach to the handler.

    Returns:
        Decorator function.

    Example:
        ```python
        @event_handler(UserCreatedEvent, priority=10)
        async def send_welcome_email(event: UserCreatedEvent) -> None:
            await email_service.send_welcome(event.email)
        ```
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        handler_name = name or func.__name__
        module = func.__module__

        full_metadata = {
            "priority": priority,
            **metadata,
        }

        info = HandlerInfo(
            handler_type=HandlerType.EVENT,
            message_types=[event_type],
            handler=func,
            name=handler_name,
            module=module,
            is_async=_is_async_callable(func),
            metadata=full_metadata,
        )
        _handler_registry[HandlerType.EVENT].append(info)

        set_handler_info(func, info)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        set_handler_info(wrapper, info)
        return wrapper

    return decorator


def multi_event_handler(
    *event_types: type[Event],
    name: str | None = None,
    priority: int = 0,
    **metadata: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to register a function as a handler for multiple event types.

    Args:
        *event_types: The Event classes this handler handles.
        name: Optional custom name for the handler.
        priority: Handler priority (higher = executed first).
        **metadata: Additional metadata to attach to the handler.

    Returns:
        Decorator function.

    Example:
        ```python
        @multi_event_handler(UserCreatedEvent, UserUpdatedEvent)
        async def update_search_index(event: Event) -> None:
            await search_service.index_user(event.aggregate_id)
        ```
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        handler_name = name or func.__name__
        module = func.__module__

        full_metadata = {
            "priority": priority,
            **metadata,
        }

        info = HandlerInfo(
            handler_type=HandlerType.EVENT,
            message_types=list(event_types),
            handler=func,
            name=handler_name,
            module=module,
            is_async=_is_async_callable(func),
            metadata=full_metadata,
        )
        _handler_registry[HandlerType.EVENT].append(info)

        set_handler_info(func, info)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        set_handler_info(wrapper, info)
        return wrapper

    return decorator


def saga(
    *,
    name: str | None = None,
    timeout: float | None = None,
    **metadata: Any,
) -> Callable[[type[T]], type[T]]:
    """Decorator to register a class as a saga.

    Args:
        name: Optional custom name for the saga.
        timeout: SagaProtocol timeout in seconds.
        **metadata: Additional metadata to attach to the saga.

    Returns:
        Decorator function.

    Example:
        ```python
        @saga(timeout=300)
        class OrderFulfillmentSaga(SagaProtocol):
            @SagaStep(start=True)
            async def create_order(self, context: SagaContext):
                ...

            @SagaStep(after=OrderCreatedEvent)
            async def reserve_inventory(self, context: SagaContext):
                ...
        ```
    """

    def decorator(cls: type[T]) -> type[T]:
        saga_name = name or cls.__name__
        module = cls.__module__

        full_metadata = {
            "timeout": timeout,
            **metadata,
        }

        info = HandlerInfo(
            handler_type=HandlerType.SAGA,
            message_types=[],  # Sagas handle multiple events
            handler=cls,
            name=saga_name,
            module=module,
            is_async=True,  # Sagas are always async
            metadata=full_metadata,
        )
        _handler_registry[HandlerType.SAGA].append(info)

        set_handler_info(cls, info)
        return cls

    return decorator


def projection(
    *,
    name: str | None = None,
    **metadata: Any,
) -> Callable[[type[T]], type[T]]:
    """Decorator to register a class as a projection.

    Args:
        name: Optional custom name for the projection.
        **metadata: Additional metadata to attach to the projection.

    Returns:
        Decorator function.

    Example:
        ```python
        @projection(name="user-read-model")
        class UserProjection(ProjectionProtocol):
            async def on_UserCreatedEvent(self, event: UserCreatedEvent):
                self.users[event.aggregate_id] = {
                    "id": event.aggregate_id,
                    "username": event.username,
                }
        ```
    """

    def decorator(cls: type[T]) -> type[T]:
        projection_name = name or cls.__name__
        module = cls.__module__

        info = HandlerInfo(
            handler_type=HandlerType.PROJECTION,
            message_types=[],  # Projections handle multiple events
            handler=cls,
            name=projection_name,
            module=module,
            is_async=True,  # Projections are always async
            metadata=metadata,
        )
        _handler_registry[HandlerType.PROJECTION].append(info)

        set_handler_info(cls, info)
        return cls

    return decorator
