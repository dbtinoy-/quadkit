"""Scenario coverage for the MySQL backend with an injected fake driver.

The real ``aiomysql`` package is installed in this environment, but the
pool/connection logic is exercised against an in-memory fake client
(injected into the module-level ``aiomysql`` references) so no database
server is required.  Covers pool creation (success, failure, retry
exhaustion), connection acquisition (plain + circuit breaker), health
checks (healthy/cached/unhealthy paths), statistics, shutdown, and the
``MySQLConnection`` query surface with error mapping and monitoring.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Self

import aiomysql
import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.exceptions.resilience import RetryExhaustedError
from quadkit.contracts.infra.resilience import RetryConfig
from quadkit.sql.backends.mysql import _connection as mysql_connection_module
from quadkit.sql.backends.mysql import _pool as mysql_pool_module
from quadkit.sql.backends.mysql._connection import MySQLConnection
from quadkit.sql.backends.mysql._pool import MySQLConnectionPool, create_mysql_pool
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    QueryError,
)

# --------------------------------------------------------------------------
# Fake driver
# --------------------------------------------------------------------------


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]], error: Exception | None) -> None:
        self._rows = rows
        self._error = error
        self.executed: list[tuple[str, Any]] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def execute(self, query: str, params: Any = None) -> None:
        self.executed.append((query, params))
        if self._error is not None:
            raise self._error

    async def executemany(self, query: str, params_list: list[tuple[Any, ...]]) -> None:
        self.executed.append((query, params_list))
        if self._error is not None:
            raise self._error

    async def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    async def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class FakeConnection:
    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
        affected: int = 1,
        close_error: Exception | None = None,
    ) -> None:
        self._rows = rows or []
        self._error = error
        self.affected_rows = affected
        self._close_error = close_error
        self.executed: list[tuple[str, Any]] = []
        self.committed = 0
        self.closed = 0
        self.cursor_cls: Any = None

    async def execute(self, query: str, params: Any = None) -> None:
        self.executed.append((query, params))
        if self._error is not None:
            raise self._error

    def cursor(self, cursor_cls: Any = None) -> FakeCursor:
        self.cursor_cls = cursor_cls
        return FakeCursor(self._rows, self._error)

    async def commit(self) -> None:
        self.committed += 1

    async def close(self) -> None:
        self.closed += 1
        if self._close_error is not None:
            raise self._close_error


class FakePool:
    def __init__(
        self,
        conn: FakeConnection | None = None,
        acquire_error: Exception | None = None,
    ) -> None:
        self._conn = conn
        self._acquire_error = acquire_error
        self.close_calls = 0
        self.wait_closed_calls = 0
        self.acquired = 0

    @asynccontextmanager
    async def acquire(self) -> Any:
        if self._acquire_error is not None:
            raise self._acquire_error
        self.acquired += 1
        yield self._conn

    def close(self) -> None:
        self.close_calls += 1

    async def wait_closed(self) -> None:
        self.wait_closed_calls += 1


class FakeAiomysqlModule:
    """Stand-in for the aiomysql module used by the backend."""

    DictCursor = aiomysql.DictCursor
    Error = aiomysql.Error

    def __init__(self) -> None:
        self.create_pool_calls: list[dict[str, Any]] = []
        self.pool: FakePool | None = None
        self.pool_error: Exception | None = None
        self.fail_first_n = 0

    async def create_pool(self, **kwargs: Any) -> FakePool:
        self.create_pool_calls.append(kwargs)
        if self.fail_first_n > 0:
            self.fail_first_n -= 1
            raise aiomysql.Error(2003, "Can't connect to MySQL server")
        return self.pool or FakePool()


class FakeQueryMonitor:
    def __init__(self) -> None:
        self.queries: list[str] = []

    @asynccontextmanager
    async def monitor_query(
        self,
        query: str,
        parameters: list[Any] | None = None,
        connection_id: str | None = None,
        transaction_id: str | None = None,
    ) -> Any:
        self.queries.append(query)
        yield


class FakeMonitor:
    def __init__(self) -> None:
        self.query_monitor = FakeQueryMonitor()
        self.start_calls = 0
        self.stop_calls = 0

    async def start_pool_monitoring(self, pool: Any) -> None:
        self.start_calls += 1

    async def stop_pool_monitoring(self) -> None:
        self.stop_calls += 1

    def get_query_monitor(self) -> FakeQueryMonitor:
        return self.query_monitor


class FakeCircuitBreaker:
    def __init__(self, open_circuit: bool = False) -> None:
        self._open = open_circuit
        self.state = "open" if open_circuit else "closed"
        self.protect_calls = 0

    @asynccontextmanager
    async def protect(self) -> Any:
        self.protect_calls += 1
        if self._open:
            msg = "circuit is open"
            raise RuntimeError(msg)
        yield

    def reset(self) -> None:
        self._open = False
        self.state = "closed"


def _install_fake(monkeypatch: pytest.MonkeyPatch, fake: FakeAiomysqlModule) -> None:
    monkeypatch.setattr(mysql_pool_module, "aiomysql", fake)
    monkeypatch.setattr(mysql_pool_module, "HAS_MYSQL", True)
    monkeypatch.setattr(mysql_connection_module, "aiomysql", fake)


def _make_pool(**overrides: Any) -> MySQLConnectionPool:
    return MySQLConnectionPool(
        host="db.test",
        port=3307,
        user="u",
        password="p",
        database="d",
        min_size=1,
        max_size=2,
        **overrides,
    )


# --------------------------------------------------------------------------
# Pool creation
# --------------------------------------------------------------------------


async def test_pool_initialize_creates_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAiomysqlModule()
    fake.pool = FakePool(FakeConnection())
    _install_fake(monkeypatch, fake)

    pool = _make_pool(ssl={"ssl": True}, timeout=7)
    await pool.initialize()

    call = fake.create_pool_calls[0]
    assert call["host"] == "db.test"
    assert call["port"] == 3307
    assert call["db"] == "d"
    assert call["minsize"] == 1
    assert call["maxsize"] == 2
    assert call["ssl"] is True  # ssl config merged into pool kwargs
    assert pool.connection_timeout == 7
    assert pool.max_connections == 2
    assert pool._pool is not None  # noqa: SLF001
    assert pool._is_healthy  # noqa: SLF001

    # second initialize is a no-op
    await pool.initialize()
    assert len(fake.create_pool_calls) == 1


async def test_pool_creation_failure_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAiomysqlModule()
    fake.pool_error = aiomysql.Error(2003, "refused")

    async def boom(**kwargs: Any) -> FakePool:
        fake.create_pool_calls.append(kwargs)
        raise aiomysql.Error(2003, "refused")

    fake.create_pool = boom  # type: ignore[method-assign]
    _install_fake(monkeypatch, fake)

    # the constructor substitutes a default RetryConfig when None —
    # speed it up with a no-op sleep
    pool = _make_pool()
    with pytest.MonkeyPatch.context() as mp:

        async def _fast_sleep(_seconds: float) -> None:
            return None

        mp.setattr(asyncio, "sleep", _fast_sleep)
        with pytest.raises(RetryExhaustedError, match="All 3 retry attempts failed"):
            await pool.initialize()
    assert pool._error_count == 3  # noqa: SLF001
    assert pool._is_healthy is False  # noqa: SLF001
    assert len(fake.create_pool_calls) == 3


async def test_pool_retry_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAiomysqlModule()
    fake.pool = FakePool(FakeConnection())
    fake.fail_first_n = 2  # first two create_pool attempts fail
    _install_fake(monkeypatch, fake)

    pool = _make_pool(
        retry_config=RetryConfig(
            max_attempts=3,
            base_delay=0,
            jitter=False,
            # _create_pool wraps driver errors in DatabaseConnectionError
            retry_on=(aiomysql.Error, DatabaseConnectionError),
        )
    )
    await pool.initialize()
    assert len(fake.create_pool_calls) == 3
    assert pool._is_healthy  # noqa: SLF001


async def test_pool_default_retry_config_retries_wrapped_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BUG #38 regression: the default RetryConfig must actually retry.

    ``_create_pool`` wraps driver failures in ``DatabaseConnectionError``;
    the default config's ``retry_on`` must include that type or the
    documented retry policy is dead code.
    """
    fake = FakeAiomysqlModule()
    fake.pool = FakePool(FakeConnection())
    fake.fail_first_n = 1
    _install_fake(monkeypatch, fake)

    pool = _make_pool()
    assert DatabaseConnectionError in tuple(pool.retry_config.retry_on)
    # default base_delay is 1.0s — patch sleep so the test stays fast
    with pytest.MonkeyPatch.context() as mp:

        async def _fast_sleep(_seconds: float) -> None:
            return None

        mp.setattr(asyncio, "sleep", _fast_sleep)
        await pool.initialize()
    assert len(fake.create_pool_calls) == 2
    assert pool._is_healthy  # noqa: SLF001


