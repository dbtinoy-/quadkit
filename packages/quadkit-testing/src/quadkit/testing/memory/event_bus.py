"""In-memory event bus implementation for development and testing.

Provides a lightweight publish/subscribe event bus with support for
handler priorities, middleware chains, and configurable error handling.
Handlers are executed sequentially in priority order (lower value = runs
first). When ``on_handler_error`` is provided, individual handler
exceptions are caught and reported rather than aborting remaining handlers.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any

from quadkit.contracts.events import EventBusProtocol as EventBusProtocol
from quadkit.contracts.events import EventHandlerProtocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from quadkit.contracts.core import MiddlewarePipelineProtocol
    from quadkit.contracts.domain.events import DomainEvent


class InMemoryEventBus(EventBusProtocol):
    """Simple in-memory implementation of the EventBusProtocol protocol.

    Handlers are executed sequentially in priority order (lower = first).
    If ``on_handler_error`` is set, handler exceptions are caught and
    reported rather than aborting remaining handlers. This allows resilient
    event processing where a single broken handler does not block others.

    Usage::

        bus = InMemoryEventBus()
        bus.subscribe(OrderCreated, send_email_handler, priority=10)
        bus.subscribe(OrderCreated, update_stats_handler, priority=20)
        await bus.publish(OrderCreated(order_id="123"))

    With error isolation::

        def on_error(event, handler, exc):
            logger.error("Handler %s failed: %s", handler, exc)

        bus = InMemoryEventBus(on_handler_error=on_error)
    """

    def __init__(
        self,
        *,
        on_handler_error: Callable[[DomainEvent, Any, Exception], None] | None = None,
        dead_letter_handler: Callable[[DomainEvent], Any] | None = None,
        handler_timeout: float | None = None,
        scope_factory: Callable[[], AbstractAsyncContextManager[Any]] | None = None,
    ) -> None:
        """Initialize the event bus.

        Args:
            on_handler_error: Optional callback invoked when a handler raises
                an exception. Receives ``(event, handler, exception)``. When
                provided, the bus swallows the exception after calling the
                callback and continues dispatching to remaining handlers.
                When ``None`` (the default), exceptions propagate immediately.
            dead_letter_handler: Optional callback for events that have no
                subscribers. Receives the event instance. Useful for logging
                or forwarding unhandled events.
            handler_timeout: Optional per-handler timeout in seconds. If a
                handler exceeds this duration, an ``asyncio.TimeoutError`` is
                raised (and handled like any other handler error).
            scope_factory: Optional callable returning an async context manager
                representing a DI scope. When provided, each handler invocation
                is wrapped inside ``async with scope_factory():`` so that
                scoped services can be resolved even when handlers run outside
                the originating request context.
        """
        # handlers stored as (priority, handler) tuples, sorted by priority
        self._handlers: dict[
            type | str,
            list[tuple[int, EventHandlerProtocol | Callable[..., Awaitable[Any]]]],
        ] = defaultdict(list)
        # wildcard subscriptions receive every published event regardless of type
        self._wildcard_handlers: list[
            tuple[int, EventHandlerProtocol | Callable[..., Awaitable[Any]]]
        ] = []
        from quadkit.app.pipeline import (
            MiddlewarePipeline as _MiddlewarePipeline,
        )

        self._pipeline: MiddlewarePipelineProtocol = _MiddlewarePipeline()
        self._on_handler_error = on_handler_error
        self._dead_letter_handler = dead_letter_handler
        self._handler_timeout = handler_timeout
        # optional factory of an async DI scope; if provided, each handler is
        # executed inside a fresh context so that scoped dependencies can be
        # resolved safely even when handlers run outside the originating
        # request scope.
        self._scope_factory = scope_factory

    def subscribe(
        self,
        event_type: type | str,
        handler: EventHandlerProtocol | Callable[..., Awaitable[Any]],
        *,
        priority: int = 0,
    ) -> None:
        """Register a handler for a specific event type.

        Handlers with lower priority values are executed first. Handlers
        registered with the same priority run in registration order.

        Args:
            event_type: The domain event class to subscribe to.
            handler: A callable or object with a ``handle`` method.
            priority: Execution order (lower = runs first). Defaults to 0.
        """
        if event_type == "*":
            # wildcard subscription
            self._wildcard_handlers.append((priority, handler))
            self._wildcard_handlers.sort(key=lambda entry: entry[0])
        else:
            self._handlers[event_type].append((priority, handler))
            self._handlers[event_type].sort(key=lambda entry: entry[0])

    def unsubscribe(
        self,
        event_type: type | str,
        handler: EventHandlerProtocol | Callable[..., Awaitable[Any]],
    ) -> None:
        """Remove a previously registered handler for an event type.

        If the handler is not found, this is a no-op.

        Args:
            event_type: The domain event class the handler was subscribed to.
            handler: The handler instance to remove.
        """
        if event_type == "*":
            self._wildcard_handlers = [
                (p, h) for p, h in self._wildcard_handlers if h is not handler
            ]
            return
        handlers = self._handlers.get(event_type)
        if handlers is None:
            return
        self._handlers[event_type] = [(p, h) for p, h in handlers if h is not handler]

    async def flush(self) -> None:
        """Wait until all pending events have been dispatched.

        A no-op here: ``publish`` awaits every handler before it returns, so
        this engine never has an in-flight dispatch to drain. The member
        exists because ``EventBusProtocol`` declares it — the flagship bus
        dispatches in the background and does need it.
        """

    def add_middleware(self, middleware: Any) -> None:
        """Add a middleware function to the event processing chain.

        Middleware wraps the dispatch pipeline and is executed in the order
        added. Each middleware receives ``(event, next_handler)`` and must
        call ``await next_handler(event)`` to continue the chain.

        Args:
            middleware: An async callable with signature
                ``(event, next) -> None``.
        """
        self._pipeline = self._pipeline.add(middleware)

    @property
    def subscriber_count(self) -> int:
        """Total number of handler subscriptions across all event types.

        Wildcard handlers (registered with ``"*"``) are included in this
        count as they receive every event regardless of type.

        Returns:
            The combined count of all registered handler entries.
        """
        return sum(len(handlers) for handlers in self._handlers.values()) + len(
            self._wildcard_handlers
        )

    @property
    def subscribed_types(self) -> set[type]:
        """Set of event types that have at least one subscriber.

        Wildcard subscriptions are not represented here since they are not
        tied to a concrete event class.

        Returns:
            A set of event type classes with active subscriptions.
        """
        return {
            et
            for et, handlers in self._handlers.items()
            if handlers and isinstance(et, type)
        }

    async def publish(self, event: DomainEvent) -> None:  # type: ignore[override]
        """Publish a domain event to all subscribed handlers.

        If middleware is configured, the event passes through the middleware
        chain before reaching handlers. Handlers are dispatched in priority
        order (ascending). When no handlers are subscribed and a
        ``dead_letter_handler`` is configured, the event is forwarded there.

        Args:
            event: The domain event instance to publish.
        """
        await self._pipeline.execute(event, self._dispatch_to_handlers)

    async def publish_many(self, events: list[DomainEvent]) -> None:
        """Publish multiple domain events sequentially.

        Each event is published in order through the full middleware /
        handler pipeline. Errors are handled per-event according to the
        bus configuration.

        Args:
            events: The domain event instances to publish.
        """
        for event in events:
            await self.publish(event)

    async def _dispatch_to_handlers(self, event: DomainEvent) -> None:
        """Dispatch an event directly to all registered handlers in priority order.

        Each handler invocation is isolated in a try/except block. If
        ``on_handler_error`` is configured, exceptions are reported via the
        callback and execution continues with the next handler. Otherwise
        exceptions propagate immediately. When ``handler_timeout`` is set,
        each handler call is wrapped with ``asyncio.wait_for``.

        If no handlers are registered for the event type and a
        ``dead_letter_handler`` is configured, the event is forwarded there.

        Args:
            event: The domain event to dispatch.
        """
        # include both exact-type handlers and wildcard handlers
        handlers = list(self._handlers.get(type(event), [])) + list(
            self._wildcard_handlers
        )
        if not handlers:
            if self._dead_letter_handler is not None:
                import inspect as _inspect

                result = self._dead_letter_handler(event)
                if _inspect.isawaitable(result):
                    await result
            return

        for _priority, handler in handlers:
            # bind handler to default arg to avoid late-binding closure issue
            async def _invoke(_handler: Any = handler) -> None:
                if callable(_handler) and not hasattr(_handler, "handle"):
                    coro = _handler(event)
                else:
                    coro = _handler.handle(event)

                if self._handler_timeout is not None:
                    await asyncio.wait_for(coro, timeout=self._handler_timeout)
                else:
                    await coro

            try:
                if self._scope_factory is not None:
                    # run handler inside provided DI scope
                    async with self._scope_factory() as _scope:
                        await _invoke()
                else:
                    await _invoke()
            except Exception as exc:
                if self._on_handler_error is not None:
                    self._on_handler_error(event, handler, exc)
                else:
                    raise


__all__ = ["InMemoryEventBus"]
