"""Tests for :class:`quadkit.sql.orm.SessionFactory`.

Closes Improve-QuadKit gap #1: applications mapping declarative models had
no way to obtain a SQLAlchemy engine from the framework, so each built its
own against the same URL and ran two independent pools.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from quadkit.sql.orm import SessionFactory


class Base(DeclarativeBase):
    """Isolated metadata so these tests cannot collide with other suites."""


class Widget(Base):
    __tablename__ = "orm_factory_widget"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(50))


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'factory.db'}"


@pytest.fixture
async def factory(db_url: str) -> AsyncIterator[SessionFactory]:
    created = SessionFactory(db_url)
    async with created.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield created
    await created.dispose()


async def test_exposes_an_async_engine(factory: SessionFactory) -> None:
    """The gap this closes: applications need the engine itself."""
    assert isinstance(factory.engine, AsyncEngine)
    assert factory.engine.dialect.name == "sqlite"


async def test_session_scope_reads_and_writes(factory: SessionFactory) -> None:
    async with factory.begin() as session:
        session.add(Widget(name="sprocket"))

    async with factory.session() as session:
        names = (await session.execute(sa.select(Widget.name))).scalars().all()
    assert list(names) == ["sprocket"]


async def test_begin_commits_on_success(factory: SessionFactory) -> None:
    async with factory.begin() as session:
        session.add(Widget(name="committed"))

    async with factory.session() as session:
        assert await session.scalar(sa.select(sa.func.count()).select_from(Widget)) == 1


async def _fail_mid_transaction(factory: SessionFactory) -> None:
    async with factory.begin() as session:
        session.add(Widget(name="doomed"))
        await session.flush()
        raise RuntimeError("boom")


async def test_begin_rolls_back_on_error(factory: SessionFactory) -> None:
    """A failed unit of work must leave nothing behind."""
    with pytest.raises(RuntimeError, match="boom"):
        await _fail_mid_transaction(factory)

    async with factory.session() as session:
        assert await session.scalar(sa.select(sa.func.count()).select_from(Widget)) == 0


async def test_attributes_remain_readable_after_commit(factory: SessionFactory) -> None:
    """``expire_on_commit=False`` by default.

    The alternative is a lazy refresh after commit, which in async code
    surfaces as a ``MissingGreenlet`` far from its cause.
    """
    async with factory.begin() as session:
        widget = Widget(name="readable")
        session.add(widget)
        await session.flush()
    assert widget.name == "readable"


async def test_is_callable_as_a_sessionmaker(factory: SessionFactory) -> None:
    """Drop-in where code already expects ``async_sessionmaker``."""
    session = factory()
    assert isinstance(session, AsyncSession)
    await session.close()


async def test_sqlite_pragmas_are_applied(factory: SessionFactory) -> None:
    """SQLite engines get the same policy the raw providers apply.

    ``busy_timeout`` is the part that matters: without it a second
    connection fails instantly with "database is locked" the moment the
    first holds a write.
    """
    async with factory.session() as session:
        journal = await session.scalar(sa.text("PRAGMA journal_mode"))
        busy = await session.scalar(sa.text("PRAGMA busy_timeout"))
    assert str(journal).upper() == "TRUNCATE"
    assert int(busy) > 0


async def test_journal_mode_is_configurable(tmp_path: Path) -> None:
    """WAL needs ``-wal``/``-shm`` sidecars that some filesystems refuse,
    so the default is conservative and the choice is the caller's."""
    created = SessionFactory(
        f"sqlite+aiosqlite:///{tmp_path / 'delete.db'}", sqlite_journal_mode="DELETE"
    )
    async with created.session() as session:
        assert (
            str(await session.scalar(sa.text("PRAGMA journal_mode"))).upper()
            == "DELETE"
        )
    await created.dispose()


async def test_sqlite_ignores_pool_sizing(tmp_path: Path) -> None:
    """SQLAlchemy rejects pool arguments for SQLite; passing them must not
    explode just because a caller used one config for both dialects."""
    created = SessionFactory(
        f"sqlite+aiosqlite:///{tmp_path / 'pool.db'}", pool_size=20, max_overflow=40
    )
    async with created.session() as session:
        assert await session.scalar(sa.text("SELECT 1")) == 1
    await created.dispose()


async def test_dispose_closes_the_pool(db_url: str) -> None:
    created = SessionFactory(db_url)
    async with created.session() as session:
        await session.execute(sa.text("SELECT 1"))
    await created.dispose()
    # Disposing twice is harmless; shutdown paths should not need to guard.
    await created.dispose()


async def test_one_factory_means_one_engine(factory: SessionFactory) -> None:
    """The whole point: not two pools against one database."""
    assert factory.session is not None
    assert factory.sessionmaker.kw["bind"] is factory.engine