async def test_pool_retry_exhaustion_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeAiomysqlModule()
    fake.fail_first_n = 10
    _install_fake(monkeypatch, fake)

    # both attempts fail; retry_call raises RetryExhaustedError
    pool = _make_pool(
        retry_config=RetryConfig(
            max_attempts=2,
            base_delay=0,
            jitter=False,
            retry_on=(aiomysql.Error, DatabaseConnectionError),
        )
    )
    with pytest.raises(RetryExhaustedError, match="All 2 retry attempts failed"):
        await pool.initialize()
    assert len(fake.create_pool_calls) == 2
    assert pool._error_count == 2  # noqa: SLF001 — _create_pool ran per attempt


async def test_pool_factory() -> None:
    pool = create_mysql_pool(host="h2", port=3308)
    assert pool.host == "h2"
    assert pool.port == 3308


# --------------------------------------------------------------------------
# Connection acquisition
# --------------------------------------------------------------------------


async def test_get_connection_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAiomysqlModule()
    fake.pool = FakePool(FakeConnection())
    _install_fake(monkeypatch, fake)

    pool = _make_pool()
    async with pool.get_connection() as conn:
        assert isinstance(conn, MySQLConnection)
        assert conn.connection_id.startswith("mysql_")
    assert fake.pool.acquired == 1
    assert pool._connection_count == 1  # noqa: SLF001


