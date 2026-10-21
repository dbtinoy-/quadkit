"""Event bus implementation for domain event dispatching.

The EventBusProtocol implements the publish-subscribe pattern for domain events.
It dispatches events to multiple handlers and supports:

- Multiple handlers per event (pub/sub pattern)
- Middleware pipeline for cross-cutting concerns
- DI container integration for handler resolution
- Async event dispatching with configurable concurrency
- Dead letter handling for failed events
- Automatic retry for transient failures

Handler dispatch logic (registration lookup, parallel/sequential dispatch,
per-handler retry) lives in :mod:`quadkit.events.buses._dispatch`.

See Also:
    - :class:`quadkit.events.messages.event.Event`: Base event class.
    - :class:`quadkit.events.buses.command.CommandBusProtocol`: Command dispatch.
    - :class:`quadkit.events.middleware.Middleware`: Event middleware.
"""

from __future__ import annotations

import asyncio
from contextlib import nullcontext as _nullcontext
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.events.buses._dispatch import HandlerDispatchMixin
from quadkit.events.buses.base import Bus, MiddlewareFunc
from quadkit.events.config import EventBusConfig
from quadkit.events.exceptions import EventError, EventHandlerError
from quadkit.events.hooks import EventHandledHook, EventPublishedHook
from quadkit.events.messages.event import Event
from quadkit.logging import get_logger

logger = get_logger(__name__)
# Keep explicit marker for P2 drain-loop exception policy: except Exception as exc:


@dataclass
class DispatchResult:
    """Result of an event dispatch operation.

    Attributes:
        success: True if all handlers completed successfully.
        handler_results: List of return values from each handler.
        errors: List of (exception_type, exception_instance) tuples.
    """

    success: bool
    handler_results: list[Any] = field(default_factory=list)
    errors: list[tuple[type, Exception]] = field(default_factory=list)

    def raise_if_errors(self) -> None:
        """Raise if any handler failed. Call explicitly when needed."""
        if self.errors:
            error_count = len(self.errors)
            first_error = self.errors[0][1] if self.errors else None
            error_msg = f"{error_count} handler(s) failed"
            if first_error:
                error_msg += f": {first_error}"
            raise EventError(error_msg, details={"errors": self.errors})

    @property
    def has_errors(self) -> bool:
        """Return True if any handler failed."""
        return len(self.errors) > 0


from quadkit.contracts.events import EventBusProtocol as EventBusProtocol
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core import (
        ChannelProtocol,
        HookRegistryProtocol,
        ParallelProtocol,
    )
    from quadkit.contracts.observability.tracing import TracerProtocol


