"""Tests for PostgresConnection (driver wrapper: error mapping, dicts, monitoring)."""

from __future__ import annotations

import pytest

from quadkit.sql.backends._postgres_connection import (
    HAS_MONITORING,
    PostgresConnection,
)
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseTimeoutError,
    QueryError,
)


def _pg_error() -> type[Exception]:
    """Return the asyncpg PostgresError class the module bound at import."""
    from quadkit.sql.backends import _postgres_connection as m

    return m.PostgresError


class _DriverConn:
    """Scripted asyncpg-like connection."""

    def __init__(self, results: dict | None = None) -> None:
        self.results = results or {}
        self.calls: list[tuple[str, tuple]] = []
        self.closed = 0
        self._txn_active = False

    async def execute(self, query: str, *params: object) -> str:
        self.calls.append(("execute", params))
        value = self.results.get(("execute", query))
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, str) else "OK 1"

    async def fetchrow(self, query: str, *params: object) -> dict | None:
        self.calls.append(("fetchrow", params))
        value = self.results.get(("fetchrow", query))
        if isinstance(value, Exception):
            raise value
        return value

    async def fetch(self, query: str, *params: object) -> list[dict]:
        self.calls.append(("fetch", params))
        value = self.results.get(("fetch", query))
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, list) else []

    async def close(self) -> None:
        self.closed += 1

    def transaction(self):
        import contextlib

        @contextlib.asynccontextmanager
        async def _txn():
            self._txn_active = True
            try:
                yield
            finally:
                self._txn_active = False

        return _txn()


def _conn() -> tuple[PostgresConnection, _DriverConn]:
    return _conn_results({})


def _conn_results(results: dict) -> tuple[PostgresConnection, _DriverConn]:
    driver = _DriverConn(results)
    return PostgresConnection(driver), driver


class TestExecute:
    async def test_returns_driver_tag(self) -> None:
        pc, driver = _conn_results({("execute", "DELETE FROM t"): "DELETE 3"})
        result = await pc.execute("DELETE FROM t")
        assert result == "DELETE 3"
        assert driver.calls == [("execute", ())]

    async def test_params_fanned_out(self) -> None:
        pc, driver = _conn()
        await pc.execute("SELECT $1, $2", (1, "x"))
        assert driver.calls == [("execute", (1, "x"))]

    async def test_postgres_error_becomes_query_error(self) -> None:
        boom = _pg_error()("syntax error")
        pc, _ = _conn_results({("execute", "BROKEN"): boom})
        with pytest.raises(QueryError, match="Query execution failed"):
            await pc.execute("BROKEN")

    async def test_generic_error_becomes_connection_error(self) -> None:
        pc, _ = _conn_results({("execute", "X"): OSError("socket gone")})
        with pytest.raises(DatabaseConnectionError, match="Connection error"):
            await pc.execute("X")

    async def test_timeout_maps_to_connection_error(self) -> None:
        pc, _ = _conn_results({("execute", "X"): DatabaseTimeoutError("slow")})
        with pytest.raises(DatabaseConnectionError, match="Connection error"):
            await pc.execute("X")


class TestFetchOne:
    async def test_row_to_dict(self) -> None:
        pc, _ = _conn_results({("fetchrow", "SELECT 1"): {"id": 1}})
        assert await pc.fetch_one("SELECT 1") == {"id": 1}

    async def test_params(self) -> None:
        pc, driver = _conn_results({("fetchrow", "Q"): {"id": 9}})
        await pc.fetch_one("Q", (42,))
        assert driver.calls == [("fetchrow", (42,))]

    async def test_missing_row_none(self) -> None:
        pc, _ = _conn()
        assert await pc.fetch_one("SELECT 1") is None

    async def test_postgres_error_becomes_query_error(self) -> None:
        pc, _ = _conn_results({("fetchrow", "B"): _pg_error()("bad query")})
        with pytest.raises(QueryError, match="Query fetch failed"):
            await pc.fetch_one("B")

    async def test_generic_error_becomes_query_error(self) -> None:
        pc, _ = _conn_results({("fetchrow", "B"): OSError("down")})
        with pytest.raises(QueryError, match="Unexpected Postgres error"):
            await pc.fetch_one("B")


