"""Database-backed quota backend for LLM routing.

Persists per-provider daily quota state to the ``provider_daily_usage``
table via ``DatabaseProviderProtocol``.  Suitable for multi-process and
production deployments.

All SQL errors are absorbed so that quota tracking failures never interrupt
inference.  If the DB is unreachable, methods return safe defaults
(is_exhausted → False, increment → no-op).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from quadkit.ai.llm.routing.backends._time import end_of_utc_day
from quadkit.ai.llm.routing.types import ProviderUsage
from quadkit.logging import get_logger, safe_error_type

if TYPE_CHECKING:
    from quadkit.contracts.data import DatabaseProviderProtocol

logger = get_logger(__name__)

__all__ = ["DatabaseQuotaBackend"]

_INCREMENT_SQL = """
INSERT INTO provider_daily_usage (provider, usage_date, success_count)
VALUES ($1, $2, 1)
ON CONFLICT (provider, usage_date)
DO UPDATE SET
    success_count = provider_daily_usage.success_count + 1,
    updated_at    = NOW()
"""

_MARK_EXHAUSTED_SQL = """
INSERT INTO provider_daily_usage (provider, usage_date, is_exhausted, exhausted_until)
VALUES ($1, $2, TRUE, $3)
ON CONFLICT (provider, usage_date)
DO UPDATE SET
    is_exhausted    = TRUE,
    exhausted_until = $3,
    updated_at      = NOW()
"""

_RECORD_ERROR_SQL = """
INSERT INTO provider_daily_usage (provider, usage_date, error_count)
VALUES ($1, $2, 1)
ON CONFLICT (provider, usage_date)
DO UPDATE SET
    error_count = provider_daily_usage.error_count + 1,
    updated_at  = NOW()
"""

_GET_TODAY_SQL = """
SELECT provider, usage_date::text, success_count, error_count, is_exhausted,
       exhausted_until
FROM provider_daily_usage
WHERE provider = $1 AND usage_date = $2
"""

_GET_ALL_TODAY_SQL = """
SELECT provider, usage_date::text, success_count, error_count, is_exhausted,
       exhausted_until
FROM provider_daily_usage
WHERE usage_date = $1
"""


class DatabaseQuotaBackend:
    """PostgreSQL-backed quota backend using ``DatabaseProviderProtocol``.

    Uses UPSERT statements for thread-safe and process-safe concurrent
    updates without application-level locking.

    Example:
        >>> backend = DatabaseQuotaBackend(db=db_provider)
        >>> await backend.increment("groq")
        >>> await backend.is_exhausted("groq")
        False
    """

    def __init__(self, db: DatabaseProviderProtocol) -> None:
        """Initialise the database quota backend.

        Args:
            db: Framework database provider (injected from the DI container).
        """
        self._db = db

    def _today(self) -> str:
        """Return today's UTC date as an ISO 8601 string."""
        return datetime.now(UTC).date().isoformat()

    async def is_exhausted(self, provider: str) -> bool:
        """Return ``True`` when *provider* is quota-exhausted today.

        Args:
            provider: Provider name.

        Returns:
            Whether the provider is currently exhausted; defaults to ``False``
            when the database call fails.
        """
        try:
            async with self._db.scoped_context():
                conn = await self._db.get_scoped_connection()
                row = await conn.fetchrow(_GET_TODAY_SQL, provider, self._today())
                if row is None:
                    return False
                exhausted_until = row["exhausted_until"]
                if exhausted_until is None:
                    return False
                return bool(datetime.now(UTC) < exhausted_until)
        except Exception as exc:
            logger.error(
                "llm.quota.db: is_exhausted query failed",
                error_type=safe_error_type(exc),
            )
            return False

    async def increment(self, provider: str) -> None:
        """Record one successful completion for *provider* today.

        Args:
            provider: Provider name.
        """
        try:
            async with self._db.scoped_context():
                conn = await self._db.get_scoped_connection()
                await conn.execute(_INCREMENT_SQL, provider, self._today())
        except Exception as exc:
            logger.error(
                "llm.quota.db: increment failed",
                error_type=safe_error_type(exc),
            )

    async def mark_exhausted(
        self, provider: str, *, until: datetime | None = None
    ) -> None:
        """Mark *provider* exhausted until *until*.

        Args:
            provider: Cascade-entry key (``name:model``) or provider name.
            until: Exhaustion expiry; ``None`` means the rest of today (UTC).
        """
        expiry = until or end_of_utc_day()
        try:
            async with self._db.scoped_context():
                conn = await self._db.get_scoped_connection()
                await conn.execute(_MARK_EXHAUSTED_SQL, provider, self._today(), expiry)
                logger.info("llm.quota.db: quota marked exhausted")
        except Exception as exc:
            logger.error(
                "llm.quota.db: mark_exhausted failed",
                error_type=safe_error_type(exc),
            )

    async def record_error(self, provider: str) -> None:
        """Record a non-exhaustion error for *provider* today.

        Args:
            provider: Provider name.
        """
        try:
            async with self._db.scoped_context():
                conn = await self._db.get_scoped_connection()
                await conn.execute(_RECORD_ERROR_SQL, provider, self._today())
        except Exception as exc:
            logger.error(
                "llm.quota.db: record_error failed",
                error_type=safe_error_type(exc),
            )

    async def get_usage(self, provider: str) -> ProviderUsage | None:
        """Return today's usage record for *provider*.

        Args:
            provider: Provider name.

        Returns:
            :class:`ProviderUsage` or ``None`` when not found or on DB error.
        """
        try:
            async with self._db.scoped_context():
                conn = await self._db.get_scoped_connection()
                row = await conn.fetchrow(_GET_TODAY_SQL, provider, self._today())
                if row is None:
                    return None
                return ProviderUsage(
                    provider=row["provider"],
                    usage_date=row["usage_date"],
                    success_count=row["success_count"],
                    error_count=row["error_count"],
                    is_exhausted=row["is_exhausted"],
                    exhausted_until=row["exhausted_until"],
                )
        except Exception as exc:
            logger.error(
                "llm.quota.db: get_usage failed",
                error_type=safe_error_type(exc),
            )
            return None

    async def get_all_usage(self) -> list[ProviderUsage]:
        """Return all today's usage records.

        Returns:
            List of :class:`ProviderUsage`; empty list on DB error.
        """
        try:
            async with self._db.scoped_context():
                conn = await self._db.get_scoped_connection()
                rows = await conn.fetch(_GET_ALL_TODAY_SQL, self._today())
                return [
                    ProviderUsage(
                        provider=row["provider"],
                        usage_date=row["usage_date"],
                        success_count=row["success_count"],
                        error_count=row["error_count"],
                        is_exhausted=row["is_exhausted"],
                    )
                    for row in rows
                ]
        except Exception as exc:
            logger.error(
                "llm.quota.db: get_all_usage failed",
                error_type=safe_error_type(exc),
            )
            return []
