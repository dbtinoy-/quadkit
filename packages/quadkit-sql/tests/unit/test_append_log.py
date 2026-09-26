"""Unit tests for DatabaseProviderAppendLog (repositories/append_log.py)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.sql.exceptions import QueryError
from quadkit.sql.repositories.append_log import (
    DatabaseProviderAppendLog,
    _row_to_dict,
)


class _FakeProvider:
    def __init__(self) -> None:
        self.execute_query = AsyncMock(return_value=[])
        self.calls: list[tuple[str, list[Any]]] = []


def _make_log(provider: _FakeProvider) -> DatabaseProviderAppendLog[dict[str, Any]]:
    return DatabaseProviderAppendLog(
        provider=provider,
        table_name="events",
        serializer=lambda e: e,
        deserializer=lambda d: d,
    )


class TestAppend:
    @pytest.mark.asyncio
    async def test_empty_append_returns_current_version(self) -> None:
        provider = _FakeProvider()
        provider.execute_query.return_value = [{"coalesce": 3}]
        log = _make_log(provider)
        assert await log.append("s1", []) == 3

    @pytest.mark.asyncio
    async def test_append_writes_one_row_per_event(self) -> None:
        provider = _FakeProvider()
        provider.execute_query.return_value = [{"coalesce": 0}]
        log = _make_log(provider)
        events = [
            {"event_id": "e1", "event_type": "Created", "payload": 1},
            {"event_id": "e2", "event_type": "Updated", "payload": 2},
        ]
        new_version = await log.append("s1", events)
        assert new_version == 2
        assert provider.execute_query.call_count == 3  # 1 version read + 2 inserts
        insert_calls = provider.execute_query.call_args_list[1:]
        # First insert: stream version 1, serialized event JSON, metadata {}.
        first_sql, first_params = insert_calls[0].args
        assert "INSERT INTO events" in first_sql
        assert first_params[0] == "s1"
        assert first_params[1] == 1
        assert first_params[2] == "e1"
        assert first_params[3] == "Created"
        # The framework serialization layer (orjson) emits bytes.
        assert b'"payload"' in first_params[4]
        assert first_params[5] == b"{}"
        # Second insert increments the stream version.
        second_sql, second_params = insert_calls[1].args
        assert second_params[1] == 2
        assert second_params[2] == "e2"

    @pytest.mark.asyncio
    async def test_expected_version_mismatch_raises(self) -> None:
        provider = _FakeProvider()
        provider.execute_query.return_value = [{"coalesce": 5}]
        log = _make_log(provider)
        with pytest.raises(ValueError, match="Concurrency conflict"):
            await log.append("s1", [{"event_id": "e"}], expected_version=4)
        # No insert was attempted.
        assert provider.execute_query.call_count == 1

    @pytest.mark.asyncio
    async def test_expected_version_match_proceeds(self) -> None:
        provider = _FakeProvider()
        provider.execute_query.return_value = [{"coalesce": 5}]
        log = _make_log(provider)
        assert await log.append("s1", [{"event_id": "e"}], expected_version=5) == 6


class TestRead:
    @pytest.mark.asyncio
    async def test_read_deserializes_rows_and_injects_raw_row(self) -> None:
        provider = _FakeProvider()
        provider.execute_query.return_value = [
            {
                "event_id": "e1",
                "event_type": "Created",
                "event_data": '{"payload": 1}',
                "metadata": "{}",
                "timestamp": "2026-01-01T00:00:00Z",
                "stream_version": 1,
            }
        ]
        log = _make_log(provider)
        rows = await log.read("s1", from_version=1, to_version=2)
        assert len(rows) == 1
        assert rows[0]["payload"] == 1
        assert rows[0]["_raw_row"]["event_id"] == "e1"
        sql, params = provider.execute_query.call_args.args
        assert "stream_version >= $2" in sql
        assert "stream_version <= $3" in sql
        assert params == ["s1", 1, 2]

    @pytest.mark.asyncio
    async def test_read_without_to_version_omits_upper_bound(self) -> None:
        provider = _FakeProvider()
        provider.execute_query.return_value = []
        log = _make_log(provider)
        assert await log.read("s1") == []
        sql, params = provider.execute_query.call_args.args
        assert "stream_version <= $3" not in sql
        assert params == ["s1", 0]


class TestReadAll:
    @pytest.mark.asyncio
    async def test_read_all_uses_limit_offset(self) -> None:
        provider = _FakeProvider()
        provider.execute_query.return_value = [("e1", "T", '{"a": 1}', "{}", "ts", 1)]
        log = _make_log(provider)
        rows = await log.read_all(offset=10, limit=5)
        assert rows[0]["a"] == 1
        sql, params = provider.execute_query.call_args.args
        assert "LIMIT $1 OFFSET $2" in sql
        assert params == [5, 10]


class TestStreamVersion:
    @pytest.mark.asyncio
    async def test_no_rows_returns_zero(self) -> None:
        provider = _FakeProvider()
        provider.execute_query.return_value = []
        log = _make_log(provider)
        assert await log.get_stream_version("s1") == 0

    @pytest.mark.asyncio
    async def test_reads_coalesce_column(self) -> None:
        provider = _FakeProvider()
        provider.execute_query.return_value = [{"coalesce": 7}]
        log = _make_log(provider)
        assert await log.get_stream_version("s1") == 7


class TestDeleteStream:
    @pytest.mark.asyncio
    async def test_success_returns_true(self) -> None:
        provider = _FakeProvider()
        log = _make_log(provider)
        assert await log.delete_stream("s1") is True
        sql, params = provider.execute_query.call_args.args
        assert sql == "DELETE FROM events WHERE stream_id = $1"
        assert params == ["s1"]

    @pytest.mark.asyncio
    async def test_database_error_returns_false(self) -> None:
        provider = _FakeProvider()
        provider.execute_query.side_effect = QueryError("boom")
        log = _make_log(provider)
        assert await log.delete_stream("s1") is False


class TestRowNormalization:
    def test_mapping_row_passthrough(self) -> None:
        row = {"event_id": "e", "event_data": "{}"}
        assert _row_to_dict(row) == row

    def test_positional_row_zipped_to_columns(self) -> None:
        row = ("e1", "T", '{"a": 1}', "{}", "ts", 3)
        normalized = _row_to_dict(row)
        assert normalized["event_id"] == "e1"
        assert normalized["event_data"] == '{"a": 1}'
        assert normalized["stream_version"] == 3
