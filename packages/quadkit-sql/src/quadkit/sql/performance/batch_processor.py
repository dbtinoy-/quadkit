"""Batch processor for efficient large-dataset operations.

Provides chunked processing, bulk insert, and progress tracking
for operations that involve thousands or millions of records.

Example:
    processor = BatchProcessor(provider)

    # Process in batches
    result = await processor.process_in_batches(
        query=qb,
        batch_size=500,
        processor=lambda batch: send_emails(batch),
    )

    # Bulk insert with chunking
    inserted = await processor.bulk_insert_chunked(
        table="events",
        records=million_records,
        chunk_size=1000,
    )
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from quadkit.contracts.data.identifiers import Column, Table
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import DatabaseConnectionError, DatabaseError, QueryError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)


@dataclass
class BatchResult:
    """Result of a batch processing operation."""

    total_processed: int = 0
    total_batches: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    items_per_second: float = 0.0


class BatchProcessor:
    """Efficient batch processing for large dataset operations.

    Args:
        provider: Database provider used for query execution.
        max_concurrent_batches: Maximum number of batches that may be
            processed concurrently.  When the limit is reached the producer
            loop blocks until a processing slot becomes free, preventing
            unbounded memory growth when the producer is faster than the
            consumer.  Default is ``1`` (fully sequential).
    """

    def __init__(
        self,
        provider: Any,
        max_concurrent_batches: int = 1,
    ) -> None:
        self._provider = provider
        self._semaphore = asyncio.Semaphore(max(1, max_concurrent_batches))

    @property
    def _monotonic(self) -> float:
        """Return monotonic time using ambient clock."""
        return ambient_clock.monotonic()

    async def process_in_batches(
        self,
        *,
        query_fn: Callable[[int, int], Awaitable[list[dict[str, Any]]]],
        batch_size: int = 1000,
        processor: Callable[[list[dict[str, Any]]], Awaitable[None]],
        on_progress: Callable[[int, int], None] | None = None,
        max_records: int | None = None,
    ) -> BatchResult:
        """Process query results in batches.

        Args:
            query_fn: Async function that takes (offset, limit) and returns rows.
            batch_size: Number of records per batch.
            processor: Async function to process each batch.
            on_progress: Optional callback (processed, total).
            max_records: Optional maximum number of records to process.

        Returns:
            BatchResult with processing statistics.
        """
        result = BatchResult()
        start = self._monotonic
        offset = 0

        while True:
            batch = await query_fn(offset, batch_size)
            if not batch:
                break

            try:
                # Acquire semaphore before each batch to limit concurrency and
                # apply backpressure when max_concurrent_batches is exceeded.
                async with self._semaphore:
                    await processor(batch)
                result.total_processed += len(batch)
                result.total_batches += 1
            except (DatabaseError, QueryError, DatabaseConnectionError):
                result.errors += 1
                logger.exception(
                    "Batch %d failed at offset %d",
                    result.total_batches,
                    offset,
                )
                raise

            if on_progress:
                on_progress(result.total_processed, max_records or 0)

            if max_records and result.total_processed >= max_records:
                break

            offset += batch_size

            if len(batch) < batch_size:
                break

        result.duration_seconds = self._monotonic - start
        if result.duration_seconds > 0:
            result.items_per_second = round(
                result.total_processed / result.duration_seconds,
                1,
            )

        logger.info(
            "Batch processing complete: %d items in %d batches (%.1f items/sec)",
            result.total_processed,
            result.total_batches,
            result.items_per_second,
        )
        return result

    async def bulk_insert_chunked(
        self,
        table: str,
        records: list[dict[str, Any]],
        *,
        chunk_size: int = 500,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> int:
        """Insert records in chunks for memory efficiency.

        Args:
            table: Target table name.
            records: Records to insert.
            chunk_size: Records per chunk.
            on_progress: Optional callback (inserted, total).

        Returns:
            Total number of records inserted.
        """
        total = len(records)
        inserted = 0
        start = self._monotonic

        for i in range(0, total, chunk_size):
            chunk = records[i : i + chunk_size]

            if not chunk:
                break

            columns = list(chunk[0].keys())
            values_lists: list[list[Any]] = [
                [row[col] for col in columns] for row in chunk
            ]

            # Build multi-row INSERT
            placeholders_per_row = []
            all_params: list[Any] = []
            param_idx = 1

            for row_values in values_lists:
                row_placeholders = []
                for val in row_values:
                    row_placeholders.append(f"${param_idx}")
                    all_params.append(val)
                    param_idx += 1
                placeholders_per_row.append(
                    f"({', '.join(row_placeholders)})",
                )

            sql = (
                f"INSERT INTO {Table(table)} "  # noqa: S608 -- identifiers quoted via Table()/Column()
                f"({', '.join(str(Column(c)) for c in columns)}) "
                f"VALUES {', '.join(placeholders_per_row)}"
            )

            await self._provider.execute(sql, all_params)
            inserted += len(chunk)

            if on_progress:
                on_progress(inserted, total)

        elapsed = self._monotonic - start
        rate = inserted / elapsed if elapsed > 0 else 0
        logger.info(
            "Bulk insert: %d/%d records into %s (%.1f rec/sec)",
            inserted,
            total,
            table,
            rate,
        )
        return inserted