class EventBusImpl(HandlerDispatchMixin, Bus[Event, None], EventBusProtocol):  # type: ignore[type-var]
    """Event bus for publishing domain events.

    Orchestrates subscription management, per-event-type BoundedChannel
    backpressure (MAJ-11), and background drain tasks. All handler dispatch
    logic (lookup, parallel/sequential dispatch, retry) is provided by
    HandlerDispatchMixin.

    Attributes:
        DEFAULT_MAX_CONCURRENT_HANDLERS: Maximum concurrent handler executions.
        DEFAULT_HANDLER_TIMEOUT_SECONDS: Timeout for each handler execution.
        DEFAULT_RETRY_FAILED_HANDLERS: Whether to retry failed handlers.
        DEFAULT_MAX_HANDLER_RETRIES: Maximum retry attempts per handler.
        DEFAULT_ENABLE_DEAD_LETTER: Whether to enable dead letter queue.
        DEFAULT_ALLOW_NO_HANDLERS: Whether to allow events with no handlers.
        DEFAULT_PARALLEL_DISPATCH: Whether to dispatch handlers in parallel.
        DEFAULT_CONTINUE_ON_ERROR: Whether to continue on handler errors.
    """

    DEFAULT_MAX_CONCURRENT_HANDLERS: int = 10
    DEFAULT_HANDLER_TIMEOUT_SECONDS: float = 30.0
    DEFAULT_RETRY_FAILED_HANDLERS: bool = True
    DEFAULT_MAX_HANDLER_RETRIES: int = 3
    DEFAULT_ENABLE_DEAD_LETTER: bool = True
    DEFAULT_ALLOW_NO_HANDLERS: bool = True
    DEFAULT_PARALLEL_DISPATCH: bool = True
    DEFAULT_CONTINUE_ON_ERROR: bool = True

    def __init__(
        self,
        middlewares: list[MiddlewareFunc] | None = None,
        config: EventBusConfig | None = None,
        parallel: ParallelProtocol | None = None,
        tracer: TracerProtocol | None = None,
        hooks: HookRegistryProtocol | None = None,
    ) -> None:
        """Initialize the event bus.

        Args:
            middlewares: List of middleware functions.
            config: Event bus configuration.
            parallel: Parallel execution protocol for concurrent handler execution.
            tracer: Optional tracer for distributed tracing.
        """
        super().__init__(middlewares)
        self._parallel = parallel
        self._tracer: TracerProtocol | None = tracer
        self._hooks: HookRegistryProtocol | None = hooks

        self._config: EventBusConfig = config or EventBusConfig(
            max_concurrent_handlers=self.DEFAULT_MAX_CONCURRENT_HANDLERS,
            handler_timeout_seconds=self.DEFAULT_HANDLER_TIMEOUT_SECONDS,
            retry_failed_handlers=self.DEFAULT_RETRY_FAILED_HANDLERS,
            max_handler_retries=self.DEFAULT_MAX_HANDLER_RETRIES,
            enable_dead_letter=self.DEFAULT_ENABLE_DEAD_LETTER,
            allow_no_handlers=self.DEFAULT_ALLOW_NO_HANDLERS,
            parallel_dispatch=self.DEFAULT_PARALLEL_DISPATCH,
            continue_on_error=self.DEFAULT_CONTINUE_ON_ERROR,
        )

        self._subscribers: dict[type[Event], list[Any]] = {}
        self._global_handlers: list[Any] = []

        max_concurrent = self._config.max_concurrent_handlers or 10
        self._handler_semaphore: asyncio.Semaphore | None = None
        if max_concurrent > 0:
            self._handler_semaphore = asyncio.Semaphore(max_concurrent)

        self._handler_cache: dict[type[Event], list[Any]] = {}
        self._event_channels: dict[type[Event], ChannelProtocol] = {}
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._in_flight: int = 0
        self._dispatch_errors: list[Exception] = []
        self._closed: bool = False

    @property
    def dispatch_errors(self) -> tuple[Exception, ...]:
        """Return handler failures observed during asynchronous dispatch.

        ``publish()`` reports enqueue acceptance, while handlers run in the
        background drain.  This read-only snapshot lets health checks and
        operator surfaces inspect failures even when ``continue_on_error`` is
        enabled.
        """
        return tuple(self._dispatch_errors)

    def clear_dispatch_errors(self) -> None:
        """Clear the observed dispatch failures after an operator has read them."""
        self._dispatch_errors.clear()

    def subscribe(self, event_type: type[Event], handler: Any) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: The event class to subscribe to.
            handler: Handler to call when event is published.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        self._handler_cache.pop(event_type, None)

    def set_tracer(self, tracer: TracerProtocol | None) -> None:
        """Attach an optional tracer after provider boot wiring.

        Args:
            tracer: Tracer to attach, or None to clear.
        """
        self._tracer = tracer

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry after provider boot wiring."""
        self._hooks = hooks

    @staticmethod
    def _qualified_name(value: object) -> str:
        """Return a fully-qualified name for a type, function, or instance."""
        target = value if hasattr(value, "__qualname__") else type(value)
        module = getattr(target, "__module__", type(value).__module__)
        qualname = getattr(
            target,
            "__qualname__",
            getattr(target, "__name__", type(value).__qualname__),
        )
        return f"{module}.{qualname}"

    async def _emit_action(self, hook_name: str, payload: object) -> None:
        """Emit a bus action hook when a registry is available."""
        if self._hooks is None:
            return

        await self._hooks.call_action(hook_name, payload=payload)

    async def _emit_published_hook(self, event: Event) -> None:
        """Emit the canonical publication hook for an enqueued event."""
        aggregate_id = getattr(event, "aggregate_id", None)
        await self._emit_action(
            "event.published",
            EventPublishedHook(
                event_type=self._qualified_name(type(event)),
                aggregate_id=str(aggregate_id) if aggregate_id is not None else None,
            ),
        )

    async def _emit_event_handled(self, event: Event, handler: object) -> None:
        """Emit the canonical handler completion hook."""
        await self._emit_action(
            "event.handled",
            EventHandledHook(
                event_type=self._qualified_name(type(event)),
                handler=self._qualified_name(handler),
            ),
        )

    def handler(self, event_type: type[Event]) -> Callable[[Callable], Callable]:
        """Decorator to subscribe a handler to an event type."""

        def decorator(func: Callable) -> Callable:
            self.subscribe(event_type, func)
            return func

        return decorator

    def subscribe_all(self, handler: Any) -> None:
        """Subscribe a handler to all events.

        Args:
            handler: Handler to call for every published event.
        """
        self._global_handlers.append(handler)
        self._handler_cache.clear()

    def unsubscribe(self, event_type: type[Event], handler: Any) -> bool:  # type: ignore[override]
        """Unsubscribe a handler from an event type.

        Args:
            event_type: The event class.
            handler: Handler to remove.

        Returns:
            True if handler was found and removed.
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                self._handler_cache.pop(event_type, None)
                return True
            except ValueError:
                pass
        return False

    async def publish(self, event: Event) -> Result[None, EventError]:
        """Publish an event to all subscribers via a bounded channel.

        Enqueues the event into a per-event-type BoundedChannel; a background
        drain task dequeues and dispatches it to all handlers. Blocks when the
        channel is at capacity providing natural backpressure (MAJ-11).

        Args:
            event: The event to publish.

        Returns:
            Ok(None) on successful enqueue. Err(EventHandlerError) when
            no handlers are registered and allow_no_handlers is False.
            Err(EventError) once the bus has been closed: a publish after
            shutdown must not quietly start a new drain task.
        """
        event_type = type(event)
        if self._closed:
            return Err(
                EventError(
                    f"Event bus is closed; {event_type.__name__} was not published",
                    details={"event_type": event_type.__name__},
                )
            )

        span = (
            self._tracer.start_span(
                f"event.publish {event_type.__name__}",
                attributes={
                    "messaging.system": "event_bus",
                    "event.type": event_type.__name__,
                },
            )
            if self._tracer
            else None
        )

        with span if span is not None else _nullcontext():
            handlers = await self._get_handlers_for_event(event_type)

            if not handlers:
                if self._config.allow_no_handlers:
                    return Ok(None)
                return Err(
                    EventHandlerError(
                        event_type=event_type.__name__,
                        handler="",
                        error=f"No handlers registered for event {event_type.__name__}",
                    )
                )

            channel = self._ensure_channel_for(event_type)
            await channel.send(event)
            await self._emit_published_hook(event)
        return Ok(None)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report event-bus readiness and accumulated dispatch failures.

        Publication is intentionally asynchronous, so a successful
        ``publish()`` does not prove that every handler completed.  The
        diagnostics count makes that distinction visible to health consumers.
        """
        _ = timeout
        errors = self.dispatch_errors
        status = HealthStatus.DEGRADED if errors else HealthStatus.HEALTHY
        return HealthCheckResult(
            component=self.__class__.__name__,
            status=status,
            details={
                "subscriber_count": sum(
                    len(handlers) for handlers in self._subscribers.values()
                ),
                "in_flight": self._in_flight,
                "queued_event_types": sum(
                    not channel.is_empty for channel in self._event_channels.values()
                ),
                "dispatch_error_count": len(errors),
                "dispatch_errors": [str(error) for error in errors],
            },
        )

    async def close(self, timeout: float = 30.0) -> None:
        """Drain what was accepted, then stop the background drain tasks.

        ``publish()`` returns as soon as the event is queued, so at shutdown
        the queue may still hold events the caller believes are delivered.
        Closing each channel lets its drain task finish the queued events
        and exit; tasks that are still running after ``timeout`` seconds
        are cancelled. Idempotent: a second call is a no-op.

        Only drain tasks owned by the running loop are waited on; a task
        started on another loop is left to settle there, because its
        completion can never be observed from here.

        Args:
            timeout: Seconds to wait for queued events to be handled before
                the remaining drain tasks are cancelled.
        """
        if self._closed:
            return
        self._closed = True
        for channel in self._event_channels.values():
            await channel.close()
        pending = [task for task in self._background_tasks if not task.done()]
        if not pending:
            return

        loop = asyncio.get_running_loop()
        # A drain task is started lazily by the first ``publish()`` for an event
        # type, so it belongs to whichever loop published — which is not
        # necessarily the loop now closing the bus. ``asyncio.wait`` learns that
        # a task finished through a done-callback, and that callback is
        # scheduled on the *task's* loop, so waiting on a foreign task stays
        # blocked for the whole ``timeout`` however long ago the task finished.
        # During application shutdown that timeout is the caller's entire
        # shutdown budget, so a foreign drain task would fail the shutdown
        # outright. Those tasks are left to settle on their own loop.
        local = [task for task in pending if task.get_loop() is loop]
        foreign = [task for task in pending if task.get_loop() is not loop]
        if foreign:
            logger.warning(
                "event_bus.close_foreign_drain_tasks",
                count=len(foreign),
            )

        if local:
            _, still_running = await asyncio.wait(local, timeout=timeout)
            for task in still_running:
                task.cancel()
            if still_running:
                await asyncio.gather(*still_running, return_exceptions=True)

    async def flush(self) -> None:
        """Wait until all pending events in every channel have been dispatched.

        Yields control repeatedly until every BoundedChannel is empty and all
        in-progress handler dispatches have completed. Useful in tests.
        """
        while (
            any(not ch.is_empty for ch in self._event_channels.values())
            or self._in_flight > 0
        ):
            await asyncio.sleep(0)
        await asyncio.sleep(0)


__all__ = ["EventBusImpl"]
