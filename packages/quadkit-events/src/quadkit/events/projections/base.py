"""Base projection classes for read models.

Projections maintain read-optimized views of data by processing events.
"""

# mypy: disable-error-code = annotation-unchecked

from __future__ import annotations

from abc import ABC, abstractmethod
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.domain import DomainEvent
from quadkit.events.messages.event import Event


class ProjectionStatus(StrEnum):
    """Status of a projection."""

    RUNNING = "running"
    PAUSED = "paused"
    REBUILDING = "rebuilding"
    ERROR = "error"


@dataclass
class ProjectionCheckpoint:
    """Checkpoint for projection position tracking."""

    projection_name: str
    position: int = 0
    last_processed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ProjectionProtocol(ABC):
    """Base class for event projections.

    Projections listen to events and maintain read-optimized views.
    They support rebuilding from event history.

    Example:
        ```python
        class OrderSummaryProjection(ProjectionProtocol):
            def __init__(self, read_model: OrderReadModel):
                self.read_model = read_model

            @property
            def name(self) -> str:
                return "order_summary"

            @property
            def handles(self) -> set[type]:
                return {OrderCreatedEvent, OrderCompletedEvent, OrderCancelledEvent}

            async def apply(self, event: Event) -> None:
                if isinstance(event, OrderCreatedEvent):
                    await self.read_model.create_summary(
                        order_id=event.order_id,
                        customer_id=event.customer_id,
                        status="pending"
                    )
                elif isinstance(event, OrderCompletedEvent):
                    await self.read_model.update_status(
                        event.order_id, "completed"
                    )

            async def reset(self) -> None:
                await self.read_model.truncate_summaries()
        ```
    """

    def __init__(self) -> None:
        """Initialize the projection."""
        self._status: ProjectionStatus = ProjectionStatus.RUNNING
        self._checkpoint: ProjectionCheckpoint | None = (
            None  # Will be initialized lazily to avoid name access
        )
        self._error: str | None = None
        self.idempotent_apply: bool = True  # M-05: Enable idempotent skipping

        # Per-projection event handler registry (registry pattern)
        # Handlers must implement `can_handle(event) -> bool` and
        # `handle_event(event) -> Awaitable[None]`.
        self._registered_event_handlers: list[object] = []
        # Note: don't call `_register_event_handlers` here — subclasses often
        # need to set instance attributes in their own `__init__` before
        # registering handlers. Registration is performed lazily in
        # `_get_event_handler` when needed.

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique projection name."""
        ...

    @property
    @abstractmethod
    def handles(self) -> set[type[Event]]:
        """Set of event types this projection handles."""
        ...

    @property
    def depends_on(self) -> list[str]:
        """List of projection names this projection depends on."""
        return []

    async def apply(self, event: Event) -> None:
        """Apply an event to update the projection.

        M-05: If ``idempotent_apply`` is True, events with a sequence number
        less than or equal to the current projection position are ignored.

        Args:
            event: Event to process
        """
        # M-05: Skip if already processed
        if self.idempotent_apply:
            event_pos = getattr(event, "sequence_number", None)
            if event_pos is not None and event_pos <= self.position:
                return

        # First try to find a decorated handler
        handler = self._get_event_handler(event)
        if handler:
            await handler(event)
        # No fallback shims — unknown events are ignored

    def _get_event_handler(self, event: Event) -> Callable | None:
        """Get the event handler for the given event type.

        Checks, in order:
        1. `@event_handler` decorated methods on the projection
        2. Registered handler objects from the per-projection registry
        """
        event_type = type(event)
        event_name = event_type.__name__

        # 1) Decorator-discovered handlers (existing behaviour)
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if callable(attr) and hasattr(attr, "_handles_event"):
                handler_event = attr._handles_event
                if isinstance(handler_event, str):
                    # Match by event name
                    if handler_event == event_name:
                        from typing import cast

                        return cast("Callable", attr)
                elif handler_event == event_type:
                    from typing import cast

                    return cast("Callable", attr)

        # 2) Per-projection registered handlers (registry pattern)
        # Lazily invoke subclass registration hook if nothing registered yet.
        if not getattr(self, "_registered_event_handlers", []):
            with contextlib.suppress(AttributeError, TypeError):
                self._register_event_handlers()

        for handler in getattr(self, "_registered_event_handlers", []):
            can_handle = getattr(handler, "can_handle", None)
            if not callable(can_handle):
                continue
            try:
                if can_handle(event):
                    # Return a callable wrapper that invokes handler.handle_event
                    async def _wrapper(evt: Event) -> None:
                        await handler.handle_event(evt)

                    return _wrapper
            except (TypeError, ValueError, AttributeError):
                # GuardProtocol against misbehaving handler implementations
                continue

        return None

    def _register_event_handlers(self) -> None:
        """Hook for subclasses to programmatically register event handlers.

        Subclasses may call `self.register_event_handler(handler_instance)` to
        add handler objects that implement `can_handle` and
        `handle_event` methods.
        """
        return

    def register_event_handler(self, handler: object) -> None:
        """Register a per-projection event handler object.

        Handler must implement:
          - can_handle(event) -> bool
          - async handle_event(event) -> None
        """
        if not hasattr(self, "_registered_event_handlers"):
            self._registered_event_handlers = []
        self._registered_event_handlers.append(handler)

    @abstractmethod
    async def reset(self) -> None:
        """Reset projection state for rebuild.

        Override this to clear your read model before rebuild.
        """
        ...

    @property
    def status(self) -> ProjectionStatus:
        """Get projection status."""
        return self._status

    @property
    def checkpoint(self) -> ProjectionCheckpoint:
        """Get current checkpoint."""
        if self._checkpoint is None:
            self._checkpoint = ProjectionCheckpoint(projection_name=self.name)
        return self._checkpoint

    @property
    def position(self) -> int:
        """Get current position in event stream."""
        if self._checkpoint is None:
            self._checkpoint = ProjectionCheckpoint(projection_name=self.name)
        return self._checkpoint.position

    def advance(self, position: int) -> None:
        """Advance checkpoint position."""
        if self._checkpoint is None:
            self._checkpoint = ProjectionCheckpoint(projection_name=self.name)
        self._checkpoint.position = position
        self._checkpoint.last_processed_at = datetime.now(UTC)

    def can_handle(self, event: Event) -> bool:
        """Check if projection handles this event type."""
        return type(event) in self.handles

    def pause(self) -> None:
        """Pause the projection."""
        self._status = ProjectionStatus.PAUSED

    def resume(self) -> None:
        """Resume the projection."""
        self._status = ProjectionStatus.RUNNING

    def set_rebuilding(self) -> None:
        """Set projection to rebuilding status."""
        self._status = ProjectionStatus.REBUILDING

    @property
    def error(self) -> str | None:
        """Get projection error message."""
        return self._error

    def set_error(self, error: str) -> None:
        """Set projection to error status."""
        self._status = ProjectionStatus.ERROR
        self._error = error

    def restore_checkpoint(self, checkpoint: ProjectionCheckpoint) -> None:
        """Restore projection from a checkpoint."""
        self._checkpoint = checkpoint


class InlineProjection(ProjectionProtocol):
    """ProjectionProtocol with inline event handlers.

    Allows defining handlers without subclassing.

    Example:
        ```python
        projection = InlineProjection("order_counts")

        @projection.handle(OrderCreatedEvent)
        async def on_order_created(event: OrderCreatedEvent):
            counts[event.customer_id] = counts.get(event.customer_id, 0) + 1
        ```
    """

    def __init__(self, name: str):
        """Initialize inline projection.

        Args:
            name: ProjectionProtocol name
        """
        super().__init__()
        self._name = name
        self._handlers: dict[type[Event], Callable[[Event], Any]] = {}
        self._reset_handler: Callable[..., Any] | None = None

    @property
    def name(self) -> str:
        """Get projection name."""
        return self._name

    @property
    def handles(self) -> set[type[Event]]:
        """Get handled event types."""
        return set(self._handlers.keys())

    def handle(
        self,
        event_type: type[Event],
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register an event handler.

        Args:
            event_type: Event type to handle

        Returns:
            Decorator function
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._handlers[event_type] = func
            return func

        return decorator

    def on_reset(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to register reset handler.

        Args:
            func: Reset function

        Returns:
            The function
        """
        self._reset_handler = func
        return func

    async def apply(self, event: Event) -> None:
        """Apply event using registered handler."""
        handler = self._handlers.get(type(event))
        if handler:
            import asyncio

            result = handler(event)
            if asyncio.iscoroutine(result):
                await result

    async def reset(self) -> None:
        """Reset using registered handler."""
        if self._reset_handler:
            import asyncio

            result = self._reset_handler()
            if asyncio.iscoroutine(result):
                await result


