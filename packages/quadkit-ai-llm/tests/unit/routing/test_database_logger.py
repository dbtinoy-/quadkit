"""Regression tests for the database routing logger's compatibility and privacy."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from quadkit.ai.llm.routing.loggers.database import DatabaseInferenceLogger
from quadkit.ai.llm.routing.types import InferenceLog, InferenceResult


class _FakeConnection:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetch_rows: list[dict[str, Any]] = []
        self.fetch_call: tuple[str, tuple[Any, ...]] | None = None

    async def execute(self, sql: str, *params: Any) -> None:
        self.execute_calls.append((sql, params))

    async def fetch(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        self.fetch_call = (sql, params)
        return self.fetch_rows


class _FakeDatabase:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    @asynccontextmanager
    async def scoped_context(self):
        yield

    async def get_scoped_connection(self) -> _FakeConnection:
        return self.connection


def _entry() -> InferenceLog:
    return InferenceLog(
        result=InferenceResult(
            provider="groq",
            model="model-a",
            content="a sensitive model completion",
            prompt_tokens=12,
            completion_tokens=7,
            latency_ms=18.6,
        ),
        providers_tried=["groq"],
        total_attempts=1,
        context={"analysis_id": "analysis-123"},
    )


@pytest.mark.asyncio
async def test_database_logger_omits_completion_content_by_default() -> None:
    connection = _FakeConnection()
    logger = DatabaseInferenceLogger(db=_FakeDatabase(connection))

    await logger.log(_entry())

    sql, params = connection.execute_calls[0]
    assert "latency_ms" in sql
    assert params[3] is None  # completion content is opt-in
    assert params[6] == 19
    assert params[11] == '{"analysis_id":"analysis-123"}'


@pytest.mark.asyncio
async def test_database_logger_can_explicitly_store_completion_content() -> None:
    connection = _FakeConnection()
    logger = DatabaseInferenceLogger(
        db=_FakeDatabase(connection),
        store_content=True,
    )

    await logger.log(_entry())

    assert connection.execute_calls[0][1][3] == "a sensitive model completion"


@pytest.mark.asyncio
async def test_database_logger_logs_only_exception_type_on_write_failure() -> None:
    """Database failure logs must omit exception text and traceback data."""
    connection = _FakeConnection()
    connection.execute = AsyncMock(side_effect=RuntimeError("sensitive SQL detail"))

    with patch("quadkit.ai.llm.routing.loggers.database.logger") as mock_logger:
        await DatabaseInferenceLogger(db=_FakeDatabase(connection)).log(_entry())

    mock_logger.error.assert_called_once_with(
        "llm_inference_log_persist_failed",
        error_type="RuntimeError",
    )
    mock_logger.exception.assert_not_called()
    assert "sensitive SQL detail" not in str(mock_logger.error.call_args)


@pytest.mark.asyncio
async def test_database_logger_logs_only_exception_type_on_read_failure() -> None:
    """Recent-log query failures are swallowed without exposing raw DB errors."""
    connection = _FakeConnection()
    connection.fetch = AsyncMock(side_effect=RuntimeError("sensitive SQL detail"))

    with patch("quadkit.ai.llm.routing.loggers.database.logger") as mock_logger:
        entries = await DatabaseInferenceLogger(
            db=_FakeDatabase(connection)
        ).get_recent()

    assert entries == []
    mock_logger.error.assert_called_once_with(
        "llm_inference_log_read_failed",
        error_type="RuntimeError",
    )
    mock_logger.exception.assert_not_called()
    assert "sensitive SQL detail" not in str(mock_logger.error.call_args)


@pytest.mark.asyncio
async def test_database_logger_reads_context_latency_and_only_routing_rows() -> None:
    created_at = datetime(2026, 10, 27, tzinfo=UTC)
    connection = _FakeConnection()
    connection.fetch_rows = [
        {
            "routing_id": "routing-123",
            "provider": "groq",
            "model": "model-a",
            "content": None,
            "prompt_tokens": 12,
            "completion_tokens": 7,
            "latency_ms": 19,
            "is_paid": False,
            "succeeded": True,
            "total_attempts": 1,
            "providers_tried": ["groq"],
            "context": '{"analysis_id":"analysis-123"}',
            "error_message": None,
            "created_at": created_at,
        }
    ]
    logger = DatabaseInferenceLogger(db=_FakeDatabase(connection))

    entries = await logger.get_recent(limit=5)

    assert connection.fetch_call is not None
    assert "WHERE routing_id IS NOT NULL" in connection.fetch_call[0]
    assert len(entries) == 1
    assert entries[0].context == {"analysis_id": "analysis-123"}
    assert entries[0].result is not None
    assert entries[0].result.content == ""
    assert entries[0].result.latency_ms == 19.0
