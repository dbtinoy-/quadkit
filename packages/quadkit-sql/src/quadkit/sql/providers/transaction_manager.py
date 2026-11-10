"""
Transaction management for database providers.

Handles database transactions including context managers and manual control.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from contextlib import asynccontextmanager
import contextvars
from dataclasses import dataclass
from hashlib import sha256
from itertools import count
from typing import TYPE_CHECKING, Any
import uuid

from quadkit.contracts.core import HookRegistryProtocol
from quadkit.contracts.data.identifiers import validate_identifier

if TYPE_CHECKING:
    from quadkit.contracts.core.identity import IdGeneratorProtocol
from quadkit.contracts.data.sql.database import IsolationLevel
from quadkit.logging import get_logger
from quadkit.sql.exceptions import TransactionError
from quadkit.sql.hooks import SQLTransactionBegunHook, SQLTransactionEndedHook

logger = get_logger(__name__)


@dataclass
class _TransactionScope:
    connection: Any
    owner: asyncio.Task[Any] | None
    active: bool = True
    rollback_only: bool = False
    manual_lease: Any | None = None


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
        self._savepoint_counter = count()
        self._hooks: HookRegistryProtocol | None = None
        self._in_transaction_var: contextvars.ContextVar[bool] = contextvars.ContextVar(
            "transaction_in_transaction", default=False
        )
        self._transaction_connection_var: contextvars.ContextVar[Any | None] = (
            contextvars.ContextVar("transaction_connection", default=None)
        )
        self._scope_var: contextvars.ContextVar[_TransactionScope | None] = (
            contextvars.ContextVar("transaction_scope", default=None)
        )

    def current_connection(self) -> Any:
        """Return this task's live transaction connection, or refuse unsafe use.

        Context variables are copied into child tasks. A connection must not be
        used concurrently by a child or after its owning scope has ended.
        """
        self._require_transaction_owner()
        scope = self._scope_var.get()
        if scope is None or not scope.active:
            raise RuntimeError("transaction connection is no longer active")
        return scope.connection

    def _set_scope(self, connection: Any) -> None:
        self._scope_var.set(_TransactionScope(connection, asyncio.current_task()))
        self._transaction_connection_var.set(connection)
        self._in_transaction_var.set(True)

    def _clear_scope(self) -> None:
        scope = self._scope_var.get()
        if scope is not None:
            scope.active = False
        self._scope_var.set(None)
        self._transaction_connection_var.set(None)
        self._in_transaction_var.set(False)

    def _require_transaction_owner(self) -> None:
        """Refuse a transaction context copied into another asyncio task."""
        if not self._in_transaction_var.get():
            return
        scope = self._scope_var.get()
        try:
            current = asyncio.current_task()
        except RuntimeError:
            current = None
        if scope is None or current is None or scope.owner is not current:
            raise TransactionError("transaction context belongs to another task")

    @property
    def in_transaction(self) -> bool:
        """Check whether the current task owns an active transaction."""
        self._require_transaction_owner()
        return self._in_transaction_var.get()

    @property
    def _transaction_connection(self) -> Any | None:
        """Compatibility accessor for the current transaction connection."""
        self._require_transaction_owner()
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

    def _check_outer_transaction_boundary(self, connection: Any) -> None:
        """Check for known physical ambient work, if the driver supports it.

        Custom managers may leave this unimplemented. This check does not
        protect against direct raw users racing after the check.
        """

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
        await self._execute_savepoint_sql(connection, f"SAVEPOINT {name}")

    async def _release_savepoint_raw(self, connection: Any, name: str) -> None:
        """Release (commit) a savepoint.

        Args:
            connection: Active database connection.
            name: Savepoint name.
        """
        await self._execute_savepoint_sql(connection, f"RELEASE SAVEPOINT {name}")

    async def _rollback_to_savepoint_raw(self, connection: Any, name: str) -> None:
        """Roll back to a savepoint without undoing the outer transaction.

        Args:
            connection: Active database connection.
            name: Savepoint name.
        """
        await self._execute_savepoint_sql(connection, f"ROLLBACK TO SAVEPOINT {name}")

    async def _execute_savepoint_sql(self, connection: Any, statement: str) -> None:
        """Support direct-execute drivers and cursor-only drivers such as aiomysql."""
        if callable(getattr(connection, "execute", None)):
            await connection.execute(statement)
        else:
            async with connection.cursor() as cursor:
                await cursor.execute(statement)

    async def _quarantine_and_close(self, connection: Any) -> None:
        """Refuse managed reuse and attempt to close the uncertain connection."""
        self.connection_manager.quarantine()
        try:
            await self.connection_manager._close_connection(connection)
        except BaseException:
            # The connection and any externally held raw handles remain unsafe.
            logger.error("Failed to close quarantined database connection")

    async def _rollback_after_failure(self, connection: Any) -> tuple[bool, bool]:
        """Attempt rollback without releasing the connection on repeated cancellation.

        Return (rollback_succeeded, additional_cancellation). If the driver
        cannot roll back, refuse future acquisitions through this manager. This
        is not evidence that an interrupted COMMIT did not take effect, and it
        cannot revoke raw connections or independently shared pool references.
        """

        async def rollback_or_quarantine() -> bool:
            try:
                await self._rollback_transaction_raw(connection)
                return True
            except BaseException:
                # Driver errors may contain SQL or sensitive bind values.
                logger.error("Rollback failed in DatabaseDriver.transaction")
                await self._quarantine_and_close(connection)
                return False

        task = asyncio.create_task(rollback_or_quarantine())
        cancelled_again = False
        while True:
            try:
                return await asyncio.shield(task), cancelled_again
            except asyncio.CancelledError:
                if task.cancelled():
                    self.connection_manager.quarantine()
                    logger.error("Rollback failed in DatabaseDriver.transaction")
                    return False, True
                cancelled_again = True

    async def _close_after_hook_failure(self, connection: Any) -> bool:
        """Keep the lock until a failed rollback hook's connection is closed."""
        self.connection_manager.quarantine()
        task = asyncio.create_task(self._quarantine_and_close(connection))
        cancelled_again = False
        while True:
            try:
                await asyncio.shield(task)
                return cancelled_again
            except asyncio.CancelledError:
                if task.cancelled():
                    return True
                cancelled_again = True

    @asynccontextmanager
    async def transaction(self, isolation: IsolationLevel | None = None) -> Any:
        """Context manager for transactions.

        Nested scopes use savepoints; catching a nested exception does not
        commit its writes. Operations must stay in the owning asyncio task;
        child tasks cannot safely share or outlive its connection. An explicit
        isolation level applies only when starting the outer transaction.

        Args:
            isolation: Optional isolation level. When ``None`` the driver's
                default is used.
        """
        self._require_transaction_owner()
        self.connection_manager._require_usable()
        if self._in_transaction_var.get():
            # The caller may catch a nested failure and continue the outer
            # transaction. Isolate that work instead of silently committing it.
            self.current_connection()
            async with self.savepoint():
                yield
            return

        async with self.connection_manager.get_connection() as conn:
            # Refuse before setting task state or attempting BEGIN: cleanup must
            # not roll back or commit a transaction owned by a raw caller.
            self._check_outer_transaction_boundary(conn)
            self._set_scope(conn)
            committed = False
            try:
                await self._begin_transaction_raw(conn, isolation)
                await self._emit_transaction_begin()
                yield
                scope = self._scope_var.get()
                if scope is not None and scope.rollback_only:
                    raise RuntimeError(
                        "transaction requires rollback after savepoint failure"
                    )
                await self._commit_transaction_raw(conn)
                committed = True
                await self._emit_transaction_end(committed=True)
                # A successful hook can still open an implicit transaction on
                # the just-committed connection. Known drivers can detect it
                # before the connection is returned to the pool or reused.
                self._check_outer_transaction_boundary(conn)
            except BaseException:
                if not committed:
                    rolled_back, cancelled_again = await self._rollback_after_failure(
                        conn
                    )
                    if rolled_back:
                        try:
                            # Hooks run in the transaction-owning task, not the
                            # rollback task, to preserve reentrant lock behavior.
                            await self._emit_transaction_end(committed=False)
                            self._check_outer_transaction_boundary(conn)
                        except BaseException as hook_error:
                            logger.error("Transaction rollback hook failed")
                            cancelled_again = (
                                await self._close_after_hook_failure(conn)
                                or cancelled_again
                                or isinstance(hook_error, asyncio.CancelledError)
                            )
                    if cancelled_again:
                        raise asyncio.CancelledError from None
                # COMMIT returned but the completion hook failed; do not
                # report rollback, and do not reuse a hook-mutated connection.
                elif await self._close_after_hook_failure(conn):
                    raise asyncio.CancelledError from None
                # A failed or cancelled COMMIT may already have succeeded. An
                # attempted rollback is cleanup, not proof of its outcome.
                raise
            finally:
                self._clear_scope()

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
        if name is None:
            generated = (
                sha256(self._id_generator.generate().encode()).hexdigest()[:12]
                if self._id_generator
                else uuid.uuid4().hex[:12]
            )
            # Repeated IDs from an injected generator must not alias a live
            # nested savepoint on the same connection.
            base_name = f"{generated}_{next(self._savepoint_counter)}"
        else:
            base_name = name
        sp_name = validate_identifier(f"sp_{base_name}")

        if not self._in_transaction_var.get():
            async with self.transaction():
                async with self.savepoint(name):
                    yield
            return

        conn = self.current_connection()
        try:
            await self._create_savepoint_raw(conn, sp_name)
        except BaseException:
            scope = self._scope_var.get()
            if scope is not None:
                scope.rollback_only = True
            raise
        try:
            yield
            await self._release_savepoint_raw(conn, sp_name)
        except BaseException as exc:
            logger.warning("savepoint_rollback", savepoint=sp_name, error=str(exc))
            try:
                await self._rollback_to_savepoint_raw(conn, sp_name)
                await self._release_savepoint_raw(conn, sp_name)
            except BaseException:  # noqa: BLE001 — preserve the original exception
                scope = self._scope_var.get()
                if scope is not None:
                    scope.rollback_only = True
                logger.exception("Savepoint rollback failed")
            raise

    async def begin_transaction(self) -> None:
        """Begin a transaction"""
        self._require_transaction_owner()
        self.connection_manager._require_usable()
        if self._in_transaction_var.get():
            self.current_connection()
            return

        lease = self.connection_manager.get_connection()
        connection = await lease.__aenter__()
        try:
            await self._begin_transaction_raw(connection)
            self._set_scope(connection)
            scope = self._scope_var.get()
            assert scope is not None
            scope.manual_lease = lease
            await self._emit_transaction_begin()
        except BaseException:
            try:
                await self._rollback_transaction_raw(connection)
            except BaseException:  # noqa: BLE001 — keep the original failure
                logger.exception("Rollback failed while starting manual transaction")
            self._clear_scope()
            await lease.__aexit__(None, None, None)
            raise

    async def commit_transaction(self) -> None:
        """Commit current transaction."""
        self._require_transaction_owner()
        self.connection_manager._require_usable()
        if not self._in_transaction_var.get():
            return
        conn = self.current_connection()
        scope = self._scope_var.get()
        if scope is None or scope.manual_lease is None:
            raise RuntimeError("cannot manually commit a managed transaction")
        if scope.rollback_only:
            await self.rollback_transaction()
            raise RuntimeError("transaction requires rollback after savepoint failure")
        try:
            try:
                await self._commit_transaction_raw(conn)
            except BaseException:
                try:
                    await self._rollback_transaction_raw(conn)
                except BaseException:  # noqa: BLE001 — preserve the commit error
                    logger.exception("Rollback failed after manual commit error")
                raise
            await self._emit_transaction_end(committed=True)
        finally:
            self._clear_scope()
            await scope.manual_lease.__aexit__(None, None, None)

    async def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        self._require_transaction_owner()
        self.connection_manager._require_usable()
        if not self._in_transaction_var.get():
            return
        conn = self.current_connection()
        scope = self._scope_var.get()
        if scope is None or scope.manual_lease is None:
            raise RuntimeError("cannot manually roll back a managed transaction")
        try:
            await self._rollback_transaction_raw(conn)
            await self._emit_transaction_end(committed=False)
        finally:
            self._clear_scope()
            await scope.manual_lease.__aexit__(None, None, None)
