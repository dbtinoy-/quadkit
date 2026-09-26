"""Base handler classes for CQRS pattern.

Provides abstract base classes for command, query, and event handlers
with proper typing support.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from quadkit.contracts.exceptions.events import EventError
    from quadkit.events.messages.command import Command
    from quadkit.events.messages.event import Event
    from quadkit.events.messages.query import Query
    from quadkit.result import Result

TCommand = TypeVar("TCommand", bound="Command")
TQuery = TypeVar("TQuery", bound="Query")
TEvent = TypeVar("TEvent", bound="Event")
TResult = TypeVar("TResult")


class CommandHandlerProtocol(ABC, Generic[TCommand, TResult]):
    """Base class for command handlers.

    Command handlers process commands and optionally return results.
    Each command type should have exactly one handler.

    Example:
        ```python
        class CreateOrderHandler(CommandHandlerProtocol[CreateOrderCommand, OrderId]):
            def __init__(self, repository: OrderRepository):
                self.repository = repository

            async def handle(self, command: CreateOrderCommand) -> OrderId:
                order = Order.create(
                    customer_id=command.customer_id,
                    items=command.items
                )
                await self.repository.save(order)
                return order.id
        ```
    """

    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        """Handle a command.

        Args:
            command: The command to handle

        Returns:
            Command execution result
        """
        ...


class QueryHandlerProtocol(ABC, Generic[TQuery, TResult]):
    """Base class for query handlers.

    Query handlers process queries and return results.
    Each query type should have exactly one handler.
    Queries should not modify state.

    Example:
        ```python
        class GetOrdersHandler(QueryHandlerProtocol[GetOrdersQuery, list[OrderDTO]]):
            def __init__(self, read_model: OrderReadModel):
                self.read_model = read_model

            async def handle(self, query: GetOrdersQuery) -> list[OrderDTO]:
                return await self.read_model.get_orders(
                    customer_id=query.customer_id,
                    status=query.status
                )
        ```
    """

    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        """Handle a query.

        Args:
            query: The query to handle

        Returns:
            Query result
        """
        ...


class EventHandlerProtocol(ABC, Generic[TEvent]):
    """Base class for event handlers.

    Event handlers process events and perform side effects.
    Unlike command handlers, multiple handlers can subscribe to
    the same event type.

    Example:
        ```python
        class SendOrderConfirmationHandler(EventHandlerProtocol[OrderCreatedEvent]):
            def __init__(self, email_service: EmailService):
                self.email_service = email_service

            async def handle(self, event: OrderCreatedEvent) -> None:
                await self.email_service.send_confirmation(
                    order_id=event.order_id,
                    customer_email=event.customer_email
                )
        ```
    """

    @abstractmethod
    async def handle(self, event: TEvent) -> Result[None, EventError]:
        """Handle an event.

        Args:
            event: The event to handle.

        Returns:
            ``Ok(None)`` on success, ``Err(EventError)`` if handling fails
            in an expected, recoverable way.
        """
        ...


class MultiEventHandlerProtocol(ABC):
    """Handler that can process multiple event types.

    Useful for handlers that react to related events.

    Example:
        ```python
        class InventoryHandler(MultiEventHandlerProtocol):
            def handles(self) -> list[type]:
                return [ItemAddedEvent, ItemRemovedEvent]

            async def handle(self, event: Event) -> None:
                if isinstance(event, ItemAddedEvent):
                    await self._add_item(event)
                elif isinstance(event, ItemRemovedEvent):
                    await self._remove_item(event)
        ```
    """

    @abstractmethod
    def handles(self) -> list[type]:
        """Return list of event types this handler processes."""
        ...

    @abstractmethod
    async def handle(self, event: Any) -> Result[None, EventError]:
        """Handle an event.

        Returns:
            ``Ok(None)`` on success, ``Err(EventError)`` if handling fails
            in an expected, recoverable way.
        """
        ...


__all__ = [
    "CommandHandlerProtocol",
    "EventHandlerProtocol",
    "MultiEventHandlerProtocol",
    "QueryHandlerProtocol",
]
