"""In-memory CQRS command and query bus implementations for testing.

Provides minimal in-memory CQRS dispatch for unit tests and local development.
For production use with middleware pipelines, metrics, and transaction support,
use the ``quadkit-events`` extension.

Example::

    from quadkit.testing import InMemoryCommandBus, InMemoryQueryBus

    # Command bus
    cmd_bus = InMemoryCommandBus()
    cmd_bus.register(CreateOrder, CreateOrderHandler())
    result = await cmd_bus.dispatch(CreateOrder(item="widget"))

    # Query bus
    query_bus = InMemoryQueryBus()
    query_bus.register(GetOrderById, GetOrderByIdHandler())
    order = await query_bus.execute(GetOrderById(order_id="123"))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.events import CommandBusProtocol as CommandBusProtocol
from quadkit.contracts.events import QueryBusProtocol as QueryBusProtocol
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result
from quadkit.testing.memory.exceptions import (
    CommandBusError,
    CommandError,
    CommandHandlerNotFoundError,
    DuplicateHandlerError,
    QueryBusError,
    QueryDuplicateHandlerError,
    QueryHandlerNotFoundError,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core import MiddlewarePipelineProtocol
    from quadkit.contracts.events import CommandHandlerProtocol, QueryHandlerProtocol

logger = get_logger(__name__)


# =============================================================================
# Command Bus
# =============================================================================


class InMemoryCommandBus(CommandBusProtocol):
    """Lightweight in-memory command bus implementing the CommandBusProtocol protocol.

    Each command type maps to exactly one handler (enforced). Dispatching
    resolves the handler and invokes ``handler.handle(command)`` or calls
    the handler directly if it is a plain callable.

    When ``on_handler_error`` is provided, handler exceptions are caught
    and reported via the callback instead of propagating.

    Usage::

        bus = InMemoryCommandBus()

        class CreateOrderHandler:
            async def handle(self, command: CreateOrder) -> str:
                return f"order-{command.item}"

        bus.register(CreateOrder, CreateOrderHandler())
        result = await bus.dispatch(CreateOrder(item="widget"))

    Args:
        on_handler_error: Optional callback receiving
            ``(command, handler, exception)`` when a handler raises.
    """

    def __init__(
        self,
        *,
        on_handler_error: Callable[[Any, Any, Exception], None] | None = None,
    ) -> None:
        self._handlers: dict[type, Any] = {}
        from quadkit.app.pipeline import (
            MiddlewarePipeline as _MiddlewarePipeline,
        )

        self._pipeline: MiddlewarePipelineProtocol = _MiddlewarePipeline()
        self._on_handler_error = on_handler_error

    @property
    def handler_count(self) -> int:
        """Return the number of registered handlers.

        Returns:
            The count of currently registered handlers.
        """
        return len(self._handlers)

    def register(
        self, command_type: type, handler: CommandHandlerProtocol | Any
    ) -> None:
        """Register a handler for a command type (one handler per type).

        Args:
            command_type: The command class this handler processes.
            handler: A callable or object with an async ``handle`` method.

        Raises:
            DuplicateHandlerError: If a handler is already registered for
                this command type.
        """
        if command_type in self._handlers:
            raise DuplicateHandlerError(command_type.__name__)
        self._handlers[command_type] = handler
        logger.debug(
            "command_bus.handler_registered",
            command=command_type.__name__,
        )

    def unregister(self, command_type: type) -> None:
        """Remove the handler registered for a command type.

        Args:
            command_type: The command class to unregister.

        Raises:
            HandlerNotFoundError: If no handler is registered.
        """
        if command_type not in self._handlers:
            raise CommandHandlerNotFoundError(command_type.__name__)
        del self._handlers[command_type]

    def has_handler(self, command_type: type) -> bool:
        """Check whether a handler is registered for the given command type.

        Args:
            command_type: The command class to check.

        Returns:
            True if a handler is registered.
        """
        return command_type in self._handlers

    def add_middleware(self, middleware: Callable[..., Any]) -> None:
        """Add a middleware to the command dispatch pipeline.

        Middleware wraps dispatch and is executed in the order added. Each
        middleware receives ``(command, next_handler)`` and must call
        ``await next_handler(command)`` to continue the chain.

        Args:
            middleware: An async callable with signature
                ``(command, next) -> result``.
        """
        self._pipeline = self._pipeline.add(middleware)

    async def dispatch(self, command: Any) -> Any:
        """Dispatch a command to its registered handler through the middleware chain.

        Args:
            command: The command object to dispatch.

        Returns:
            The result returned by the handler.

        Raises:
            HandlerNotFoundError: If no handler is registered for the
                command's type.
        """
        command_type = type(command)
        handler = self._handlers.get(command_type)
        if handler is None:
            raise CommandHandlerNotFoundError(command_type.__name__)

        return await self._pipeline.execute(
            command, lambda x: self._invoke_handler(x, handler)
        )

    async def dispatch_result(self, command: Any) -> Result[Any, CommandBusError]:
        """Dispatch a command and wrap the outcome in a Result.

        Returns ``Ok(value)`` on success. On ``CommandBusError`` (e.g. no
        registered handler), returns ``Err(error)`` directly.  Any other
        exception raised by the handler is wrapped in ``CommandError`` so
        callers receive a typed ``Err`` without catching bare ``Exception``.

        Infrastructure exceptions that are not handler failures should be
        inspected via ``result.unwrap_err().cause`` when applicable.

        Args:
            command: The command object to dispatch.

        Returns:
            ``Ok(result)`` on success, ``Err(CommandBusError)`` on failure.
        """
        try:
            result = await self.dispatch(command)
            return Ok(result)
        except CommandBusError as exc:
            return Err(exc)
        except Exception as exc:  # noqa: BLE001 — the wrapper's contract is Ok-or-Err; any handler failure becomes Err
            return Err(CommandError(exc))

    async def _invoke_handler(self, command: Any, handler: Any) -> Any:
        """Invoke the handler directly, with error callback support.

        Args:
            command: The command to handle.
            handler: The registered handler.

        Returns:
            The handler result.
        """
        try:
            if callable(handler) and not hasattr(handler, "handle"):
                return await handler(command)
            return await handler.handle(command)
        except Exception as exc:
            if self._on_handler_error is not None:
                self._on_handler_error(command, handler, exc)
                return None
            raise


# =============================================================================
# Query Bus
# =============================================================================


class InMemoryQueryBus(QueryBusProtocol):
    """Lightweight in-memory query bus implementing the QueryBusProtocol protocol.

    Each query type maps to exactly one handler (enforced). Executing a
    query resolves the handler and invokes ``handler.handle(query)`` or
    calls the handler directly if it is a plain callable.

    When ``on_handler_error`` is provided, handler exceptions are caught
    and reported via the callback instead of propagating.

    Usage::

        bus = InMemoryQueryBus()

        class GetOrderHandler:
            async def handle(self, query: GetOrderById) -> Order:
                return Order(id=query.order_id)

        bus.register(GetOrderById, GetOrderHandler())
        order = await bus.execute(GetOrderById(order_id="123"))

    Args:
        on_handler_error: Optional callback receiving
            ``(query, handler, exception)`` when a handler raises.
    """

    def __init__(
        self,
        *,
        on_handler_error: Callable[[Any, Any, Exception], None] | None = None,
    ) -> None:
        self._handlers: dict[type, Any] = {}
        from quadkit.app.pipeline import (
            MiddlewarePipeline as _MiddlewarePipeline,
        )

        self._pipeline: MiddlewarePipelineProtocol = _MiddlewarePipeline()
        self._on_handler_error = on_handler_error

    @property
    def handler_count(self) -> int:
        """Return the number of registered handlers.

        Returns:
            The count of currently registered handlers.
        """
        return len(self._handlers)

    def register(self, query_type: type, handler: QueryHandlerProtocol | Any) -> None:
        """Register a handler for a query type (one handler per type).

        Args:
            query_type: The query class this handler processes.
            handler: A callable or object with an async ``handle`` method.

        Raises:
            QueryDuplicateHandlerError: If a handler is already registered for
                this query type.
        """
        if query_type in self._handlers:
            raise QueryDuplicateHandlerError(query_type.__name__)
        self._handlers[query_type] = handler
        logger.debug(
            "query_bus.handler_registered",
            query=query_type.__name__,
        )

    def unregister(self, query_type: type) -> None:
        """Remove the handler registered for a query type.

        Args:
            query_type: The query class to unregister.

        Raises:
            QueryHandlerNotFoundError: If no handler is registered.
        """
        if query_type not in self._handlers:
            raise QueryHandlerNotFoundError(query_type.__name__)
        del self._handlers[query_type]

    def has_handler(self, query_type: type) -> bool:
        """Check whether a handler is registered for the given query type.

        Args:
            query_type: The query class to check.

        Returns:
            True if a handler is registered.
        """
        return query_type in self._handlers

    def add_middleware(self, middleware: Callable[..., Any]) -> None:
        """Add a middleware to the query execution pipeline.

        Middleware wraps execution and is invoked in the order added. Each
        middleware receives ``(query, next_handler)`` and must call
        ``await next_handler(query)`` to continue the chain.

        Args:
            middleware: An async callable with signature
                ``(query, next) -> result``.
        """
        self._pipeline = self._pipeline.add(middleware)

    async def execute(self, query: Any) -> Any:
        """Execute a query through its registered handler and middleware chain.

        Args:
            query: The query object to execute.

        Returns:
            The result returned by the handler.

        Raises:
            QueryHandlerNotFoundError: If no handler is registered for the
                query's type.
        """
        query_type = type(query)
        handler = self._handlers.get(query_type)
        if handler is None:
            raise QueryHandlerNotFoundError(query_type.__name__)

        return await self._pipeline.execute(
            query, lambda x: self._invoke_handler(x, handler)
        )

    async def execute_result(self, query: Any) -> Result[Any, Exception]:
        """Execute a query and wrap the outcome in a Result.

        Returns ``Ok(value)`` on success or ``Err(exception)`` on failure.
        The ``on_handler_error`` callback is **not** invoked — the caller
        is expected to inspect the Result directly.

        Args:
            query: The query object to execute.

        Returns:
            ``Ok(result)`` on success, ``Err(exception)`` on failure.
            The error is the exact exception raised by the handler, preserving
            the original type for downstream ``isinstance`` checks.
        """
        try:
            result = await self.execute(query)
            return Ok(result)
        except Exception as exc:  # noqa: BLE001 — the wrapper's contract is Ok-or-Err; the handler's exception type is preserved in Err
            return Err(exc)

    async def _invoke_handler(self, query: Any, handler: Any) -> Any:
        """Invoke the handler directly, with error callback support.

        Args:
            query: The query to handle.
            handler: The registered handler.

        Returns:
            The handler result.
        """
        try:
            if callable(handler) and not hasattr(handler, "handle"):
                return await handler(query)
            return await handler.handle(query)
        except Exception as exc:
            if self._on_handler_error is not None:
                self._on_handler_error(query, handler, exc)
                return None
            raise


__all__ = [
    "CommandBusError",
    "CommandHandlerNotFoundError",
    "DuplicateHandlerError",
    "InMemoryCommandBus",
    "InMemoryQueryBus",
    "QueryBusError",
    "QueryDuplicateHandlerError",
    "QueryHandlerNotFoundError",
]
