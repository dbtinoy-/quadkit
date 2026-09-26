"""Regression tests for the connection-lifecycle defects found in the R88 sweep.

Two documented bugs were deferred to quadkit-sql:

1. **MRO-stub contract breach** — :class:`DatabaseDriver` subclasses
   ``DatabaseProviderProtocol`` but never implements ``get_connection`` /
   ``get_unit_of_work``.  The inherited Protocol bodies are ``...`` stubs
   that return ``None``, so ``async with driver.get_connection()`` raises
   ``TypeError`` and ``driver.get_unit_of_work()`` is ``None`` (which the DI
   registration happily binds as a UoW factory).
2. **Pool-slot leak → pool exhaustion** — ``DatabaseManager.get_connection``
   called outside a scoped context acquires a pool connection context
   manager but never stores it (no active context dict), so the slot is
   never released.  Repeated out-of-scope use exhausts the pool and every
   subsequent acquire stalls (the "deadlock").

These tests pin the corrected behaviour.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import pytest

from quadkit.sql.providers.database_service import DatabaseService

from quadkit.sql.providers.connection_manager import ConnectionManager

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _CountingPool:
    """Minimal pool double that tracks live (acquired) slots."""

    def __init__(self, size: int = 2) -> None:
        self._size = size
        self._available = size
        self._initialized = True
        self.peak_active = 0
        self.exhausted = False

    @property
    def active(self) -> int:
        return self._size - self._available

    async def initialize(self) -> None:
        self._initialized = True

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Any, None]:
        if self._available <= 0:
            self.exhausted = True
            raise RuntimeError("pool exhausted")
        self._available -= 1
        self.peak_active = max(self.peak_active, self.active)
        try:
            yield _FakeConnection()
        finally:
            self._available += 1

    async def return_connection(self, connection: Any) -> None:
        pass


class _FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    async def execute(self, sql: str, params: Any = None) -> Any:
        return None

    async def close(self) -> None:
        self.closed = True


class _BareDriver:
    """Driver double with *no* connection_manager (forces the pool path)."""

    database_type = "sqlite"

    async def is_connected(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# 1. MRO-stub contract breach (DatabaseDriver)
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_driver() -> Any:
    from quadkit.sql.providers.sqlite_provider import SQLiteProvider

    return SQLiteProvider(":memory:")


async def test_driver_get_connection_yields_usable_connection(
    sqlite_driver: Any,
) -> None:
    """``async with driver.get_connection()`` must satisfy the protocol.

    Before the fix this resolved to the Protocol's ``...`` stub, which
    returns ``None`` → ``TypeError: 'NoneType' object does not support the
    asynchronous context manager protocol``.
    """
    async with sqlite_driver.get_connection() as conn:
        result = await conn.execute("SELECT 1")
    assert result is not None


async def test_driver_get_unit_of_work_returns_working_uow(
    sqlite_driver: Any,
) -> None:
    """``driver.get_unit_of_work()`` must return a usable UoW, not ``None``.

    The DI registration binds ``driver.get_unit_of_work`` as the scoped
    UoW factory — a ``None``-returning stub corrupts every UoW resolution.
    """
    uow = sqlite_driver.get_unit_of_work()
    assert uow is not None

    async with uow:
        pass
    await uow.commit()  # must not raise even without an open transaction


async def test_driver_uow_commit_and_rollback_roundtrip(sqlite_driver: Any) -> None:
    uow = sqlite_driver.get_unit_of_work()
    async with uow:
        pass
    await uow.commit()
    assert uow._committed  # noqa: SLF001 — whitebox: lifecycle flag set

    # Drivers have no request scope, so the UoW context manager does not
    # auto-commit/rollback (that is scope-driven); explicit calls work.
    uow2 = sqlite_driver.get_unit_of_work()
    with pytest.raises(ValueError):
        async with uow2:
            raise ValueError("boom")
    await uow2.rollback()
    assert uow2._rolled_back  # noqa: SLF001 — explicit rollback path


# ---------------------------------------------------------------------------
# 2. Pool-slot leak outside a scoped context
# ---------------------------------------------------------------------------


def _make_service(pool: _CountingPool) -> Any:
    from quadkit.sql.providers.database_service import DatabaseService

    svc = DatabaseService("sqlite:///:memory:", connection_pool=pool)
    svc.db_provider = _BareDriver()  # no connection_manager → pool path
    svc._started = True  # noqa: SLF001 — skip boot; exercise the CM path only
    return svc


async def test_service_get_connection_out_of_scope_releases_slot() -> None:
    """Out-of-scope ``get_connection`` must release the pool slot on exit.

    Before the fix the manager path entered the pool's context manager
    without storing it (no active context), so the slot stayed acquired
    forever — one call per pool slot and the pool is exhausted.
    """
    pool = _CountingPool(size=2)
    svc = _make_service(pool)

    async with svc.get_connection() as conn:
        assert isinstance(conn, _FakeConnection)
        assert pool.active == 1
    assert pool.active == 0

    # A second acquisition must work immediately (no leaked slot).
    async with svc.get_connection():
        pass
    assert pool.active == 0
    assert pool.exhausted is False


async def test_repeated_out_of_scope_use_does_not_exhaust_pool() -> None:
    """The exhaustion scenario: N sequential out-of-scope borrows.

    With the leak, a size-1 pool exhausts after the first borrow and every
    later acquire raised/stalled.  After the fix the slot is returned each
    time.
    """
    pool = _CountingPool(size=1)
    svc = _make_service(pool)

    for _ in range(5):
        async with svc.get_connection():
            assert pool.active == 1
    assert pool.active == 0
    assert pool.exhausted is False


async def test_acquire_release_returns_pool_slot() -> None:
    """``acquire()``/``release()`` is the manual-management API — release
    must actually free the pool slot (it was a no-op before)."""
    pool = _CountingPool(size=1)
    svc = _make_service(pool)

    conn = await svc.acquire()
    assert pool.active == 1
    await svc.release(conn)
    assert pool.active == 0

    # Re-acquire works after release.
    conn2 = await svc.acquire()
    assert conn2 is not None
    await svc.release(conn2)
    assert pool.active == 0


async def test_scoped_context_still_reuses_and_releases() -> None:
    """In-scope usage keeps working: scoped borrows, scope exit releases."""
    pool = _CountingPool(size=2)
    svc = _make_service(pool)

    async with svc.scoped_context():
        conn = await svc.get_scoped_connection()
        assert isinstance(conn, _FakeConnection)
        assert pool.active == 1
        # Second scoped borrow reuses the same slot.
        again = await svc.get_scoped_connection()
        assert again is conn
        assert pool.active == 1
    assert pool.active == 0


class _CountingConnectionManager(ConnectionManager):
    """Connection manager whose connection creation is counted."""

    def __init__(self) -> None:
        super().__init__("sqlite:///:memory:")
        self.created = 0
        self.closed: list[Any] = []

    async def _create_connection(self) -> Any:
        self.created += 1
        return object()

    async def _close_connection(self, connection: Any) -> None:
        self.closed.append(connection)


async def test_a_boot_in_flight_does_not_replace_the_schema() -> None:
    """The store that creates a table while boot is still connecting keeps it.

    This is the shape the demo suite hit: the audit store's first write boots
    the service lazily while the database provider is booting the same
    service, so the write opens the connection and creates the schema —
    and the boot that finishes afterwards must not replace that connection
    with a second, empty one.
    """
    service = DatabaseService("sqlite+aiosqlite:///:memory:")
    gate = asyncio.Event()
    creating = service._create_driver_provider  # type: ignore[attr-defined]

    def gated_provider() -> Any:
        driver = creating()

        async def connect() -> None:
            await gate.wait()
            await original_connect()

        original_connect = driver.connect
        driver.connect = connect
        return driver

    service._create_driver_provider = gated_provider  # type: ignore[method-assign]

    booting = asyncio.create_task(service.boot())
    await asyncio.sleep(0)

    await service.execute(
        "CREATE TABLE audit_log (id INTEGER PRIMARY KEY, checksum TEXT)"
    )
    gate.set()
    await booting

    rows = await service.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
    )
    assert [row["name"] for row in rows.rows] == ["audit_log"]

    await service.disconnect()


async def test_connecting_twice_keeps_the_first_connection() -> None:
    """A second ``connect()`` must not open — and start from — a fresh handle.

    An in-memory SQLite database belongs to its connection: everything
    created through it is gone the moment the handle is replaced.  A second
    connect used to overwrite ``_connection`` unconditionally, so a store
    that had created its table on the first connection read "no such table"
    through the second one.
    """
    manager = _CountingConnectionManager()

    await manager.connect()
    first = manager._connection
    await manager.connect()

    assert manager.created == 1
    assert manager._connection is first

    await manager.disconnect()
    await manager.connect()

    assert manager.created == 2
    assert manager._connection is not first