class TestFetchAll:
    async def test_rows_to_dicts(self) -> None:
        pc, _ = _conn_results({("fetch", "SELECT *"): [{"a": 1}, {"a": 2}]})
        assert await pc.fetch_all("SELECT *") == [{"a": 1}, {"a": 2}]

    async def test_empty(self) -> None:
        pc, _ = _conn()
        assert await pc.fetch_all("SELECT *") == []

    async def test_params(self) -> None:
        pc, driver = _conn_results({("fetch", "Q"): []})
        await pc.fetch_all("Q", (7,))
        assert driver.calls == [("fetch", (7,))]

    async def test_postgres_error_becomes_query_error(self) -> None:
        pc, _ = _conn_results({("fetch", "B"): _pg_error()("boom")})
        with pytest.raises(QueryError, match="Query fetch all failed"):
            await pc.fetch_all("B")

    async def test_generic_error_becomes_query_error(self) -> None:
        pc, _ = _conn_results({("fetch", "B"): RuntimeError("x")})
        with pytest.raises(QueryError, match="Query fetch all failed"):
            await pc.fetch_all("B")


class TestExecuteMany:
    async def test_runs_all_in_transaction(self) -> None:
        pc, driver = _conn()
        await pc.execute_many("INSERT INTO t VALUES ($1)", [(1,), (2,)])
        assert driver.calls == [("execute", (1,)), ("execute", (2,))]

    async def test_empty_list_noop(self) -> None:
        pc, driver = _conn()
        await pc.execute_many("INSERT INTO t VALUES ($1)", [])
        assert driver.calls == []

    async def test_postgres_error_becomes_query_error(self) -> None:
        pc, _ = _conn_results({("execute", "Q"): _pg_error()("violates")})
        with pytest.raises(QueryError, match="Batch execution failed"):
            await pc.execute_many("Q", [(1,)])

    async def test_generic_error_becomes_query_error(self) -> None:
        pc, _ = _conn_results({("execute", "Q"): ConnectionError("lost")})
        with pytest.raises(QueryError, match="Batch execution failed"):
            await pc.execute_many("Q", [(1,)])


class TestClose:
    async def test_async_close(self) -> None:
        pc, driver = _conn()
        await pc.close()
        assert driver.closed == 1

    async def test_sync_close(self) -> None:
        calls = {"n": 0}

        class _SyncConn:
            def close(self) -> None:
                calls["n"] += 1

        pc = PostgresConnection(_SyncConn())
        await pc.close()
        assert calls["n"] == 1

    async def test_close_without_method(self) -> None:
        pc = PostgresConnection(object())
        await pc.close()  # must not raise

    async def test_close_swallows_os_errors(self) -> None:
        class _Broken:
            async def close(self) -> None:
                raise OSError("already closed")

        pc = PostgresConnection(_Broken())
        await pc.close()  # must not raise


class TestTransaction:
    async def test_yields_self(self) -> None:
        pc, _ = _conn()
        async with pc.transaction() as conn:
            assert conn is pc

    async def test_yields_even_on_error(self) -> None:
        pc, _ = _conn()
        with pytest.raises(RuntimeError, match="body"):
            async with pc.transaction():
                raise RuntimeError("body")


class TestMonitoring:
    @pytest.mark.skipif(not HAS_MONITORING, reason="monitoring module unavailable")
    async def test_monitor_wraps_query(self) -> None:
        import contextlib

        events: list[dict] = []

        @contextlib.asynccontextmanager
        async def monitor_query(*, query, parameters, connection_id):  # noqa: ARG001
            events.append(
                {
                    "query": query,
                    "parameters": parameters,
                    "connection_id": connection_id,
                },
            )
            yield

        class _QM:
            pass

        qm = _QM()
        qm.monitor_query = monitor_query

        class _Mon:
            def get_query_monitor(self):
                return qm

        pc, driver = _conn()
        pc.monitor = _Mon()
        await pc.execute("SELECT 1", (5,))
        assert driver.calls == [("execute", (5,))]
        assert events == [
            {
                "query": "SELECT 1",
                "parameters": [5],
                "connection_id": pc.connection_id,
            },
        ]

    @pytest.mark.skipif(not HAS_MONITORING, reason="monitoring module unavailable")
    async def test_monitor_fetch_all(self) -> None:
        import contextlib

        events: list[str] = []

        @contextlib.asynccontextmanager
        async def monitor_query(*, query, parameters, connection_id):  # noqa: ARG001
            events.append(query)
            yield

        class _QM:
            pass

        qm = _QM()
        qm.monitor_query = monitor_query

        class _Mon:
            def get_query_monitor(self):
                return qm

        pc, _ = _conn_results({("fetch", "Q"): []})
        pc.monitor = _Mon()
        await pc.fetch_all("Q")
        assert events == ["Q"]


class TestIdentity:
    def test_connection_id_shape(self) -> None:
        pc, _ = _conn()
        assert pc.connection_id.startswith("postgres_")
        assert len(pc.connection_id) > len("postgres_")

    def test_is_database_connection(self) -> None:
        from quadkit.sql.abstractions.connection import DatabaseConnection

        pc, _ = _conn()
        assert isinstance(pc, DatabaseConnection)

