"""
Connection management for database providers.

Handles connection lifecycle, pooling, and basic connection operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

from quadkit.contracts.core import HookRegistryProtocol
from quadkit.logging import get_logger
from quadkit.sql import ConnectionPoolProtocol
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
        self._connection: Any | None = None
        self._hooks: HookRegistryProtocol | None = None
        # Serialize access to the shared single connection so that concurrent
        # coroutines cannot both run queries on the same asyncpg connection
        # simultaneously (which would raise InterfaceError).
        self._connection_lock: asyncio.Lock | None = None
        # Task that currently holds _connection_lock; enables reentrant
        # acquisition when a transaction and its inner queries share the
        # same coroutine (e.g. SQLiteProvider single-connection mode).
        self._connection_holder: asyncio.Task[Any] | None = None

        # Parse connection string for metadata
        parsed = urlparse(connection_string)
        self.database_type = (
            parsed.scheme.split("+")[0] if "+" in parsed.scheme else parsed.scheme
        )
        self.host = parsed.hostname
        self.port = parsed.port
        self.database = parsed.path.lstrip("/") if parsed.path else None
        self.username = parsed.username
        self.password = parsed.password

    @property
    def connected(self) -> bool:
        """Check if database is connected"""
        return self._connected

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
        if self.connection_pool:
            async with self.connection_pool.get_connection() as conn:
                await self._emit_connection_acquired()
                yield conn
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
                yield self._connection
                return
            async with self._connection_lock:
                self._connection_holder = asyncio.current_task()
                try:
                    await self._emit_connection_acquired()
                    yield self._connection
                finally:
                    self._connection_holder = None
