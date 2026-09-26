"""
Transaction management for database providers.

Handles database transactions including context managers and manual control.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
import contextvars
from typing import TYPE_CHECKING, Any
import uuid

from quadkit.contracts.core import HookRegistryProtocol
from quadkit.contracts.data.identifiers import validate_identifier

if TYPE_CHECKING:
    from quadkit.contracts.core.identity import IdGeneratorProtocol
from quadkit.contracts.data.sql.database import IsolationLevel
from quadkit.logging import get_logger
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)
from quadkit.sql.hooks import SQLTransactionBegunHook, SQLTransactionEndedHook

logger = get_logger(__name__)


class TransactionManager(ABC):
    """
    Manages database transactions.

    This class handles both automatic transaction context management
    and manual transaction control.
    """

    def __init__(
        self,
        connection_manager: Any,
        id_generator: IdGeneratorProtocol | None = None,
    ) -> None:
        self.connection_manager = connection_manager
        self._id_generator = id_generator
        self._hooks: HookRegistryProtocol | None = None
        self._in_transaction_var: contextvars.ContextVar[bool] = contextvars.ContextVar(
            "transaction_in_transaction", default=False
        )
        self._transaction_connection_var: contextvars.ContextVar[Any | None] = (
            contextvars.ContextVar("transaction_connection", default=None)
        )

    @property
    def in_transaction(self) -> bool:
        """Check if currently in a transaction"""
        return self._in_transaction_var.get()

    @property
    def _transaction_connection(self) -> Any | None:
        """Compatibility accessor for the current transaction connection."""
        return self._transaction_connection_var.get()

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry for transaction lifecycle events."""
        self._hooks = hooks

    async def _emit_transaction_begin(self) -> None:
        """Emit the canonical transaction begin hook when configured."""
        if self._hooks is None:
            return

        await self._hooks.call_action(
            "transaction.begin",
            payload=SQLTransactionBegunHook(),
        )

    async def _emit_transaction_end(self, *, committed: bool) -> None:
        """Emit the canonical transaction end hook when configured."""
        if self._hooks is None:
            return

        await self._hooks.call_action(
            "transaction.end",
            payload=SQLTransactionEndedHook(committed=committed),
        )

    @abstractmethod
    async def _begin_transaction_raw(
        self, connection: Any, isolation: IsolationLevel | None = None
    ) -> None:
        """Begin transaction (implementation-specific).

        Args:
            connection: Active database connection.
            isolation: Optional isolation level to apply.
        """

    @abstractmethod
    async def _commit_transaction_raw(self, connection: Any) -> None:
        """Commit transaction (implementation-specific)"""

    @abstractmethod
    async def _rollback_transaction_raw(self, connection: Any) -> None:
        """Rollback transaction (implementation-specific)"""

    async def _create_savepoint_raw(self, connection: Any, name: str) -> None:
        """Create a named savepoint (implementation-specific, default SQL syntax).

        Override in driver subclasses if the driver requires a different call.

        Args:
            connection: Active database connection.
            name: Savepoint name.
        """
        await connection.execute(f"SAVEPOINT {name}")

    async def _release_savepoint_raw(self, connection: Any, name: str) -> None:
        """Release (commit) a savepoint.

        Args:
            connection: Active database connection.
            name: Savepoint name.
        """
        await connection.execute(f"RELEASE SAVEPOINT {name}")

    async def _rollback_to_savepoint_raw(self, connection: Any, name: str) -> None:
        """Roll back to a savepoint without undoing the outer transaction.

        Args:
            connection: Active database connection.
            name: Savepoint name.
        """
        await connection.execute(f"ROLLBACK TO SAVEPOINT {name}")

    @asynccontextmanager
    async def transaction(self, isolation: IsolationLevel | None = None) -> Any:
        """Context manager for transactions.

        Args:
            isolation: Optional isolation level. When ``None`` the driver's
                default is used.
        """
        is_nested = self._in_transaction_var.get()
        if is_nested:
            # Already in a transaction — reuse existing connection, just yield
            yield
            return

        async with self.connection_manager.get_connection() as conn:
            self._transaction_connection_var.set(conn)
            self._in_transaction_var.set(True)

            try:
                await self._begin_transaction_raw(conn, isolation)
                await self._emit_transaction_begin()
                yield
                await self._commit_transaction_raw(conn)
                await self._emit_transaction_end(committed=True)
            except (
                DatabaseError,
                QueryError,
                DatabaseConnectionError,
                DatabaseTimeoutError,
                OSError,
                ConnectionError,
                RuntimeError,
                TimeoutError,
            ):
                # Attempt rollback and log if rollback fails
                try:
                    await self._rollback_transaction_raw(conn)
                    await self._emit_transaction_end(committed=False)
                except Exception:  # noqa: BLE001 — a rollback failure must not mask the original transaction error
                    logger.exception(
                        "Rollback failed in DatabaseDriver.transaction",
                    )
                raise
            finally:
                self._transaction_connection_var.set(None)
                self._in_transaction_var.set(False)

    @asynccontextmanager
    async def savepoint(self, name: str | None = None) -> Any:
        """Context manager for a savepoint (nested transaction).

        A savepoint can only be used inside an active transaction.  If no
        outer transaction is running, a new transaction is started
        automatically.

        Example::

            async with manager.transaction():
                await repo.insert(order)
                async with manager.savepoint():
                    # This block may fail independently without rolling
                    # back the outer transaction.
                    await repo.insert(order_item)

        Args:
            name: Optional savepoint name.  A random UUID-based name is
                generated when omitted.

        Yields:
            Nothing — the context manager manages the savepoint lifecycle.
        """
        base_name = name or (
            self._id_generator.generate()[:12]
            if self._id_generator
            else uuid.uuid4().hex[:12]
        )
        sp_name = f"sp_{validate_identifier(base_name)}"

        if (
            self._in_transaction_var.get()
            and self._transaction_connection_var.get() is not None
        ):
            conn = self._transaction_connection_var.get()
            await self._create_savepoint_raw(conn, sp_name)
            try:
                yield
                await self._release_savepoint_raw(conn, sp_name)
            except Exception as e:  # noqa: BLE001 — savepoint must rollback on any failure
                logger.warning("savepoint_rollback", savepoint=sp_name, error=str(e))
                await self._rollback_to_savepoint_raw(conn, sp_name)
                raise
        else:
            # No outer transaction — wrap in one transparently.
            async with self.transaction():
                conn = self._transaction_connection_var.get()
                await self._create_savepoint_raw(conn, sp_name)
                try:
                    yield
                    await self._release_savepoint_raw(conn, sp_name)
                except Exception as e:  # noqa: BLE001 — savepoint must rollback on any failure
                    logger.warning(
                        "savepoint_rollback", savepoint=sp_name, error=str(e)
                    )
                    await self._rollback_to_savepoint_raw(conn, sp_name)
                    raise

    async def begin_transaction(self) -> None:
        """Begin a transaction"""
        if self._in_transaction_var.get():
            return

        connection = await self.connection_manager._create_connection()
        await self.connection_manager._emit_connection_acquired()
        self._transaction_connection_var.set(connection)
        await self._begin_transaction_raw(connection)
        self._in_transaction_var.set(True)
        await self._emit_transaction_begin()

    async def commit_transaction(self) -> None:
        """Commit current transaction"""
        if (
            not self._in_transaction_var.get()
            or not self._transaction_connection_var.get()
        ):
            return

        conn = self._transaction_connection_var.get()
        await self._commit_transaction_raw(conn)
        await self._emit_transaction_end(committed=True)
        await self.connection_manager._close_connection(conn)
        self._transaction_connection_var.set(None)
        self._in_transaction_var.set(False)

    async def rollback_transaction(self) -> None:
        """Rollback current transaction"""
        if (
            not self._in_transaction_var.get()
            or not self._transaction_connection_var.get()
        ):
            return

        conn = self._transaction_connection_var.get()
        await self._rollback_transaction_raw(conn)
        await self._emit_transaction_end(committed=False)
        await self.connection_manager._close_connection(conn)
        self._transaction_connection_var.set(None)
        self._in_transaction_var.set(False)
