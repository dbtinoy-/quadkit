"""
Connection management for database providers.

Handles connection lifecycle, pooling, and basic connection operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qs, urlparse

from quadkit.contracts.core import HookRegistryProtocol
from quadkit.logging import get_logger
from quadkit.sql import ConnectionPoolProtocol
from quadkit.sql.abstractions.connection import DatabaseConnection
from quadkit.sql.exceptions import DatabaseConnectionError
from quadkit.sql.hooks import SQLConnectionReadyHook

logger = get_logger(__name__)


class ConnectionManager(ABC):
    """
    Manages database connections and connection pooling.

    This class handles the lifecycle of database connections, including
    creation, pooling, and cleanup operations.
    """

    def __init__(
        self,
        connection_string: str,
        connection_pool: ConnectionPoolProtocol | None = None,
    ) -> None:
        self.connection_string = connection_string
        self.connection_pool = connection_pool
        self._connected = False
        # A failed transaction cleanup leaves connection state uncertain. Do
        # not silently return that connection (or pool) to application use.
        self._quarantined = False
        self._connection: Any | None = None
        self._hooks: HookRegistryProtocol | None = None
        self._transaction_context_validator: Callable[[], None] | None = None
        self._transaction_connection_supplier: Callable[[], Any | None] | None = None
        # Serialize access to the shared single connection so that concurrent
        # coroutines cannot both run queries on the same asyncpg connection
        # simultaneously (which would raise InterfaceError).
        self._connection_lock: asyncio.Lock | None = None
        # Task that currently holds _connection_lock; enables reentrant
        # acquisition when a transaction and its inner queries share the
        # same coroutine (e.g. SQLiteProvider single-connection mode).
        self._connection_holder: asyncio.Task[Any] | None = None
        # Set by DatabaseDriver after both managers have been constructed.
        self.transaction_manager: Any | None = None

        # Parse connection string for metadata (supporting libpq ?host=/socket/dir)
        parsed = urlparse(connection_string)
        query_params = parse_qs(parsed.query)
        self.database_type = (
            parsed.scheme.split("+")[0] if "+" in parsed.scheme else parsed.scheme
        )
        host_param = query_params.get("host", [None])[0]
        port_param = query_params.get("port", [None])[0]
        self.host = parsed.hostname or host_param
        self.port = parsed.port or (
            int(port_param) if port_param and port_param.isdigit() else None
        )
        self.database = parsed.path.lstrip("/") if parsed.path else None
        self.username = parsed.username
        self.password = parsed.password

    @property
    def connected(self) -> bool:
        """Check if database is connected"""
        return self._connected and not self._quarantined

    def quarantine(self) -> None:
        """Permanently refuse new managed acquisitions after uncertain cleanup.

        A fresh manager/provider is required. This does not revoke raw handles,
        stop already-running operations, or quarantine an independently shared
        pool accessed directly outside this manager.
        """
        self._quarantined = True

    def _require_usable(self) -> None:
        if self._quarantined:
            raise DatabaseConnectionError("database connection unavailable")
        if self._transaction_context_validator is not None:
            self._transaction_context_validator()

    def set_transaction_context_validator(
        self, validator: Callable[[], None] | None
    ) -> None:
        """Validate task ownership before managed acquisition or reconnect."""
        self._transaction_context_validator = validator

    def set_transaction_connection_supplier(
        self, supplier: Callable[[], Any | None] | None
    ) -> None:
        """Bind managed acquisitions to the owner task's transaction connection."""
        self._transaction_connection_supplier = supplier

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry for connection acquisition events."""
        self._hooks = hooks

    async def _emit_connection_acquired(self) -> None:
        """Emit the canonical connection acquisition hook when configured."""
        if self._hooks is None:
            return

        await self._hooks.call_action(
            "connection.acquired",
            payload=SQLConnectionReadyHook(backend=self.database_type),
        )

    async def connect(self) -> None:
        """Establish connection to the database"""
        self._require_usable()
        if self.connection_pool:
            await self.connection_pool.initialize()
            # Warm-up: acquire a connection to ensure pool works
            conn_cm = self.connection_pool.get_connection()
            if hasattr(conn_cm, "__aenter__"):  # Check if it's async
                async with conn_cm:
                    pass
        # Connecting twice must not replace the handle: an in-memory database
        # belongs to its connection, so whichever coroutine opened it owns the
        # schema — a second connect would silently start from an empty one.
        elif self._connection is None:
            self._connection = await self._create_connection()
        self._connected = True
        logger.info("Connected to %s database", self.database_type)

    async def disconnect(self) -> None:
        """Close connection to the database"""
        if self.connection_pool:
            await self.connection_pool.shutdown()
        elif self._connection:
            await self._close_connection(self._connection)
            self._connection = None
        self._connected = False
        logger.info("Disconnected from %s database", self.database_type)

    @abstractmethod
    async def _create_connection(self) -> Any:
        """Create a database connection (implementation-specific)"""

    @abstractmethod
    async def _close_connection(self, connection: Any) -> None:
        """Close a database connection (implementation-specific)"""

    @asynccontextmanager
    async def get_connection(self) -> Any:
        """Get a connection from pool or create new one"""
        self._require_usable()
        manager = self.transaction_manager
        if manager is not None and manager.in_transaction:
            # Queries and CRUD must use the same connection as BEGIN/COMMIT,
            # including with a pool or manually started transaction.
            conn = manager.current_connection()
            await self._emit_connection_acquired()
            self._require_usable()
            yield conn
        elif self.connection_pool:
            # Quadkit pools yield an abstraction wrapping the native driver
            # handle, but driver methods expect that native handle. Unwrap only
            # known connection abstractions, never arbitrary driver's internals.
            # Pool implementations may translate exceptions thrown through
            # their context into connection errors; defer caller exceptions
            # until after release so their type and transaction outcome survive.
            failure: BaseException | None = None
            async with self.connection_pool.get_connection() as pooled:
                self._require_usable()
                conn = pooled
                if isinstance(pooled, DatabaseConnection):
                    conn = getattr(pooled, "_conn", None)
                    if conn is None:
                        raise RuntimeError(
                            "pool connection has no native driver handle"
                        )
                await self._emit_connection_acquired()
                self._require_usable()
                try:
                    yield conn
                except BaseException as exc:
                    failure = exc
            if failure is not None:
                raise failure.with_traceback(failure.__traceback__)
        else:
            if not self._connection:
                self._connection = await self._create_connection()
            # Lazily create the lock inside an async context so there is no
            # issue with creating asyncio.Lock() outside of an event loop.
            if self._connection_lock is None:
                self._connection_lock = asyncio.Lock()
            holder = self._connection_holder
            if holder is not None and holder is asyncio.current_task():
                # Reentrant acquisition: the active task already holds the
                # connection (transaction context), so reuse it directly
                # instead of deadlocking on the non-reentrant lock.
                await self._emit_connection_acquired()
                self._require_usable()
                yield self._connection
                return
            async with self._connection_lock:
                self._require_usable()
                self._connection_holder = asyncio.current_task()
                try:
                    await self._emit_connection_acquired()
                    self._require_usable()
                    yield self._connection
                finally:
                    self._connection_holder = None
