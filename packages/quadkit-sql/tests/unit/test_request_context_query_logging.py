from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from quadkit.contracts.core.trace_context import trace_id_var
from quadkit.primitives.context import create_default_context, request_scope
from quadkit.sql.exceptions import DatabaseError
from quadkit.sql.logging import MemoryQueryLogger
import quadkit.sql.providers.query_executor as query_executor_module
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
async def test_query_executor_omits_sensitive_values_and_context_identifiers() -> None:
    context = create_default_context()
    logger = MemoryQueryLogger()
    executor = _QueryExecutorUnderTest(query_logger=logger, context=context)
    private_fingerprint = "private-guest-fingerprint-7282"
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"

    trace_token = trace_id_var.set(trace_id)
    try:
        with request_scope(context.registry, request_id="req-private", user_id="user-private"):
            await executor.execute_query(
                object(),
                "SELECT * FROM users WHERE guest_fingerprint = ?",
                [private_fingerprint],
            )
    finally:
        trace_id_var.reset(trace_token)

    entries = await logger.get_recent_queries(1)
    entry = entries[0]
    assert entry.sql == "SELECT * FROM users WHERE guest_fingerprint = ?"
    assert entry.params is None
    assert entry.request_id is None
    assert entry.trace_id is None
    assert entry.user_id is None
    serialized = repr(entry)
    for private_value in (private_fingerprint, trace_id, "req-private", "user-private"):
        assert private_value not in serialized


@pytest.mark.asyncio
async def test_query_executor_keeps_logging_safe_without_request_context() -> None:
    logger = MemoryQueryLogger()
    executor = _QueryExecutorUnderTest(query_logger=logger, context=None)

    await executor.execute_query(object(), "SELECT 1")

    entries = await logger.get_recent_queries(1)
    assert entries[0].request_id is None
    assert entries[0].trace_id is None
    assert entries[0].user_id is None
    assert entries[0].sql == "SELECT ?"
    assert entries[0].params is None


@pytest.mark.asyncio
async def test_query_logs_redact_inline_literals_and_comments() -> None:
    logger = MemoryQueryLogger()
    executor = _QueryExecutorUnderTest(query_logger=logger, context=None)
    private_fingerprint = "private-fingerprint-7282"
    private_path = "/srv/private/tenant-42"
    private_token = "token=secret"

    await executor.execute_query(
        object(),
        "SELECT * FROM users "
        f"WHERE guest_fingerprint = '{private_fingerprint}' AND user_id = 73 "
        f"/* {private_path} */ -- {private_token}",
    )

    entries = await logger.get_recent_queries(1)
    sql = entries[0].sql
    assert "SELECT * FROM users" in sql
    assert "guest_fingerprint = ?" in sql
    assert "user_id = ?" in sql
    assert entries[0].params is None
    for private_value in (private_fingerprint, private_path, private_token, "73"):
        assert private_value not in sql


@pytest.mark.asyncio
async def test_query_failure_logs_sanitized_sql_and_only_exception_type(monkeypatch) -> None:
    private_error = "fingerprint=private-value at /srv/private/tenant-42"
    private_fingerprint = "private-fingerprint-7282"
    logger = MagicMock()
    monkeypatch.setattr(query_executor_module, "logger", logger)

    class FailingQueryExecutor(_QueryExecutorUnderTest):
        async def _execute_query_raw(
            self,
            connection: Any,
            sql: str,
            params: list[Any] | None = None,
        ) -> list[dict[str, Any]]:
            raise DatabaseError(private_error)

    query_logger = MemoryQueryLogger()
    executor = FailingQueryExecutor(query_logger=query_logger, context=None)
    with pytest.raises(DatabaseError):
        await executor.execute_query(
            object(),
            "SELECT * FROM users WHERE guest_fingerprint = ?",
            [private_fingerprint],
        )

    logged = repr(logger.mock_calls)
    assert "DatabaseError" in logged
    assert private_error not in logged
    assert private_fingerprint not in logged
    assert "/srv/private/tenant-42" not in logged
    logger.exception.assert_not_called()

    entries = await query_logger.get_recent_queries(1)
    assert entries[0].sql == "SELECT * FROM users WHERE guest_fingerprint = ?"
    assert entries[0].params is None
    assert entries[0].error_message == "DatabaseError"