async def test_get_connection_acquisition_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeAiomysqlModule()
    fake.pool = FakePool(acquire_error=OSError("pool dead"))
    _install_fake(monkeypatch, fake)

    pool = _make_pool()
    with pytest.raises(DatabaseConnectionError, match="Connection acquisition failed"):
        async with pool.get_connection():
            pass
    assert pool._error_count == 1  # noqa: SLF001
    assert pool._is_healthy is False  # noqa: SLF001


async def test_get_connection_circuit_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAiomysqlModule()
    fake.pool = FakePool(FakeConnection())
    _install_fake(monkeypatch, fake)

    cb = FakeCircuitBreaker()
    pool = _make_pool(circuit_breaker=cb)
    async with pool.get_connection() as conn:
        assert conn is not None
    assert cb.protect_calls == 1

    # open circuit: the breaker's rejection escapes the acquisition block
    # (the pool's except clause only covers failures inside its own
    # ``async with self._pool.acquire()`` block)
    open_cb = FakeCircuitBreaker(open_circuit=True)
    pool2 = _make_pool(circuit_breaker=open_cb)
    with pytest.raises(RuntimeError, match="circuit is open"):
        async with pool2.get_connection():
            pass
    assert open_cb.protect_calls == 1


# --------------------------------------------------------------------------
# Health checks
# --------------------------------------------------------------------------


async def test_health_check_healthy_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAiomysqlModule()
    fake.pool = FakePool(FakeConnection(affected=1))
    _install_fake(monkeypatch, fake)

    pool = _make_pool()
    await pool.initialize()  # health check requires an initialized pool
    result = await pool.health_check()
    assert result.status == HealthStatus.HEALTHY
    assert result.details["active_connections"] == 1
    assert result.details.get("cached") is None

    # second call within the 30s cache window
    cached = await pool.health_check()
    assert cached.status == HealthStatus.HEALTHY
    assert cached.details["cached"] is True


async def test_health_check_not_initialized() -> None:
    pool = _make_pool()
    result = await pool.health_check()
    assert result.status == HealthStatus.UNHEALTHY
    assert "not initialized" in result.message.lower()


