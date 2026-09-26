"""Event bus service using Result pattern for error handling.

This service demonstrates the Result[T, EventError] pattern for event operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions.events import (
    DuplicateHandlerError,
    EventError,
    HandlerNotFoundError,
)
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.events.protocols import (
        EventHandlerProtocol,
        EventMiddlewareProtocol,
    )

logger = get_logger(__name__)


class EventBusWithResultPattern:
    """Event bus using Result pattern for event operations.

    This bus handles event publication and subscription with explicit
    Result[None, EventError] returns instead of raising exceptions or
    bare success signals.
    """

    def __init__(self) -> None:
        """Initialize the event bus with empty handler registry."""
        self._handlers: dict[type, list[EventHandlerProtocol]] = {}
        self._middleware: list[EventMiddlewareProtocol] = []

    def subscribe(
        self,
        event_type: type,
        handler: EventHandlerProtocol,
    ) -> Result[None, EventError]:
        """Subscribe a handler to an event type.

        Args:
            event_type: Event class to subscribe to
            handler: Handler implementing EventHandlerProtocol

        Returns:
            Ok(None) if successful, Err(EventError) if handler already subscribed
        """
        try:
            if event_type not in self._handlers:
                self._handlers[event_type] = []

            # Check for duplicate handler
            if handler in self._handlers[event_type]:
                return Err(
                    DuplicateHandlerError(
                        f"Handler already subscribed to {event_type.__name__}",
                        message_type=event_type.__name__,
                    )
                )

            self._handlers[event_type].append(handler)
            logger.info(
                "handler_subscribed",
                event_type=event_type.__name__,
                handler_count=len(self._handlers[event_type]),
            )
            return Ok(None)
        except Exception as e:  # noqa: BLE001 — event handler isolation; must not propagate handler exceptions to bus
            logger.error("subscription_failed: %s", e)
            return Err(EventError(f"Failed to subscribe handler: {e}"))

    def unsubscribe(
        self,
        event_type: type,
        handler: EventHandlerProtocol,
    ) -> Result[None, EventError]:
        """Unsubscribe a handler from an event type.

        Args:
            event_type: Event class to unsubscribe from
            handler: Handler to remove

        Returns:
            Ok(None) if successful, Err(HandlerNotFoundError) if not subscribed
        """
        try:
            if (
                event_type not in self._handlers
                or handler not in self._handlers[event_type]
            ):
                return Err(
                    HandlerNotFoundError(
                        f"Handler not subscribed to {event_type.__name__}",
                        handler_type=type(handler).__name__,
                        message_type=event_type.__name__,
                    )
                )

            self._handlers[event_type].remove(handler)
            logger.info(
                "handler_unsubscribed",
                event_type=event_type.__name__,
                handler_count=len(self._handlers[event_type]),
            )
            return Ok(None)
        except Exception as e:  # noqa: BLE001 — event handler isolation; must not propagate handler exceptions to bus
            logger.error("unsubscription_failed: %s", e)
            return Err(EventError(f"Failed to unsubscribe handler: {e}"))

    async def publish(
        self,
        event: Any,
    ) -> Result[None, EventError]:
        """Publish an event to all subscribed handlers.

        Args:
            event: Domain event to publish

        Returns:
            Ok(None) if all handlers succeeded, Err(EventError) if any handler failed
        """
        try:
            event_type = type(event)

            # Check if handlers exist for this event type
            handlers = self._handlers.get(event_type, [])
            if not handlers:
                logger.warning(
                    "no_handlers_for_event",
                    event_type=event_type.__name__,
                )
                return Ok(None)  # No handlers is not an error

            # Execute all handlers, collecting first error if any occurs
            for handler in handlers:
                result = await handler.handle(event)
                if result.is_err():
                    error = result.unwrap_err()
                    logger.error(
                        "handler_failed",
                        event_type=event_type.__name__,
                        handler=type(handler).__name__,
                        error=str(error),
                    )
                    return Err(
                        EventError(f"Handler {type(handler).__name__} failed: {error}")
                    )

            logger.info(
                "event_published",
                event_type=event_type.__name__,
                handler_count=len(handlers),
            )
            return Ok(None)
        except Exception as e:  # noqa: BLE001 — event handler isolation; must not propagate handler exceptions to bus
            logger.error("event_publication_failed: %s", e)
            return Err(EventError(f"Event publication failed: {e}"))

    def add_middleware(
        self,
        middleware: EventMiddlewareProtocol,
    ) -> Result[None, EventError]:
        """Add a middleware to the event bus.

        Args:
            middleware: Middleware to add

        Returns:
            Ok(None) on success, Err(EventError) on failure
        """
        try:
            self._middleware.append(middleware)
            logger.info(
                "middleware_added",
                middleware_type=type(middleware).__name__,
                total_middleware=len(self._middleware),
            )
            return Ok(None)
        except Exception as e:  # noqa: BLE001 — event handler isolation; must not propagate handler exceptions to bus
            logger.error("middleware_addition_failed: %s", e)
            return Err(EventError(f"Failed to add middleware: {e}"))

    def remove_middleware(
        self,
        middleware: EventMiddlewareProtocol,
    ) -> Result[None, EventError]:
        """Remove a middleware from the event bus.

        Args:
            middleware: Middleware to remove

        Returns:
            Ok(None) on success, Err(EventError) if not found
        """
        try:
            if middleware not in self._middleware:
                return Err(
                    EventError(f"Middleware {type(middleware).__name__} not registered")
                )

            self._middleware.remove(middleware)
            logger.info(
                "middleware_removed",
                middleware_type=type(middleware).__name__,
                total_middleware=len(self._middleware),
            )
            return Ok(None)
        except Exception as e:  # noqa: BLE001 — event handler isolation; must not propagate handler exceptions to bus
            logger.error("middleware_removal_failed: %s", e)
            return Err(EventError(f"Failed to remove middleware: {e}"))

    def get_subscription_count(self, event_type: type) -> Result[int, EventError]:
        """Get number of handlers subscribed to an event type.

        Args:
            event_type: Event class to check

        Returns:
            Ok(count) with handler count, Err(EventError) on failure
        """
        try:
            count = len(self._handlers.get(event_type, []))
            return Ok(count)
        except Exception as e:  # noqa: BLE001 — event handler isolation; must not propagate handler exceptions to bus
            logger.error("subscription_count_failed: %s", e)
            return Err(EventError(f"Failed to get subscription count: {e}"))


__all__ = ["EventBusWithResultPattern"]
