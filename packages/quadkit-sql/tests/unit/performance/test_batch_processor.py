"""Tests for the batch processor (chunked query processing + bulk insert)."""

from __future__ import annotations

import pytest

from quadkit.sql.exceptions import DatabaseError
from quadkit.sql.performance.batch_processor import BatchProcessor, BatchResult


class _Provider:
    def __init__(self) -> None:
        self.executed: list[tuple[str, list]] = []

    async def execute(self, sql: str, params: list) -> None:
        self.executed.append((sql, params))


class TestProcessInBatches:
    async def _query_factory(self, chunks: list[list[dict]]) -> object:
        calls = {"n": 0}

        async def query_fn(offset: int, limit: int) -> list[dict]:
            idx = offset // limit
            return chunks[idx] if idx < len(chunks) else []

        return query_fn

    async def test_basic_batching(self) -> None:
        chunks = [[{"id": i} for i in range(3)], [{"id": 3}]]
        seen: list[list[dict]] = []

        async def processor(batch: list[dict]) -> None:
            seen.append(batch)

        result = await BatchProcessor(object()).process_in_batches(  # noqa: B018
            query_fn=await self._query_factory(chunks),
            batch_size=3,
            processor=processor,
        )
        assert result.total_processed == 4
        assert result.total_batches == 2
        assert result.errors == 0
        assert [len(b) for b in seen] == [3, 1]

    async def test_empty_first_batch(self) -> None:
        processed = []

        async def processor(batch: list[dict]) -> None:
            processed.append(batch)

        result = await BatchProcessor(object()).process_in_batches(  # noqa: B018
            query_fn=await self._query_factory([]),
            batch_size=10,
            processor=processor,
        )
        assert (result.total_processed, result.total_batches) == (0, 0)
        assert processed == []

    async def test_max_records_stops_early(self) -> None:
        chunks = [[{"id": i} for i in range(5)] for _ in range(4)]
        n = 0

        async def processor(batch: list[dict]) -> None:
            nonlocal n
            n += 1

        result = await BatchProcessor(object()).process_in_batches(  # noqa: B018
            query_fn=await self._query_factory(chunks),
            batch_size=5,
            processor=processor,
            max_records=10,
        )
        assert result.total_processed == 10
        assert n == 2

    async def test_progress_callback(self) -> None:
        chunks = [[{"id": 0}], [{"id": 1}]]
        progress: list[tuple[int, int]] = []

        async def processor(batch: list[dict]) -> None:
            pass

        await BatchProcessor(object()).process_in_batches(  # noqa: B018
            query_fn=await self._query_factory(chunks),
            batch_size=1,
            processor=processor,
            on_progress=lambda done, total: progress.append((done, total)),
            max_records=10,
        )
        assert progress == [(1, 10), (2, 10)]

    async def test_database_error_propagates_and_counts(self) -> None:
        async def query_fn(offset: int, limit: int) -> list[dict]:
            return [{"id": offset // limit}] if offset < 2 else []

        async def processor(batch: list[dict]) -> None:
            raise DatabaseError("boom")

        with pytest.raises(DatabaseError, match="boom"):
            await BatchProcessor(object()).process_in_batches(  # noqa: B018
                query_fn=query_fn,
                batch_size=1,
                processor=processor,
            )

    async def test_duration_and_rate_populated(self) -> None:
        chunks = [[{"id": 0}]]
        async_ok = object()

        async def processor(batch: list[dict]) -> None:
            pass

        result = await BatchProcessor(async_ok).process_in_batches(  # noqa: B018
            query_fn=await self._query_factory(chunks),
            batch_size=1,
            processor=processor,
        )
        assert result.duration_seconds >= 0
        assert isinstance(result.items_per_second, float)

    def test_batch_result_defaults(self) -> None:
        assert BatchResult() == BatchResult(0, 0, 0, 0.0, 0.0)


class TestBulkInsertChunked:
    async def test_single_chunk_sql_shape(self) -> None:
        provider = _Provider()
        records = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        inserted = await BatchProcessor(provider).bulk_insert_chunked(
            "events", records, chunk_size=10
        )
        assert inserted == 2
        sql, params = provider.executed[0]
        assert sql == 'INSERT INTO "events" ("a", "b") VALUES ($1, $2), ($3, $4)'
        assert params == [1, "x", 2, "y"]

    async def test_multiple_chunks(self) -> None:
        provider = _Provider()
        records = [{"v": i} for i in range(7)]
        inserted = await BatchProcessor(provider).bulk_insert_chunked(
            "t", records, chunk_size=3
        )
        assert inserted == 7
        assert len(provider.executed) == 3
        assert provider.executed[0][1] == [0, 1, 2]
        assert provider.executed[1][1] == [3, 4, 5]
        assert provider.executed[2][1] == [6]

    async def test_progress_callback(self) -> None:
        provider = _Provider()
        records = [{"v": i} for i in range(5)]
        progress: list[tuple[int, int]] = []
        await BatchProcessor(provider).bulk_insert_chunked(
            "t",
            records,
            chunk_size=2,
            on_progress=lambda d, t: progress.append((d, t)),
        )
        assert progress == [(2, 5), (4, 5), (5, 5)]

    async def test_empty_records(self) -> None:
        provider = _Provider()
        assert await BatchProcessor(provider).bulk_insert_chunked("t", []) == 0
        assert provider.executed == []
