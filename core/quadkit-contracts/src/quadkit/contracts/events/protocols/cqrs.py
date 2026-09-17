"""CQRS command and query protocols."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CommandHandlerProtocol(Protocol):
    """Protocol for command handlers."""

    async def handle(self, command: Any) -> Any:
        """Handle a command.

        Args:
            command: Command to handle.

        Returns:
            Command result.
        """
        ...


@runtime_checkable
class CommandBusProtocol(Protocol):
    """Protocol for command bus implementations.

    Example:
        ```python
        class CommandBusProtocol:
            async def dispatch(self, command: Command) -> Any:
                handler = self._handlers[type(command)]
                return await handler.handle(command)
        ```
    """

    async def dispatch(self, command: Any) -> Any:
        """Dispatch a command to its handler.

        Args:
            command: Command to dispatch.

        Returns:
            Result from the command handler.
        """
        ...


@runtime_checkable
class QueryHandlerProtocol(Protocol):
    """Protocol for query handlers."""

    async def handle(self, query: Any) -> Any:
        """Handle a query.

        Args:
            query: Query to handle.

        Returns:
            Query result.
        """
        ...


@runtime_checkable
class QueryBusProtocol(Protocol):
    """Protocol for query bus implementations.

    Example:
        ```python
        class QueryBusProtocol:
            async def execute(self, query: Query) -> Any:
                handler = self._handlers[type(query)]
                return await handler.handle(query)
        ```
    """

    async def execute(self, query: Any) -> Any:
        """Execute a query through its handler.

        Args:
            query: Query to execute.

        Returns:
            Query result.
        """
        ...
