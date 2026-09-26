"""Simple transaction management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)

if TYPE_CHECKING:
    from quadkit.contracts.data.sql.database import ConnectionPoolProtocol

logger = get_logger(__name__)


class SimpleTransactionManager:
    """Simple transaction manager for application-level use.

    Not to be confused with ``providers.transaction_manager.TransactionManager``
    which is the internal provider-level transaction handler.
    """

    def __init__(self, connection_pool: ConnectionPoolProtocol) -> None:
        self.connection_pool: ConnectionPoolProtocol = connection_pool
        # Per-instance ContextVar — eliminates the module-level global.
        self._transaction_var: ContextVar[Any] = ContextVar("db_txn", default=None)

    def get_current_connection(self) -> Any:
        """Get the active transaction connection for the current async task."""
        return self._transaction_var.get()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any, None]:
        """Context manager for database transactions."""
        # Check if we're already in a transaction
        existing_conn = self.get_current_connection()
        if existing_conn:
            # Nested transaction - just yield existing connection
            yield existing_conn
            return

        # Start a new transaction
        async with self.connection_pool.get_connection() as conn:
            token = self._transaction_var.set(conn)

            try:
                await conn.execute("BEGIN")
                yield conn
                await conn.execute("COMMIT")
            except (
                DatabaseError,
                QueryError,
                DatabaseConnectionError,
                DatabaseTimeoutError,
            ):
                logger.exception("Transaction failed")
                # Attempt rollback and log if rollback itself fails
                try:
                    await conn.execute("ROLLBACK")
                except Exception as rollback_exc:  # noqa: BLE001 — a rollback failure must not mask the original transaction error
                    with suppress(ImportError, AttributeError, RuntimeError):
                        logger.debug(
                            "Rollback failed during transaction: %s",
                            rollback_exc,
                            exc_info=True,
                        )
                raise
            finally:
                self._transaction_var.reset(token)


@asynccontextmanager
async def transaction(manager: SimpleTransactionManager) -> AsyncGenerator[None, None]:
    """Transaction context manager.

    Args:
        manager: SimpleTransactionManager instance from DI container.
    """
    async with manager.transaction():
        yield
