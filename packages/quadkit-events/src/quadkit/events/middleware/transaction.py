"""Transaction middleware for CQRS buses.

Provides transaction management for command handlers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import contextlib
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from quadkit.events.messages.base import Message
from quadkit.events.middleware.base import AbstractMiddleware, NextHandler
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class TransactionContext(ABC):
    """Abstract transaction context.

    Implement this for your specific database/transaction system.
    """

    @abstractmethod
    async def begin(self) -> None:
        """Begin a transaction."""
        ...

    @abstractmethod
    async def commit(self) -> None:
        """Commit the transaction."""
        ...

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the transaction."""
        ...


class TransactionMiddleware(AbstractMiddleware[Message, Any]):
    """AbstractMiddleware that wraps handlers in transactions.

    Provides automatic transaction management:
    - Begins transaction before handler
    - Commits on success
    - Rollbacks on error

    Example:
        ```python
        # With a transaction context factory
        class SQLAlchemyTransactionContext(TransactionContext):
            def __init__(self, session):
                self.session = session

            async def begin(self):
                pass  # SQLAlchemy auto-begins

            async def commit(self):
                await self.session.commit()

            async def rollback(self):
                await self.session.rollback()

        transaction_middleware = TransactionMiddleware(
            context_factory=lambda: SQLAlchemyTransactionContext(session)
        )
        command_bus.use(transaction_middleware)
        ```
    """

    def __init__(
        self,
        context_factory: Callable[[], TransactionContext] | None = None,
        propagation: str = "required",
    ):
        """Initialize the transaction middleware.

        Args:
            context_factory: Factory function to create transaction context
            propagation: Transaction propagation behavior:
                - "required": Use existing or create new (default)
                - "requires_new": Always create new
                - "supports": Use existing if available
        """
        self._context_factory = context_factory
        self._propagation = propagation
        self._current_context: TransactionContext | None = None

    @asynccontextmanager
    async def transaction(self) -> Any:
        """Create a transaction context manager.

        Example:
            ```python
            async with transaction_middleware.transaction():
                # Execute commands
                # Note: dispatch() is the standard method for CommandBusProtocol
                await command_bus.dispatch(command1)
                await command_bus.dispatch(command2)
                # Both commands in same transaction
            ```
        """
        if not self._context_factory:
            yield
            return

        context = self._context_factory()
        await context.begin()

        try:
            self._current_context = context
            yield context
            await context.commit()
        except (RuntimeError, ValueError, TypeError, AttributeError):
            with contextlib.suppress(OSError, ValueError, TypeError):
                logger.exception("Transaction failed, rolling back")
            await context.rollback()
            raise
        finally:
            self._current_context = None

    async def __call__(self, message: Message, next_handler: NextHandler) -> Any:
        """Execute with transaction management."""
        # If no context factory, just pass through
        if not self._context_factory:
            return await next_handler(message)

        # Handle propagation
        if self._propagation == "supports":
            # Use existing transaction if available, otherwise no transaction
            if self._current_context:
                return await next_handler(message)
            return await next_handler(message)

        if self._propagation == "required" and self._current_context:
            # Reuse existing transaction
            return await next_handler(message)

        # Create new transaction (required or requires_new)
        async with self.transaction():
            return await next_handler(message)


class UnitOfWorkMiddleware(AbstractMiddleware[Message, Any]):
    """AbstractMiddleware that implements Unit of Work pattern.

    Collects all changes during handler execution and commits them atomically.

    Example:
        ```python
        class UnitOfWork:
            def __init__(self):
                self._operations = []

            def register(self, operation):
                self._operations.append(operation)

            async def commit(self):
                for op in self._operations:
                    await op()
                self._operations.clear()

        uow_middleware = UnitOfWorkMiddleware(
            uow_factory=UnitOfWork
        )
        ```
    """

    def __init__(self, uow_factory: Callable[[], Any]):
        """Initialize the Unit of Work middleware.

        Args:
            uow_factory: Factory to create UoW instances
        """
        self._uow_factory = uow_factory

    async def __call__(self, message: Message, next_handler: NextHandler) -> Any:
        """Execute with Unit of Work."""
        uow = self._uow_factory()

        # Store UoW in message metadata for handlers to access
        if hasattr(message, "metadata") and message.metadata is not None:
            # Store UoW inside the metadata.custom dict.
            # This avoids mutating the model's own attributes.
            message.metadata.custom["_unit_of_work"] = uow

        try:
            result = await next_handler(message)
            await uow.commit()
            return result
        except (RuntimeError, ValueError, TypeError, AttributeError):
            with contextlib.suppress(OSError, ValueError, TypeError):
                logger.exception("UnitOfWork failed, rolling back")
            if hasattr(uow, "rollback"):
                await uow.rollback()
            raise


__all__ = [
    "TransactionContext",
    "TransactionMiddleware",
    "UnitOfWorkMiddleware",
]
