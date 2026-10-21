"""SQLAlchemy ORM session factory.

Why this exists
---------------
``DatabaseProviderProtocol`` is a *connection and raw-SQL* interface —
``execute_query``, ``transaction``, pools — built on aiosqlite/asyncpg
directly. Applications that map declarative models need a SQLAlchemy
``AsyncEngine`` and ``async_sessionmaker``, and there was no way to obtain
one from the framework.

The practical consequence was that every such application created its own
engine from the same URL, so one deployment ran **two independent pools**
against one database: double the connections, two sets of pragmas to keep
in step, and no shared transaction between a repository call and an ORM
call. ``apps/qk-erp`` hit exactly this and recorded it as Improve-QuadKit
gap #1 rather than quietly living with it.

This module closes that gap: one engine, one pool, resolvable from the
container.

SQLite handling
---------------
The engine is tuned with :func:`configure_sqlite_pragmas` automatically,
so an ORM engine gets the same ``busy_timeout``/journal policy the raw
providers already apply. Journal mode is configurable because WAL needs
``-wal``/``-shm`` sidecar files, which overlay and network filesystems —
including many CI sandboxes and container volumes — reject with
``disk I/O error``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from quadkit.logging import get_logger
from quadkit.sql.performance.engine_pragmas import configure_sqlite_pragmas

logger = get_logger(__name__)

__all__ = ["SessionFactory"]


class SessionFactory:
    """Owns one :class:`AsyncEngine` and hands out ORM sessions.

    Args:
        url: SQLAlchemy database URL, e.g.
            ``postgresql+asyncpg://user:pw@host/db`` or
            ``sqlite+aiosqlite:///./app.db``.
        echo: Log every statement. Development only.
        pool_size: Connections kept open. Ignored by SQLite.
        max_overflow: Extra connections allowed beyond ``pool_size``.
        pool_recycle: Seconds before a pooled connection is replaced.
            Guards against a proxy or database closing idle connections.
        expire_on_commit: Left ``False`` by default so attributes stay
            readable after commit — the usual source of surprise
            ``MissingGreenlet`` errors in async code.
        sqlite_journal_mode: Journal mode applied to SQLite engines.
            ``TRUNCATE`` is the safe default; ``WAL`` is faster but needs
            sidecar files the filesystem may refuse.
        engine_kwargs: Passed straight to ``create_async_engine``.

    Example:
        ```python
        factory = await container.resolve(SessionFactory)

        async with factory.session() as session:
            rows = (await session.execute(select(User))).scalars().all()

        async with factory.begin() as session:   # commits on success
            session.add(User(name="Mei"))
        ```
    """

    def __init__(
        self,
        url: str,
        *,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_recycle: int = 3600,
        expire_on_commit: bool = False,
        sqlite_journal_mode: str = "TRUNCATE",
        **engine_kwargs: Any,
    ) -> None:
        self.url = url
        self._is_sqlite = url.startswith("sqlite")
        self._expire_on_commit = expire_on_commit
        self._sqlite_journal_mode = sqlite_journal_mode

        options: dict[str, Any] = {"echo": echo, "future": True, **engine_kwargs}
        if not self._is_sqlite:
            # SQLite's driver manages a single file handle; pool sizing is
            # meaningless and SQLAlchemy rejects some of these for it.
            options.setdefault("pool_size", pool_size)
            options.setdefault("max_overflow", max_overflow)
            options.setdefault("pool_recycle", pool_recycle)
            options.setdefault("pool_pre_ping", True)
        self._options = options

        self._engine_instance: AsyncEngine | None = None
        self._sessionmaker_instance: async_sessionmaker[AsyncSession] | None = None

    # -- access ------------------------------------------------------------

    def _build(self) -> AsyncEngine:
        """Create the engine on first use.

        Deliberately **lazy**. Constructing a factory should not resolve a
        database driver: an application configured with a sync URL
        (``sqlite://`` rather than ``sqlite+aiosqlite://``) uses the raw
        providers perfectly well and may never ask for an ORM session. If
        the engine were built at registration time, merely wiring the
        container would fail for those apps.
        """
        engine = create_async_engine(self.url, **self._options)
        if self._is_sqlite:
            configure_sqlite_pragmas(
                engine.sync_engine, journal_mode=self._sqlite_journal_mode
            )
        logger.debug(
            "sql.session_factory_created",
            extra={"dialect": engine.dialect.name, "sqlite": self._is_sqlite},
        )
        return engine

    @property
    def engine(self) -> AsyncEngine:
        """The underlying engine — for DDL, migrations and introspection."""
        if self._engine_instance is None:
            self._engine_instance = self._build()
        return self._engine_instance

    @property
    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        """The raw sessionmaker, for callers that manage their own scope."""
        if self._sessionmaker_instance is None:
            self._sessionmaker_instance = async_sessionmaker(
                self.engine, expire_on_commit=self._expire_on_commit
            )
        return self._sessionmaker_instance

    def __call__(self) -> AsyncSession:
        """Create a session, so the factory is a drop-in ``sessionmaker``."""
        return self.sessionmaker()

    # -- scopes ------------------------------------------------------------

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """A session with no surrounding transaction. Closes on exit."""
        async with self.sessionmaker() as session:
            yield session

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        """A session inside a transaction: commits on success, rolls back on error."""
        async with self.sessionmaker() as session, session.begin():
            yield session

    # -- lifecycle ---------------------------------------------------------

    async def dispose(self) -> None:
        """Close every pooled connection. Safe if the engine was never built."""
        if self._engine_instance is None:
            return
        await self._engine_instance.dispose()
        self._engine_instance = None
        self._sessionmaker_instance = None
        logger.debug("sql.session_factory_disposed")
