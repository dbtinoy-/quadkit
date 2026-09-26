"""Connection and transaction manager for quadkit-sql."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Self

from quadkit.contracts import UnitOfWorkProtocol
from quadkit.contracts.core import HookRegistryProtocol
from quadkit.di.decorators import inject
from quadkit.domain.unit_of_work import run_lifecycle_hooks
from quadkit.logging import get_logger
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)
from quadkit.sql.hooks import SQLConnectionReadyHook
from quadkit.sql.unit_of_work.identity_map import IdentityMap

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from quadkit.contracts.domain.events import DomainEvent
    from quadkit.sql.providers import DatabaseService

logger = get_logger(__name__)


class ScopedUnitOfWork(UnitOfWorkProtocol):
    """Unit of Work that uses scoped database connections."""

    def __init__(self, manager_or_provider: Any):
        # Improved check for shims/mocks
        if (
            hasattr(manager_or_provider, "manager")
            and manager_or_provider.manager is not None
        ):
            # If it's a Mock, manager_or_provider.manager will be another Mock
            # which is usually what we want if it's a DatabaseService
            self.manager = manager_or_provider.manager
            self.provider = manager_or_provider
        else:
            self.manager = manager_or_provider
            self.provider = getattr(manager_or_provider, "provider", None)

        self._committed = False
        self._rolled_back = False
        self.identity_map: IdentityMap = IdentityMap()
        self._new_entities: list[Any] = []
        self._dirty_entities: list[Any] = []
        self._deleted_entities: list[Any] = []
        self._events: list[DomainEvent] = []
        self._commit_hooks: list[Callable[[], Any]] = []
        self._rollback_hooks: list[Callable[[], Any]] = []

    def register_new(self, entity: Any) -> None:
        """Register a new entity scheduled for insertion."""
        self._new_entities.append(entity)

    def register_dirty(self, entity: Any) -> None:
        """Register an existing entity with pending changes."""
        if entity not in self._dirty_entities:
            self._dirty_entities.append(entity)

    def register_deleted(self, entity: Any) -> None:
        """Register an entity scheduled for deletion."""
        if entity not in self._deleted_entities:
            self._deleted_entities.append(entity)

    # ------------------------------------------------------------------
    # Event collection
    # ------------------------------------------------------------------

    def register_event(self, event: DomainEvent) -> None:
        """Collect a domain event to be gathered after commit.

        The internal list is cleared at the end of :meth:`commit` or
        :meth:`rollback`.
        """
        self._events.append(event)

    def collect_events(self) -> list[DomainEvent]:
        """Return all collected domain events without clearing them.

        The list is cleared by :meth:`commit` or :meth:`rollback`.
        """
        return list(self._events)

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_commit(self, callback: Callable[[], Any]) -> None:
        """Register a callback to run after a successful commit.

        The callback may be a plain function or a coroutine function (or a
        sync function returning an awaitable); awaitable results are awaited.
        """
        self._commit_hooks.append(callback)

    def on_rollback(self, callback: Callable[[], Any]) -> None:
        """Register a callback to run after a rollback.

        The callback may be a plain function or a coroutine function (or a
        sync function returning an awaitable); awaitable results are awaited.
        """
        self._rollback_hooks.append(callback)

    async def commit(self) -> None:
        """Commit the unit of work and run registered commit hooks."""
        if not self._committed and not self._rolled_back:
            if self.manager.provider.db_provider:
                await self.manager.provider.db_provider.commit()
            self._committed = True
            self._events.clear()
            await run_lifecycle_hooks(self._commit_hooks)

    async def rollback(self) -> None:
        """Rollback the unit of work and run registered rollback hooks.

        A no-op once committed — there is nothing left to roll back.
        """
        if not self._rolled_back and not self._committed:
            if self.manager.provider.db_provider:
                await self.manager.provider.db_provider.rollback()
            self._rolled_back = True
            self._events.clear()
            await run_lifecycle_hooks(self._rollback_hooks)

    async def __aenter__(self) -> Self:
        context = self.manager.get_current_context()
        if context:
            context["transaction_level"] += 1
            if context["transaction_level"] == 1 and self.manager.provider.db_provider:
                await self.manager.provider.db_provider.begin_transaction()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        context = self.manager.get_current_context()
        if context:
            context["transaction_level"] -= 1
            if context["transaction_level"] == 0:
                # Route through commit()/rollback() so lifecycle hooks run,
                # state flags are set, and a second commit/rollback (e.g. an
                # explicit ``await uow.commit()`` inside the block) is a
                # guarded no-op instead of a double provider call.
                if exc_type is None:
                    await self.commit()
                else:
                    await self.rollback()


@inject
class DatabaseManager:
    """Handles connection pooling, scoped contexts, and transactions."""

    def __init__(self, provider: DatabaseService):
        self.provider = provider
        self._hooks: HookRegistryProtocol | None = None
        # Per-instance ContextVar — eliminates the module-level global.
        self._context_var: ContextVar[dict[str, Any] | None] = ContextVar(
            "db_context",
            default=None,
        )

    def get_current_context(self) -> dict[str, Any] | None:
        """Get the current database context for this request/scope."""
        return self._context_var.get()

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry for scoped connection events."""
        self._hooks = hooks

    async def _emit_connection_acquired(self) -> None:
        """Emit the canonical connection acquisition hook when configured."""
        if self._hooks is None:
            return

        await self._hooks.call_action(
            "connection.acquired",
            payload=SQLConnectionReadyHook(backend=self.provider.database_type),
        )

    @asynccontextmanager
    async def transaction(
        self, isolation_level: Any | None = None
    ) -> AsyncGenerator[None, None]:
        """Async context manager for transaction management through provider."""
        if not self.provider.db_provider:
            await self.provider.boot()

        # This assumes the underlying driver supports transaction() async context manager
        if self.provider.db_provider and hasattr(
            self.provider.db_provider, "transaction"
        ):
            async with self.provider.db_provider.transaction(isolation_level):
                yield
        elif self.provider.db_provider:
            # Fallback if driver doesn't have transaction method
            await self.provider.db_provider.begin_transaction()
            try:
                yield
                await self.provider.db_provider.commit_transaction()
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
                if self.provider.db_provider:
                    await self.provider.db_provider.rollback_transaction()
                raise

    @asynccontextmanager
    async def scoped_context(self) -> AsyncGenerator[dict[str, Any], None]:
        """Context manager for scoped database operations."""
        context = {
            "connection": None,
            "transaction_level": 0,
            "created_at": asyncio.get_running_loop().time(),
        }
        token = self._context_var.set(context)
        try:
            yield context
        finally:
            if context.get("connection"):
                connection = context["connection"]
                if self.provider.connection_pool:
                    conn_cm = context.get("_connection_cm")
                    if conn_cm is not None:
                        try:
                            if hasattr(conn_cm, "__aexit__"):
                                await conn_cm.__aexit__(None, None, None)
                        except (AttributeError, TypeError, RuntimeError):
                            logger.exception("Error exiting connection context manager")
                    else:
                        try:
                            cp = self.provider.connection_pool
                            if cp and hasattr(cp, "return_connection"):
                                await cp.return_connection(connection)
                        except (
                            AttributeError,
                            TypeError,
                            ConnectionError,
                            RuntimeError,
                        ):
                            logger.exception("Error returning connection to pool")
                else:
                    # No pool — close raw connection to prevent leaks.
                    try:
                        if (
                            hasattr(connection, "close")
                            and not getattr(connection, "is_closed", lambda: False)()
                        ):
                            await connection.close()  # type: ignore[union-attr]
                    except Exception as e:  # noqa: BLE001 — best-effort cleanup; must not raise in finally
                        logger.debug("connection_close_failed", error=str(e))
            self._context_var.reset(token)

    def get_unit_of_work(self) -> UnitOfWorkProtocol:
        """Get a unit of work that uses scoped connections."""
        return ScopedUnitOfWork(self)

    async def get_connection(self) -> Any:
        """Get a connection for the current scope.

        Raises:
            RuntimeError: If called outside a :meth:`scoped_context` while
                a connection pool is configured.  Pool slots are released
                when the owning scope exits; acquiring without a scope
                would leak the slot and, after enough out-of-scope borrows,
                exhaust the pool (every later acquire stalls).  Outside a
                scope use ``DatabaseService.get_connection()`` (async
                context manager) or ``acquire()`` / ``release()`` instead.
        """
        context = self.get_current_context()
        if context and context.get("connection"):
            return context["connection"]

        if self.provider.connection_pool:
            if context is None:
                msg = (
                    "DatabaseManager.get_connection() was called outside a "
                    "scoped_context while a connection pool is configured. "
                    "Use DatabaseService.get_connection() (async context "
                    "manager) or acquire()/release() outside a scope."
                )
                raise RuntimeError(msg)
            if not getattr(self.provider.connection_pool, "_initialized", False):
                await self.provider.connection_pool.initialize()

            conn_cm = self.provider.connection_pool.get_connection()
            if asyncio.iscoroutine(conn_cm):
                conn_cm = await conn_cm

            connection = await conn_cm.__aenter__()
            await self._emit_connection_acquired()
            if context:
                context["connection"] = connection
                context["_connection_cm"] = conn_cm
            return connection

        if self.provider.db_provider:
            create_fn = getattr(self.provider.db_provider, "_create_connection", None)
            if create_fn:
                connection = await create_fn()
                await self._emit_connection_acquired()
                if context:
                    context["connection"] = connection
                return connection

        raise RuntimeError("No database provider or pool available")


__all__ = [
    "DatabaseManager",
    "ScopedUnitOfWork",
]