async def test_health_check_failure_path(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAiomysqlModule()
    fake.pool = FakePool(
        FakeConnection(error=aiomysql.Error(1045, "access denied"), affected=0)
    )
    _install_fake(monkeypatch, fake)

    pool = _make_pool()
    result = await pool.health_check()
    assert result.status == HealthStatus.UNHEALTHY
    assert pool._is_healthy is False  # noqa: SLF001
    # connection-acquisition failures map to DatabaseConnectionError,
    # which the health checker treats as an availability issue (no
    # query-error count); the query itself never ran (affected=0)
    assert pool._error_count == 0  # noqa: SLF001


# --------------------------------------------------------------------------
# Stats / shutdown
# --------------------------------------------------------------------------


async def test_pool_stats_and_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAiomysqlModule()
    fake.pool = FakePool(FakeConnection())
    _install_fake(monkeypatch, fake)

    monitor = FakeMonitor()
    pool = _make_pool(monitor=monitor)
    # monitoring start is a background tracked task
    await asyncio.sleep(0.05)
    assert monitor.start_calls == 1

    await pool.initialize()
    stats = await pool.get_pool_stats()
    assert stats["is_initialized"] is True
    assert stats["monitoring_enabled"] is True
    assert stats["host"] == "db.test:3307"
    assert stats["pool_size"] == "1-2"
    assert await pool.get_query_stats() == {}

    await pool.shutdown()
    assert fake.pool.close_calls == 1
    assert fake.pool.wait_closed_calls == 1
    assert pool._pool is None  # noqa: SLF001
    assert monitor.stop_calls == 1

    # shutdown is idempotent
    await pool.shutdown()
    assert fake.pool.close_calls == 1


# --------------------------------------------------------------------------
# MySQLConnection query surface
# --------------------------------------------------------------------------


def _conn(
    rows: list[dict[str, Any]] | None = None,
    error: Exception | None = None,
    affected: int = 1,
    monitor: FakeMonitor | None = None,
) -> MySQLConnection:
    return MySQLConnection(
        FakeConnection(rows=rows, error=error, affected=affected), monitor
    )


async def test_connection_execute() -> None:
    conn = _conn(affected=3)
    result = await conn.execute("INSERT INTO t VALUES (1)", (1,))
    assert result == 3
    assert conn.connection_id.startswith("mysql_")

    # no-params variant
    await conn.execute("SELECT 1")


async def test_connection_execute_error_mapping() -> None:
    # driver error -> QueryError
    conn = _conn(error=aiomysql.Error(1062, "Duplicate entry"))
    with pytest.raises(QueryError, match="Query execution failed"):
        await conn.execute("INSERT INTO t VALUES (1)")

    # unexpected error also -> QueryError
    async def broken(_query: str, _params: Any = None) -> None:
        msg = "kaboom"
        raise RuntimeError(msg)

    raw = FakeConnection()
    raw.execute = broken  # type: ignore[method-assign]
    conn2 = MySQLConnection(raw)
    with pytest.raises(QueryError, match="Query execution failed"):
        await conn2.execute("SELECT 1")


async def test_connection_fetch_one_and_all() -> None:
    rows = [{"id": 1}, {"id": 2}]
    conn = _conn(rows=rows)
    row = await conn.fetch_one("SELECT * FROM t", (1,))
    assert row == {"id": 1}

    all_rows = await conn.fetch_all("SELECT * FROM t")
    assert all_rows == rows

    empty = _conn(rows=[])
    assert await empty.fetch_one("SELECT 1") is None
    assert await empty.fetch_all("SELECT 1") == []


async def test_connection_fetch_error_mapping() -> None:
    err = aiomysql.Error(1146, "Table doesn't exist")
    with pytest.raises(QueryError, match="Query fetch failed"):
        await _conn(error=err).fetch_one("SELECT * FROM missing")
    with pytest.raises(QueryError, match="Query fetch all failed"):
        await _conn(error=err).fetch_all("SELECT * FROM missing")


async def test_connection_execute_many() -> None:
    conn = _conn()
    await conn.execute_many("INSERT INTO t VALUES (%s)", [(1,), (2,)])
    raw: FakeConnection = conn._conn  # noqa: SLF001
    assert raw.committed == 1

    with pytest.raises(QueryError, match="Batch execution failed"):
        await _conn(error=aiomysql.Error(1062, "dup")).execute_many(
            "INSERT INTO t VALUES (%s)", [(1,)]
        )


async def test_connection_monitoring_paths() -> None:
    monitor = FakeMonitor()
    conn = _conn(rows=[{"id": 1}], monitor=monitor)
    await conn.execute("SELECT 1", (1,))
    await conn.fetch_one("SELECT * FROM t")
    await conn.fetch_all("SELECT * FROM t")
    assert monitor.query_monitor.queries == [
        "SELECT 1",
        "SELECT * FROM t",
        "SELECT * FROM t",
    ]


async def test_connection_transaction_and_close() -> None:
    conn = _conn()
    async with conn.transaction() as tx:
        assert tx is conn

    raw: FakeConnection = conn._conn  # noqa: SLF001
    await conn.close()
    assert raw.closed == 1

    # close error is swallowed (best-effort)
    bad = FakeConnection(close_error=OSError("gone"))
    await MySQLConnection(bad).close()
    assert bad.closed == 1

    # sync close also supported
    closed_sync = 0

    class SyncClose:
        def close(self) -> None:
            nonlocal closed_sync
            closed_sync += 1

    await MySQLConnection(SyncClose()).close()
    assert closed_sync == 1