def event_handler(
    event_type: type[DomainEvent] | str,
) -> Callable[[Callable], Callable]:
    """Decorator to mark a **projection method** as an event handler.

    This is the projection-dispatch decorator — it is **not** the same as
    ``quadkit.events.decorators.handlers.event_handler``, which registers
    standalone handler functions in the global event-bus registry.

    This decorator simply sets the ``_handles_event`` attribute on the method
    so that :meth:`ProjectionProtocol._get_event_handler` can discover and invoke it
    when the projection processes an event.  It accepts either an event class
    or a string name (useful for forward references) and does **not** register
    anything in the global handler registry.

    Example:
        ```python
        class UserProfileProjection(ProjectionProtocol):
            @event_handler(UserRegistered)
            async def on_registered(self, event: UserRegistered) -> None:
                # Update the read model
                pass

            @event_handler("OrderPlaced")  # forward reference via string name
            async def on_order_placed(self, event: OrderPlaced) -> None:
                pass
        ```

    Args:
        event_type: The event type this method handles — either the class itself
            or a string name for forward-reference scenarios.

    Returns:
        Decorator function that tags the method with ``_handles_event``.
    """

    def decorator(func: Callable) -> Callable:
        # Store the event type on the function for later discovery
        from typing import cast

        cast("Any", func)._handles_event = event_type
        return func

    return decorator


__all__ = [
    "InlineProjection",
    "ProjectionCheckpoint",
    "ProjectionProtocol",
    "ProjectionStatus",
    "event_handler",
]
