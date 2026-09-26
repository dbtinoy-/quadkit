"""Domain event protocols."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result
    from quadkit.contracts.exceptions.events import EventError


@runtime_checkable
class DomainEventPublisherProtocol(Protocol):
    """Protocol for publishing domain events."""

    async def publish(self, event: Any) -> None:
        """Publish a domain event.

        Args:
            event: DomainEvent instance.
        """
        ...


@runtime_checkable
class EventHandlerProtocol(Protocol):
    """Protocol for event handlers."""

    async def handle(self, event: Any) -> Result[None, EventError]:
        """Handle an event.

        Args:
            event: DomainEvent to handle.

        Returns:
            ``Ok(None)`` on success, ``Err(EventError)`` if handling fails
            in an expected, recoverable way.
        """
        ...


@runtime_checkable
class MultiEventHandlerProtocol(Protocol):
    """Protocol for handlers that handle multiple event types."""

    def handles(self) -> list[type]:
        """Get list of event types handled.

        Returns:
            List of event classes.
        """
        ...

    async def handle(self, event: Any) -> Result[None, EventError]:
        """Handle an event.

        Args:
            event: DomainEvent to handle.

        Returns:
            ``Ok(None)`` on success, ``Err(EventError)`` if handling fails
            in an expected, recoverable way.
        """
        ...


@runtime_checkable
class EventBusProtocol(Protocol):
    """Protocol for event bus implementations.

    The event bus manages event publication and subscription.

        Example:
            ```python
            class InMemoryEventBus:
                async def publish(self, event: DomainEvent) -> "Result[None, EventError]":
                    for handler in self._handlers.get(type(event), []):
                        await handler.handle(event)
                    return Ok(None)

                def subscribe(self, event_type, handler):
                    self._handlers.setdefault(event_type, []).append(handler)
        ```
    """

    async def publish(self, event: Any) -> Result[None, EventError]:
        r"""Publish an event to all subscribers.

        Args:
            event: DomainEvent to publish.

        Returns:
            Ok(None) when the event is successfully enqueued for dispatch.
            Err(EventError) when the event cannot be accepted
            (e.g.\ no handlers registered and the bus requires at least one).
        """
        ...

    def subscribe(
        self,
        event_type: type,
        handler: EventHandlerProtocol | Callable[..., Awaitable[Any]],
    ) -> None:
        """Subscribe a handler to an event type.

        Implementations accept either an ``EventHandlerProtocol`` object or a
        plain async callable — the latter is what ``@event_handler`` produces
        and what the flagship
        :class:`~quadkit.events.buses.event.EventBus` dispatches directly.

        Args:
            event_type: Type of event to subscribe to.
            handler: Handler to call when event is published.
        """
        ...

    async def flush(self) -> None:
        """Wait until all pending events have been dispatched.

        Useful in tests and during shutdown to drain in-flight handler
        dispatches before tearing the bus down.  Implemented by the flagship
        :class:`~quadkit.events.buses.event.EventBus`; engines that dispatch
        synchronously may implement it as a no-op.
        """
        ...

    def unsubscribe(
        self,
        event_type: type,
        handler: EventHandlerProtocol | Callable[..., Awaitable[Any]],
    ) -> None:
        """Remove a handler subscription for an event type.

        Args:
            event_type: Type of event to unsubscribe from.
            handler: Handler to remove.
        """
        ...


@runtime_checkable
class EventBusDiagnosticsProtocol(Protocol):
    """Optional diagnostics capability for asynchronous event buses.

    ``EventBusProtocol.publish()`` only promises enqueue acceptance.  A bus
    that dispatches handlers in the background can implement this capability
    to expose settled failures without changing publication semantics.
    """

    @property
    def dispatch_errors(self) -> tuple[Exception, ...]:
        """Return a read-only snapshot of observed handler failures."""
        ...

    def clear_dispatch_errors(self) -> None:
        """Clear the observed handler failures."""
        ...


@runtime_checkable
class EventMiddlewareProtocol(Protocol):
    """Protocol for event bus middleware.

    Middleware intercepts event publication, allowing cross-cutting
    concerns like logging, metrics, or error handling to be applied
    transparently.

    The middleware receives the event and a ``next_handler`` coroutine
    that invokes the next middleware (or the actual handlers).  The
    middleware must call ``next_handler`` to continue the chain.

    Example::

        class LoggingMiddleware:
            async def __call__(self, event: Any, next_handler: Any) -> None:
                logger.info("publishing", event_type=type(event).__name__)
                await next_handler(event)
                logger.info("published", event_type=type(event).__name__)
    """

    async def __call__(self, event: Any, next_handler: Any) -> None:
        """Process an event through this middleware.

        Args:
            event: The domain event being published.
            next_handler: Coroutine to call to continue the middleware
                chain.  Must be awaited for the event to reach handlers.
        """
        ...
