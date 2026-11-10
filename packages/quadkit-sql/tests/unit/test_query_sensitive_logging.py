"""Bound parameters and driver error details must not enter query logs."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from quadkit.sql.logging import MemoryQueryLogger
from quadkit.sql.providers.query_executor import QueryExecutor
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


class StubExecutor(QueryExecutor):
    def __init__(self, query_logger, *, fail=False):
        super().__init__(query_logger)
        self.fail = fail
        self.actual_params = None

    async def _execute_query_raw(self, connection: Any, sql: str, params=None):
        self.actual_params = params
        if self.fail:
            raise RuntimeError(f"driver includes secret: {params[0]}")
        return [{"ok": True}]

    async def _execute_modify_raw(self, connection: Any, sql: str, params=None):
        self.actual_params = params
        if self.fail:
            raise RuntimeError(f"driver includes secret: {params[0]}")
        return 1


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["query", "modify"])
@pytest.mark.parametrize("fail", [False, True])
async def test_executor_redacts_before_every_logger(monkeypatch, operation, fail):
    secret = "session-token-A3-DONT-LOG"
    log = MemoryQueryLogger()
    system_log = Mock()
    monkeypatch.setattr("quadkit.sql.providers.query_executor.logger", system_log)
    executor = StubExecutor(log, fail=fail)
    run = executor.execute_query if operation == "query" else executor.execute_modify
    if fail:
        with pytest.raises(RuntimeError, match=secret):
            await run(None, "SELECT ?", [secret, "private@example.test"])
    else:
        await run(None, "SELECT ?", [secret, "private@example.test"])
    assert executor.actual_params == [secret, "private@example.test"]
    entry = (await log.get_recent_queries())[0]
    assert entry.params is None  # bind values are dropped, not echoed
    assert entry.error_message == ("RuntimeError" if fail else None)
    assert secret not in repr(entry)
    assert secret not in repr(system_log.method_calls)
    assert "private@example.test" not in repr(entry)


@pytest.mark.asyncio
async def test_real_sqlite_query_logger_does_not_store_session_token():
    logger = MemoryQueryLogger()
    provider = SQLiteProvider(database_path=":memory:", query_logger=logger)
    await provider.connect()
    try:
        await provider.execute(
            'CREATE TABLE "auth_sessions" ("token" TEXT PRIMARY KEY)'
        )
        secret = "session-token-B7-DONT-LOG"
        await provider.execute(
            'INSERT INTO "auth_sessions" ("token") VALUES (?)', [secret]
        )
        result = await provider.execute_query(
            'SELECT * FROM "auth_sessions" WHERE "token" = ?', [secret]
        )
        assert result.rows[0]["token"] == secret
        entries = await logger.get_recent_queries()
        assert secret not in repr(entries)
        assert entries[-1].params is None  # bind values are dropped, not echoed
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
async def test_file_logger_output_and_history_redact_success_and_failure(tmp_path):
    from quadkit.sql.logging import FileQueryLogger

    secret = "session-token-C9-DONT-LOG"
    path = tmp_path / "queries.log"
    log = FileQueryLogger(str(path))
    executor = StubExecutor(log)
    await executor.execute_modify(
        None, "INSERT INTO auth_sessions VALUES (?)", [secret]
    )
    executor.fail = True
    with pytest.raises(RuntimeError, match=secret):
        await executor.execute_query(
            None, "SELECT * FROM auth_sessions WHERE token = ?", [secret]
        )
    assert secret not in path.read_text()
    assert secret not in repr(await log.get_recent_queries())
    assert '"params":null' in path.read_text()
