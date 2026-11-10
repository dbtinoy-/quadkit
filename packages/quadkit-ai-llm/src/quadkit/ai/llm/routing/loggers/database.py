"""Database-backed inference logger for LLM routing.

Persists every ``InferenceLog`` entry to the ``inference_log`` table via
``DatabaseProviderProtocol``.  Suitable for production deployments.

All SQL errors are absorbed so that logging failures never interrupt
inference.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.ai.llm.routing.types import InferenceLog
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str, loads

if TYPE_CHECKING:
    from quadkit.contracts.data import DatabaseProviderProtocol

logger = get_logger(__name__)

__all__ = ["DatabaseInferenceLogger"]

_INSERT_SQL = """
INSERT INTO inference_log (
    routing_id,
    provider,
    model,
    content,
    prompt_tokens,
    completion_tokens,
    latency_ms,
    is_paid,
    succeeded,
    total_attempts,
    providers_tried,
    context,
    error_message,
    created_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
"""

_GET_RECENT_SQL = """
SELECT
    routing_id,
    provider,
    model,
    content,
    prompt_tokens,
    completion_tokens,
    latency_ms,
    is_paid,
    succeeded,
    total_attempts,
    providers_tried,
    context,
    error_message,
    created_at
FROM inference_log
WHERE routing_id IS NOT NULL
ORDER BY created_at DESC
LIMIT $1
"""


class DatabaseInferenceLogger:
    """PostgreSQL-backed inference logger using ``DatabaseProviderProtocol``.

    Every call to :meth:`log` performs a best-effort INSERT; failures are
    swallowed and only emitted as ``ERROR``-level log lines so that
    observability failures never break inference.

    Example:
        >>> db_logger = DatabaseInferenceLogger(db=db_provider)
        >>> await db_logger.log(some_inference_log)
        >>> recent = await db_logger.get_recent(limit=20)
    """

    def __init__(
        self,
        db: DatabaseProviderProtocol,
        *,
        store_content: bool = False,
    ) -> None:
        """Initialise the database inference logger.

        Args:
            db: Framework database provider (injected from the DI container).
            store_content: Explicitly opt in to retaining model completions. This
                defaults to ``False`` because generated text may contain sensitive
                health information.
        """
        self._db = db
        self._store_content = store_content

    async def log(self, entry: InferenceLog) -> None:
        """Persist one ``InferenceLog`` entry.

        Args:
            entry: :class:`~quadkit.ai.llm.routing.types.InferenceLog` instance.
        """
        try:
            provider = entry.result.provider if entry.result else None
            model = entry.result.model if entry.result else None
            content = (
                entry.result.content if entry.result and self._store_content else None
            )
            prompt_tokens = entry.result.prompt_tokens if entry.result else 0
            completion_tokens = entry.result.completion_tokens if entry.result else 0
            latency_ms = round(entry.result.latency_ms) if entry.result else 0
            is_paid = entry.result.is_paid if entry.result else False
            error_message = entry.error.message if entry.error else None

            async with self._db.scoped_context():
                conn = await self._db.get_scoped_connection()
                await conn.execute(
                    _INSERT_SQL,
                    entry.routing_id,
                    provider,
                    model,
                    content,
                    prompt_tokens,
                    completion_tokens,
                    latency_ms,
                    is_paid,
                    entry.succeeded,
                    entry.total_attempts,
                    entry.providers_tried,
                    dumps_str(entry.context),
                    error_message,
                    entry.created_at,
                )
        except Exception as exc:
            logger.error(
                "llm_inference_log_persist_failed",
                error_type=type(exc).__name__,
            )

    async def get_recent(self, limit: int = 100) -> list[InferenceLog]:
        """Return the most recent *limit* log entries (newest-first).

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of :class:`~quadkit.ai.llm.routing.types.InferenceLog` instances,
            or an empty list on DB error.
        """
        try:
            from quadkit.ai.llm.routing.types import (
                InferenceError,
                InferenceResult,
            )

            async with self._db.scoped_context():
                conn = await self._db.get_scoped_connection()
                rows = await conn.fetch(_GET_RECENT_SQL, limit)

            entries: list[InferenceLog] = []
            for row in rows:
                result: InferenceResult | None = None
                error: InferenceError | None = None

                if row["succeeded"] and row["provider"]:
                    result = InferenceResult(
                        provider=row["provider"],
                        model=row["model"] or "",
                        content=row["content"] or "",
                        prompt_tokens=row["prompt_tokens"] or 0,
                        completion_tokens=row["completion_tokens"] or 0,
                        latency_ms=float(row["latency_ms"] or 0),
                        is_paid=row["is_paid"] or False,
                    )
                elif row["error_message"]:
                    error = InferenceError(
                        message=row["error_message"],
                        providers_tried=list(row["providers_tried"] or []),
                    )

                ctx = row["context"]
                if isinstance(ctx, str):
                    try:
                        ctx = loads(ctx)
                    except (ValueError, KeyError, TypeError):
                        ctx = {}

                entries.append(
                    InferenceLog(
                        routing_id=row["routing_id"],
                        result=result,
                        error=error,
                        providers_tried=list(row["providers_tried"] or []),
                        total_attempts=row["total_attempts"] or 0,
                        context=ctx or {},
                        created_at=row["created_at"],
                    )
                )
            return entries
        except Exception as exc:
            logger.error(
                "llm_inference_log_read_failed",
                error_type=type(exc).__name__,
            )
            return []
