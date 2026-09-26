"""Unit tests for the query middleware pipeline and built-ins."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.sql.exceptions import QueryError
from quadkit.sql.middleware.base import QueryMiddleware
from quadkit.sql.middleware.builtins import (
    QueryAuditLogger,
    QueryMetricsCollector,
    SlowQueryLogger,
)
from quadkit.sql.middleware.models import QueryContext
from quadkit.sql.middleware.pipeline import QueryMiddlewarePipeline


class _RecordingMiddleware(QueryMiddleware):
    def __init__(self, name: str, order: list[str]) -> None:
        self.name = name
        self.order = order
        self.ctxs: list[QueryContext] = []

    async def before_query(self, ctx: QueryContext) -> None:
        self.order.append(f"before:{self.name}")
        self.ctxs.append(ctx)

    async def after_query(self, ctx: QueryContext) -> None:
        self.order.append(f"after:{self.name}")
        self.ctxs.append(ctx)


class _FailingAfterMiddleware(QueryMiddleware):
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def after_query(self, ctx: QueryContext) -> None:
        raise self.exc


class TestQueryMiddlewarePipeline:
    @pytest.mark.asyncio
    async def test_executes_without_middleware(self) -> None:
        pipeline = QueryMiddlewarePipeline()

        async def fn(sql: str, params: Any) -> str:
            return f"{sql} {params}"

        assert await pipeline.execute("SELECT 1", (42,), fn) == "SELECT 1 (42,)"

    @pytest.mark.asyncio
    async def test_before_in_order_after_in_reverse(self) -> None:
        order: list[str] = []
        first = _RecordingMiddleware("first", order)
        second = _RecordingMiddleware("second", order)
        pipeline = QueryMiddlewarePipeline()
        pipeline.add(first)
        pipeline.add(second)

        async def fn(sql: str, params: Any) -> None:
            return None

        await pipeline.execute("SELECT 1", None, fn)
        # 'before' hooks run in pipeline order; 'after' hooks in reverse.
        assert order == [
            "before:first",
            "before:second",
            "after:second",
            "after:first",
        ]

    @pytest.mark.asyncio
    async def test_error_recorded_and_reraised(self) -> None:
        order: list[str] = []
        mw = _RecordingMiddleware("rec", order)
        pipeline = QueryMiddlewarePipeline()
        pipeline.add(mw)
        error = QueryError("boom")

        async def fn(sql: str, params: Any) -> None:
            raise error

        with pytest.raises(QueryError):
            await pipeline.execute("SELECT 1", None, fn)
        ctx = mw.ctxs[0]
        assert ctx.error is error
        assert order[-1] == "after:rec"  # after_query still runs
        assert ctx.duration_ms >= 0.0

    @pytest.mark.asyncio
    async def test_after_query_errors_are_swallowed(self) -> None:
        # The pipeline swallows the framework error family from
        # after_query so one broken hook cannot fail the query.
        bad = _FailingAfterMiddleware(ValueError("middleware broke"))
        pipeline = QueryMiddlewarePipeline()
        pipeline.add(bad)

        async def fn(sql: str, params: Any) -> str:
            return "result"

        assert await pipeline.execute("SELECT 1", None, fn) == "result"


class _FakeLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, tuple[Any, ...]]] = []

    def warning(self, msg: Any, *args: Any) -> None:
        self.records.append(("warning", (msg, *args)))

    def info(self, msg: Any, *args: Any) -> None:
        self.records.append(("info", (msg, *args)))


class TestSlowQueryLogger:
    @pytest.mark.asyncio
    async def test_slow_query_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quadkit.sql.middleware.builtins as builtins  # noqa: PLC0415

        fake = _FakeLogger()
        monkeypatch.setattr(builtins, "logger", fake)
        mw = SlowQueryLogger(threshold_ms=5.0)
        ctx = QueryContext(sql="SELECT slow", params=None, duration_ms=10.0)
        await mw.after_query(ctx)
        assert len(fake.records) == 1
        level, (msg, *args) = fake.records[0]
        assert level == "warning"
        assert "SLOW QUERY" in msg
        assert args == [10.0, "SELECT slow"]

    @pytest.mark.asyncio
    async def test_slow_query_with_params_included_when_requested(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quadkit.sql.middleware.builtins as builtins  # noqa: PLC0415

        fake = _FakeLogger()
        monkeypatch.setattr(builtins, "logger", fake)
        mw = SlowQueryLogger(threshold_ms=5.0, log_params=True)
        ctx = QueryContext(sql="SELECT slow", params=(1, 2), duration_ms=10.0)
        await mw.after_query(ctx)
        _, (msg, *args) = fake.records[0]
        assert "params=" in msg
        assert (1, 2) in args

    @pytest.mark.asyncio
    async def test_fast_query_is_silent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import quadkit.sql.middleware.builtins as builtins  # noqa: PLC0415

        fake = _FakeLogger()
        monkeypatch.setattr(builtins, "logger", fake)
        mw = SlowQueryLogger(threshold_ms=5.0, log_params=True)
        ctx = QueryContext(sql="SELECT fast", params=(1,), duration_ms=1.0)
        await mw.after_query(ctx)
        assert fake.records == []


class TestQueryMetricsCollector:
    @pytest.mark.asyncio
    async def test_collects_per_pattern_stats(self) -> None:
        collector = QueryMetricsCollector()
        for duration in (10.0, 30.0):
            ctx = QueryContext(sql="SELECT * FROM users", duration_ms=duration)
            await collector.after_query(ctx)
        error_ctx = QueryContext(
            sql="SELECT * FROM orders",
            duration_ms=5.0,
            error=QueryError("boom"),
        )
        await collector.after_query(error_ctx)

        stats = collector.get_stats()
        assert stats["total_queries"] == 3
        assert stats["total_errors"] == 1
        users = next(
            q
            for q in stats["top_slow_queries"]
            if q["pattern"] == "SELECT * FROM users"
        )
        assert users["count"] == 2
        assert users["avg_ms"] == 20.0
        assert users["min_ms"] == 10.0
        assert users["max_ms"] == 30.0
        orders = next(
            q
            for q in stats["top_slow_queries"]
            if q["pattern"] == "SELECT * FROM orders"
        )
        assert orders["errors"] == 1

    def test_reset_clears_metrics(self) -> None:
        collector = QueryMetricsCollector()
        collector.get_stats()
        collector.reset()
        stats = collector.get_stats()
        assert stats["total_queries"] == 0
        assert stats["top_slow_queries"] == []


class TestQueryAuditLogger:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sql", ["INSERT INTO t VALUES (1)", "update t set x=1", "DELETE FROM t"]
    )
    async def test_write_statements_are_audited(
        self, sql: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quadkit.sql.middleware.builtins as builtins  # noqa: PLC0415

        fake = _FakeLogger()
        monkeypatch.setattr(builtins, "logger", fake)
        mw = QueryAuditLogger()
        await mw.after_query(QueryContext(sql=sql, duration_ms=1.0))
        assert len(fake.records) == 1
        assert fake.records[0][0] == "info"
        assert "AUDIT" in fake.records[0][1][0]

    @pytest.mark.asyncio
    async def test_read_statements_are_not_audited(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quadkit.sql.middleware.builtins as builtins  # noqa: PLC0415

        fake = _FakeLogger()
        monkeypatch.setattr(builtins, "logger", fake)
        mw = QueryAuditLogger()
        await mw.after_query(QueryContext(sql="SELECT * FROM t", duration_ms=1.0))
        assert fake.records == []


class _FailingBeforeMiddleware(QueryMiddleware):
    def __init__(self, order: list[str]) -> None:
        self.order = order

    async def before_query(self, ctx: QueryContext) -> None:
        self.order.append("before:bad")
        raise ValueError("before hook broke")

    async def after_query(self, ctx: QueryContext) -> None:
        self.order.append("after:bad")


class TestBeforeQueryErrorHandling:
    """A broken before-hook must not abort the query or skip after-hooks."""

    @pytest.mark.asyncio
    async def test_before_error_is_swallowed_and_after_hooks_still_run(self) -> None:
        order: list[str] = []
        bad = _FailingBeforeMiddleware(order)
        good = _RecordingMiddleware("good", order)
        pipeline = QueryMiddlewarePipeline()
        pipeline.add(bad)
        pipeline.add(good)

        async def fn(sql: str, params: Any) -> str:
            return "ok"

        result = await pipeline.execute("SELECT 1", None, fn)

        assert result == "ok"
        # The good middleware's before still ran (bad raised, not aborted
        # the pipeline), and both after-hooks ran in reverse pipeline order
        # ([bad, good] → after:good, after:bad).
        assert "before:good" in order
        assert order[-2:] == ["after:good", "after:bad"]


class TestMetricsPatternCap:
    """Dynamic SQL must not grow the pattern map without bound."""

    @pytest.mark.asyncio
    async def test_patterns_beyond_cap_aggregate_into_overflow(self) -> None:
        collector = QueryMetricsCollector(max_patterns=3)
        # 3 distinct patterns fill the cap; the 4th goes to overflow.
        for i in range(4):
            ctx = QueryContext(sql=f"SELECT * FROM t WHERE id = {i}", duration_ms=1.0)
            await collector.after_query(ctx)

        stats = collector.get_stats()
        assert stats["total_queries"] == 4  # totals preserved
        patterns = {q["pattern"] for q in stats["top_slow_queries"]}
        assert "(other)" in patterns
        overflow = next(q for q in stats["top_slow_queries"] if q["pattern"] == "(other)")
        assert overflow["count"] == 1
        # Named patterns unchanged.
        assert len(patterns) == 4

    @pytest.mark.asyncio
    async def test_overflow_bucket_accumulates(self) -> None:
        collector = QueryMetricsCollector(max_patterns=1)
        for i in range(5):
            await collector.after_query(QueryContext(sql=f"SELECT {i}", duration_ms=1.0))

        stats = collector.get_stats()
        assert stats["total_queries"] == 5
        overflow = next(q for q in stats["top_slow_queries"] if q["pattern"] == "(other)")
        assert overflow["count"] == 4

    @pytest.mark.asyncio
    async def test_default_cap_is_large(self) -> None:
        collector = QueryMetricsCollector()
        assert collector.max_patterns == 1000
