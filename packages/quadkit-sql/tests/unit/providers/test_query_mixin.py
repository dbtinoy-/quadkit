"""Tests for _QueryMixin: execute_query/insert/update/delete, raw execute
routing, and raw-result normalisation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.data.sql.database import (
    DeleteResult,
    InsertResult,
    QueryResult,
    UpdateResult,
)
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DuplicateKeyError,
    QueryError,
)
from quadkit.sql.providers._query_mixin import _QueryMixin


class _Host(_QueryMixin):
    def __init__(self, db_provider: Any = None, **attrs: Any) -> None:
        self.db_provider = db_provider
        self._pipeline = None
        self.resilience_handler = None
        self.config = None
        self.tracer = attrs.pop("tracer", None)
        self.metrics = attrs.pop("metrics", None)
        self._started = False
        for k, v in attrs.items():
            setattr(self, k, v)

    async def boot(self, container: Any | None = None) -> None:
        self._started = True

    def _ensure_resilience_pipeline(self) -> Any:
        return None


def _qr(rows: list[dict[str, Any]] | None = None) -> QueryResult:
    rows = rows if rows is not None else []
    return QueryResult(rows=rows, row_count=len(rows), execution_time=1.0, success=True)


class TestToQueryResult:
    def test_queryresult_passthrough(self) -> None:
        original = _qr([{"a": 1}])
        out = _QueryMixin._to_query_result(original, 5.0)
        assert out is original

    def test_list_of_dicts(self) -> None:
        out = _QueryMixin._to_query_result([{"a": 1}, {"a": 2}], 5.0)
        assert out.rows == [{"a": 1}, {"a": 2}]
        assert out.row_count == 2
        assert out.success is True

    def test_list_of_record_objects(self) -> None:
        class _Row:
            def __init__(self, a: int) -> None:
                self.a = a

            def _asdict(self) -> dict[str, Any]:
                return {"a": self.a}

            def __iter__(self):
                return iter(("a",))

            def keys(self):
                return ["a"]

            def __getitem__(self, k: str) -> Any:
                return {"a": self.a}[k]

        raw = _Row(3)
        # dict(raw) uses keys() + __getitem__ for mapping-like objects.
        out = _QueryMixin._to_query_result([raw], 2.0)
        assert out.row_count == 1

    def test_object_with_rows_attr(self) -> None:
        class _Raw:
            rows = [{"x": 1}, {"x": 2}]

        out = _QueryMixin._to_query_result(_Raw(), 3.0)
        assert out.rows == [{"x": 1}, {"x": 2}]
        assert out.row_count == 2

    def test_unknown_shape_empty_success(self) -> None:
        out = _QueryMixin._to_query_result(42, 1.0)
        assert out.rows == []
        assert out.row_count == 0
        assert out.success is True


class TestExecuteQuery:
    async def test_delegates_and_returns_result(self) -> None:
        provider = AsyncMock()
        provider.execute_query = AsyncMock(return_value=_qr([{"id": 1}]))
        host = _Host(db_provider=provider)
        res = await host.execute_query("SELECT 1", [1])
        assert res.rows == [{"id": 1}]
        provider.execute_query.assert_awaited_once_with("SELECT 1", [1])

    async def test_boots_when_no_provider(self) -> None:
        # Set the provider AFTER construction so the mixin's boot path
        # (if it ran) would be observable — here the provider is present
        # when execute_query checks, so no boot is needed.  Verify the
        # no-boot path with a provider and the boot path separately.
        host = _Host()
        host.db_provider = AsyncMock()
        host.db_provider.execute_query = AsyncMock(return_value=_qr())
        res = await host.execute_query("SELECT 1")
        assert res.success is True

    async def test_boot_called_when_no_provider(self) -> None:
        host = _Host()
        booted = []

        async def fake_boot(container: Any | None = None) -> None:
            booted.append(True)
            host._started = True
            host.db_provider = AsyncMock()
            host.db_provider.execute_query = AsyncMock(return_value=_qr())

        host.boot = fake_boot  # type: ignore[method-assign]
        await host.execute_query("SELECT 1")
        assert booted == [True]
        assert host._started is True

    async def test_error_reraised(self) -> None:
        provider = AsyncMock()
        provider.execute_query = AsyncMock(side_effect=QueryError("boom"))
        host = _Host(db_provider=provider)
        with pytest.raises(QueryError, match="boom"):
            await host.execute_query("SELECT 1")

    async def test_metrics_recorded_on_success(self) -> None:
        provider = AsyncMock()
        provider.execute_query = AsyncMock(return_value=_qr())
        metrics = AsyncMock()
        host = _Host(db_provider=provider, metrics=metrics)
        await host.execute_query("SELECT 1")
        metrics.histogram.assert_awaited()
        assert metrics.histogram.call_args.args[0] == "db.query.latency"
        metrics.counter.assert_awaited()

    async def test_metrics_error_counted_on_failure(self) -> None:
        provider = AsyncMock()
        provider.execute_query = AsyncMock(side_effect=QueryError("boom"))
        metrics = AsyncMock()
        host = _Host(db_provider=provider, metrics=metrics)
        with pytest.raises(QueryError):
            await host.execute_query("SELECT 1")
        calls = {c.args[0] for c in metrics.counter.await_args_list}
        assert "db.query.errors" in calls

    async def test_metrics_failure_never_breaks_query(self) -> None:
        provider = AsyncMock()
        provider.execute_query = AsyncMock(return_value=_qr())
        metrics = AsyncMock()
        metrics.histogram.side_effect = RuntimeError("metrics down")
        host = _Host(db_provider=provider, metrics=metrics)
        res = await host.execute_query("SELECT 1")  # must not raise
        assert res.success is True

    async def test_with_tracer_span(self) -> None:
        provider = AsyncMock()
        provider.execute_query = AsyncMock(return_value=_qr([{"a": 1}]))

        class _Span:
            def __enter__(self) -> Any:
                return self

            def __exit__(self, *a: Any) -> bool:
                return False

        class _Tracer:
            def start_span(self, name: str) -> _Span:
                _Tracer.last_span = name
                return _Span()

            last_span: str | None = None

        tracer = _Tracer()
        host = _Host(db_provider=provider, tracer=tracer)
        res = await host.execute_query("SELECT 1")
        assert res.rows == [{"a": 1}]
        assert tracer.last_span == "db.database"


class TestExecuteInsert:
    async def test_success_passthrough(self) -> None:
        provider = AsyncMock()
        expected = InsertResult(
            inserted_id=7, affected_rows=1, execution_time=0.5, success=True
        )
        provider.execute_insert = AsyncMock(return_value=expected)
        host = _Host(db_provider=provider)
        res = await host.execute_insert("users", {"name": "a"})
        assert res is expected
        provider.execute_insert.assert_awaited_once_with("users", {"name": "a"})

    async def test_query_error_converted_to_failed_result(self) -> None:
        provider = AsyncMock()
        provider.execute_insert = AsyncMock(
            side_effect=QueryError("constraint violated")
        )
        host = _Host(db_provider=provider)
        res = await host.execute_insert("users", {"name": "a"})
        assert res.success is False
        assert res.inserted_id is None
        assert "constraint violated" in (res.error_message or "")

    async def test_duplicate_key_propagates(self) -> None:
        provider = AsyncMock()
        provider.execute_insert = AsyncMock(side_effect=DuplicateKeyError("dup"))
        host = _Host(db_provider=provider)
        with pytest.raises(DuplicateKeyError):
            await host.execute_insert("users", {"name": "a"})

    async def test_connection_error_propagates(self) -> None:
        provider = AsyncMock()
        provider.execute_insert = AsyncMock(
            side_effect=DatabaseConnectionError("down")
        )
        host = _Host(db_provider=provider)
        with pytest.raises(DatabaseConnectionError):
            await host.execute_insert("users", {"name": "a"})


class TestExecuteUpdate:
    async def test_success_passthrough(self) -> None:
        provider = AsyncMock()
        expected = UpdateResult(affected_rows=2, execution_time=0.1, success=True)
        provider.execute_update = AsyncMock(return_value=expected)
        host = _Host(db_provider=provider)
        res = await host.execute_update("users", {"name": "b"}, '"id" = ?', [1])
        assert res is expected

    async def test_query_error_converted(self) -> None:
        provider = AsyncMock()
        provider.execute_update = AsyncMock(side_effect=QueryError("bad where"))
        host = _Host(db_provider=provider)
        res = await host.execute_update("users", {}, '"id" = ?', [1])
        assert res.success is False
        assert "bad where" in (res.error_message or "")

    async def test_connection_error_propagates(self) -> None:
        provider = AsyncMock()
        provider.execute_update = AsyncMock(
            side_effect=DatabaseConnectionError("down")
        )
        host = _Host(db_provider=provider)
        with pytest.raises(DatabaseConnectionError):
            await host.execute_update("users", {}, "x")


class TestExecuteDelete:
    async def test_success_passthrough(self) -> None:
        provider = AsyncMock()
        expected = DeleteResult(affected_rows=1, execution_time=0.1, success=True)
        provider.execute_delete = AsyncMock(return_value=expected)
        host = _Host(db_provider=provider)
        res = await host.execute_delete("users", '"id" = ?', [3])
        assert res is expected

    async def test_query_error_converted(self) -> None:
        provider = AsyncMock()
        provider.execute_delete = AsyncMock(side_effect=QueryError("locked"))
        host = _Host(db_provider=provider)
        res = await host.execute_delete("users", "x")
        assert res.success is False
        assert "locked" in (res.error_message or "")


class TestExecuteRaw:
    async def test_select_routed_to_query(self) -> None:
        provider = AsyncMock()
        provider.execute_query = AsyncMock(return_value=_qr([{"a": 1}]))
        provider.execute = AsyncMock(return_value=_qr())
        host = _Host(db_provider=provider)
        res = await host.execute("SELECT * FROM users")
        assert res.rows == [{"a": 1}]
        provider.execute_query.assert_awaited_once()
        provider.execute.assert_not_awaited()

    async def test_returning_routed_to_query(self) -> None:
        provider = AsyncMock()
        provider.execute_query = AsyncMock(return_value=_qr())
        provider.execute = AsyncMock(return_value=_qr())
        host = _Host(db_provider=provider)
        await host.execute("INSERT INTO t (a) VALUES (1) RETURNING id")
        provider.execute_query.assert_awaited_once()

    async def test_write_routed_to_driver_execute(self) -> None:
        provider = AsyncMock()
        provider.execute_query = AsyncMock(return_value=_qr())
        provider.execute = AsyncMock(return_value=_qr([{"id": 9}]))
        host = _Host(db_provider=provider)
        res = await host.execute("INSERT INTO t (a) VALUES (1)", [1])
        provider.execute.assert_awaited_once_with(
            "INSERT INTO t (a) VALUES (1)", [1]
        )
        provider.execute_query.assert_not_awaited()
        assert res.rows == [{"id": 9}]

    async def test_update_delete_are_writes(self) -> None:
        provider = AsyncMock()
        provider.execute = AsyncMock(return_value=_qr())
        provider.execute_query = AsyncMock(return_value=_qr())
        host = _Host(db_provider=provider)
        await host.execute("UPDATE t SET a=1")
        await host.execute("DELETE FROM t")
        assert provider.execute.await_count == 2
        provider.execute_query.assert_not_awaited()

    async def test_error_returns_failed_result(self) -> None:
        provider = AsyncMock()
        provider.execute = AsyncMock(side_effect=QueryError("syntax"))
        host = _Host(db_provider=provider)
        res = await host.execute("INSERT INTO t VALUES (1)")
        assert res.success is False
        assert "syntax" in (res.error_message or "")

    async def test_read_error_returns_failed_result(self) -> None:
        provider = AsyncMock()
        provider.execute_query = AsyncMock(side_effect=QueryError("no table"))
        host = _Host(db_provider=provider)
        res = await host.execute("SELECT * FROM missing")
        assert res.success is False
        assert "no table" in (res.error_message or "")
