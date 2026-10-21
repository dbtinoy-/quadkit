"""Run the raw-SQL executor protocol over an ORM session.

Several framework stores (:class:`~quadkit.sql.outbox.SQLOutboxStore`, the
admin audit store) are written against the minimal ``execute`` /
``fetch_all`` surface of the database provider. An application that holds
its data in SQLAlchemy sessions (through :class:`SessionFactory`) has to
hand those stores a session, not a second pool — otherwise "write the
event in the same transaction as the row" is a sentence, not a property.

Two adapters:

* :class:`SessionExecutor` — one open session; statements join whatever
  transaction it is in and commit when the owner commits. This is what a
  transactional outbox needs.
* :class:`SessionmakerExecutor` — a fresh session per statement, each in
  its own committed transaction. For pollers and relays that run outside
  any business transaction.

Statements use named parameters (``:name``), the dialect SQLAlchemy's
``text()`` speaks on every backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

__all__ = ["SessionExecutor", "SessionmakerExecutor"]


def _params(
    params: Mapping[str, Any] | tuple[Any, ...] | None,
) -> dict[str, Any] | None:
    if params is None:
        return None
    if isinstance(params, tuple):
        msg = "SessionExecutor takes named parameters (:name); positional tuples are not supported"
        raise TypeError(msg)
    return dict(params)


class SessionExecutor:
    """Execute raw SQL on one session, inside the owner's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, sql: str, params: Mapping[str, Any] | tuple[Any, ...] | None = None
    ) -> None:
        await self._session.execute(sa.text(sql), _params(params))

    async def fetch_all(
        self, sql: str, params: Mapping[str, Any] | tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        result = await self._session.execute(sa.text(sql), _params(params))
        return [dict(row) for row in result.mappings().all()]

    async def fetch_one(
        self, sql: str, params: Mapping[str, Any] | tuple[Any, ...] | None = None
    ) -> dict[str, Any] | None:
        result = await self._session.execute(sa.text(sql), _params(params))
        row = result.mappings().first()
        return dict(row) if row is not None else None


class SessionmakerExecutor:
    """Execute raw SQL with a fresh, committed session per statement."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def execute(
        self, sql: str, params: Mapping[str, Any] | tuple[Any, ...] | None = None
    ) -> None:
        async with self._sessionmaker() as session, session.begin():
            await session.execute(sa.text(sql), _params(params))

    async def fetch_all(
        self, sql: str, params: Mapping[str, Any] | tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        async with self._sessionmaker() as session:
            result = await session.execute(sa.text(sql), _params(params))
            return [dict(row) for row in result.mappings().all()]

    async def fetch_one(
        self, sql: str, params: Mapping[str, Any] | tuple[Any, ...] | None = None
    ) -> dict[str, Any] | None:
        async with self._sessionmaker() as session:
            result = await session.execute(sa.text(sql), _params(params))
            row = result.mappings().first()
            return dict(row) if row is not None else None
