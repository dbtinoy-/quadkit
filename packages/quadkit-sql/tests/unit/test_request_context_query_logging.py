from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.core.trace_context import trace_id_var
from quadkit.primitives.context import create_default_context, request_scope
from quadkit.sql.logging import MemoryQueryLogger
from quadkit.sql.providers.query_executor import QueryExecutor


class _QueryExecutorUnderTest(QueryExecutor):
    async def _execute_query_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        return [{"ok": True}]

    async def _execute_modify_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> int:
        return 1


@pytest.mark.asyncio
async def test_query_executor_logs_request_and_trace_ids_from_active_context() -> None:
    context = create_default_context()
    logger = MemoryQueryLogger()
    executor = _QueryExecutorUnderTest(query_logger=logger, context=context)

    trace_token = trace_id_var.set("4bf92f3577b34da6a3ce929d0e0e4736")
    try:
        with request_scope(context.registry, request_id="req-9", user_id="user-9"):
            await executor.execute_query(object(), "SELECT 1")
    finally:
        trace_id_var.reset(trace_token)

    entries = await logger.get_recent_queries(1)
    assert entries[0].request_id == "req-9"
    assert entries[0].trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert entries[0].user_id == "user-9"


@pytest.mark.asyncio
async def test_query_executor_keeps_logging_safe_without_request_context() -> None:
    logger = MemoryQueryLogger()
    executor = _QueryExecutorUnderTest(query_logger=logger, context=None)

    await executor.execute_query(object(), "SELECT 1")

    entries = await logger.get_recent_queries(1)
    assert entries[0].request_id is None
    assert entries[0].trace_id is None
    assert entries[0].user_id is None
