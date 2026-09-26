"""Handler dispatch mixin for the event bus.

Extracted from ``quadkit.events.buses.event`` to keep ``EventBusImpl``
under the 700-line limit.  All dispatch state lives on the concrete
``EventBusImpl`` class; this mixin only contains the dispatch logic so
that the split is purely structural (no behaviour change).
"""

from __future__ import annotations

import asyncio
from contextlib import nullcontext as _nullcontext
from typing import TYPE_CHECKING, Any

from quadkit.concurrency import BoundedChannel
from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.events.exceptions import EventHandlerError
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core import ChannelProtocol
    from quadkit.events.config import EventBusConfig
    from quadkit.events.messages.event import Event

logger = get_logger(__name__)

__all__ = ["HandlerDispatchMixin"]


class HandlerDispatchMixin:
    """Mixin providing handler registration lookup and event dispatch logic.

    Concrete classes must expose the instance attributes read by these methods
    (``_subscribers``, ``_global_handlers``, ``_handler_cache``, ``_config``,
    ``_handler_semaphore``, ``_parallel``, ``_event_channels``,
    ``_background_tasks``, ``_in_flight``, ``_dispatch_errors``).
    """

    # -- Typed stubs so type checkers understand what we read from `self` -- #
    if TYPE_CHECKING:
        _subscribers: dict[type[Event], list[Any]]
        _global_handlers: list[Any]
        _handler_cache: dict[type[Event], list[Any]]
        _config: EventBusConfig
        _handler_semaphore: asyncio.Semaphore | None
        _parallel: Any | None
        _event_channels: dict[type[Event], ChannelProtocol]
        _background_tasks: set[asyncio.Task[None]]
        _in_flight: int
        _tracer: Any | None
        _dispatch_errors: list[Exception]

        async def _emit_event_handled(self, event: Event, handler: Any) -> None: ...
        async def _execute_pipeline(self, event: Event, handler: Any) -> None: ...

    def _ensure_channel_for(self, event_type: type[Event]) -> ChannelProtocol:
        """Return (or lazily create) the bounded channel for *event_type*.

        On first call for a given event type a :class:`BoundedChannel` of
        capacity ``config.max_queue_per_subscriber`` is created and a
        background drain task is started to process events from the channel.

        Args:
            event_type: The event class to get or create a channel for.

        Returns:
            The ``BoundedChannel`` for the event type.
        """
        if event_type not in self._event_channels:
            capacity = self._config.max_queue_per_subscriber
            channel: ChannelProtocol = BoundedChannel(capacity=capacity)  # type: ignore[assignment]
            self._event_channels[event_type] = channel
            create_tracked_task(
                self._drain_channel(event_type, channel),
                self._background_tasks,
                name=f"event_handler_{type(event_type).__name__}_{id(event_type)}",
            )
        return self._event_channels[event_type]

    async def _drain_channel(
        self,
        event_type: type[Event],
        channel: ChannelProtocol,
    ) -> None:
        """Background task that drains *channel* and dispatches each event.

        Runs until the channel is closed (e.g. on bus shutdown). Errors from
        individual handler dispatches are logged and stored in
        :attr:`_dispatch_errors` but do not terminate the drain loop so that
        subsequent events continue to be processed.

        Args:
            event_type: The event class this channel serves (used for logging).
            channel: The bounded channel to drain.
        """
        try:
            async with channel.receiver() as receiver:  # type: ignore[attr-defined]
                async for event in receiver:
                    self._in_flight += 1
                    try:
                        await self._dispatch_to_handlers(event)
                    except asyncio.CancelledError:
                        # The finally block owns the in-flight decrement; doing
                        # it here as well makes cancellation drive the counter
                        # negative and can let flush() return too early.
                        raise
                    except Exception as exc:  # noqa: BLE001 — drain-loop handler isolation; one bad event must not stop others
                        logger.exception(
                            "event_drain.dispatch_error",
                            event_type=event_type.__name__,
                        )
                        # HandlerDispatchMixin records settled handler errors
                        # before raising for stop-on-error.  Avoid recording
                        # that same exception a second time here, while still
                        # retaining unexpected drain-level failures.
                        if not any(
                            recorded is exc for recorded in self._dispatch_errors
                        ):
                            self._dispatch_errors.append(exc)
                    finally:
                        self._in_flight -= 1
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — task-level failures are logged; a foreign type must not silently kill the drain task
            logger.exception(
                "event_drain.task_error",
                event_type=event_type.__name__,
            )

    async def _dispatch_to_handlers(self, event: Event) -> None:
        """Dispatch *event* to all registered handlers.

        Implements both parallel and sequential dispatch modes, honouring
        ``max_concurrent_handlers``, ``continue_on_error``, and retry
        configuration from :attr:`_config`.

        Args:
            event: The event to dispatch.
        """
        event_type = type(event)
        handlers = await self._get_handlers_for_event(event_type)

        if not handlers:
            return

        errors: list[tuple[type, Exception]] = []

        if self._config.parallel_dispatch:
            from quadkit.concurrency import Parallel
            from quadkit.contracts.core import ExecutionStrategy

            async def _wrap_handler(_handler: Any) -> tuple[Any, Any]:
                try:
                    if self._handler_semaphore:
                        async with self._handler_semaphore:
                            await self._execute_handler(event, _handler)
                    else:
                        await self._execute_handler(event, _handler)
                    return (_handler, None)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001 — handler can raise anything
                    return (_handler, e)

            tasks = [_wrap_handler(h) for h in handlers]

            if self._parallel is not None:
                results = await self._parallel.execute(
                    *tasks,
                    strategy=ExecutionStrategy.ALL_SETTLED,
                )
            else:
                results = await Parallel.execute(
                    *tasks,
                    strategy=ExecutionStrategy.ALL_SETTLED,
                )

            for handler, result in results:
                if result is not None:
                    logger.warning(
                        "event_handler.failed",
                        event_type=type(event).__name__,
                        handler=type(handler).__name__,
                        error=str(result),
                    )
                    errors.append((type(result), result))
        else:
            for handler in handlers:
                try:
                    if self._handler_semaphore:
                        async with self._handler_semaphore:
                            await self._execute_handler(event, handler)
                    else:
                        await self._execute_handler(event, handler)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001 — handler can raise anything
                    logger.warning(
                        "event_handler.failed",
                        event_type=type(event).__name__,
                        handler=type(handler).__name__,
                        error=str(e),
                    )
                    errors.append((type(e), e))
                    if not self._config.continue_on_error:
                        break

        # Every settled handler failure needs to be observable.  The previous
        # implementation discarded failures when continuing dispatch and only
        # retained the first failure when parallel stop-on-error dispatch
        # raised.  Record all handler errors before applying the configured
        # propagation policy; the drain loop de-duplicates the raised error.
        if errors:
            self._dispatch_errors.extend(error for _, error in errors)

        if errors and not self._config.continue_on_error:
            raise errors[0][1]

    async def _get_handlers_for_event(self, event_type: type[Event]) -> list[Any]:
        """Get all handlers for an event type (type-specific + global + inherited).

        Uses a per-bus cache; invalidated on subscribe/unsubscribe.

        Args:
            event_type: The event class.

        Returns:
            List of handlers in registration order.
        """
        if event_type in self._handler_cache:
            return self._handler_cache[event_type]

        handlers: list[Any] = []
        handlers.extend(self._global_handlers)

        for registered_type, type_handlers in self._subscribers.items():
            if issubclass(event_type, registered_type):
                handlers.extend(type_handlers)

        self._handler_cache[event_type] = handlers
        return handlers

    async def _execute_handler(self, event: Event, handler: Any) -> None:
        """Execute a single handler with optional retry support.

        Args:
            event: The event.
            handler: The handler callable.

        Raises:
            asyncio.TimeoutError: If handler execution exceeds the configured timeout.
            EventHandlerError: If handler fails after all retry attempts.
        """
        max_retries = (
            getattr(self._config, "max_handler_retries", 0)
            if self._config.retry_failed_handlers
            else 0
        )
        if max_retries is None:
            max_retries = 0
        retry_delay = getattr(self._config, "retry_delay_seconds", 0.1) or 0.1

        span = (
            self._tracer.start_span(  # type: ignore[union-attr]
                f"event.handle {type(event).__name__}",
                attributes={"event.type": type(event).__name__},
            )
            if getattr(self, "_tracer", None)
            else None
        )

        try:
            with span if span is not None else _nullcontext():
                for attempt in range(max_retries + 1):
                    try:
                        timeout = self._config.handler_timeout_seconds
                        if timeout and timeout > 0:
                            try:
                                await asyncio.wait_for(
                                    self._execute_pipeline(event, handler),
                                    timeout=timeout,
                                )
                            except TimeoutError:
                                handler_name = getattr(
                                    handler, "__name__", str(handler)
                                )
                                raise EventHandlerError(
                                    event_type=type(event).__name__,
                                    handler=handler_name,
                                    error=f"timed out after {timeout}s",
                                ) from None
                        else:
                            await self._execute_pipeline(event, handler)
                        await self._emit_event_handled(event, handler)
                        return
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:  # noqa: BLE001 — retry logic; catches any handler failure to decide whether to retry
                        if attempt < max_retries:
                            logger.info(
                                "Handler %s failed (attempt %d/%d), retrying in %.1fs: %s",
                                getattr(handler, "__name__", str(handler)),
                                attempt + 1,
                                max_retries + 1,
                                retry_delay,
                                e,
                            )
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                        else:
                            handler_name = getattr(handler, "__name__", str(handler))
                            raise EventHandlerError(
                                event_type=type(event).__name__,
                                handler=handler_name,
                                error=str(e),
                                cause=e,
                            ) from e
        except Exception as exc:  # noqa: BLE001 — observability catch; records span status then re-raises
            if span:
                span.record_exception(exc)
                span.set_status("error")
            raise
