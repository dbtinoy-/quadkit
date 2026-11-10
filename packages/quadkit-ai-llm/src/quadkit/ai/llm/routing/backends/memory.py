"""In-memory quota backend for LLM routing.

Suitable for development, testing, and single-process deployments.
All state is lost on process restart; use ``DatabaseQuotaBackend`` for
production deployments that require persistence across restarts.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

from quadkit.ai.llm.routing.backends._time import end_of_utc_day
from quadkit.ai.llm.routing.types import ProviderUsage
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

__all__ = ["InMemoryQuotaBackend"]


class InMemoryQuotaBackend:
    """Thread-safe in-memory quota backend using asyncio locks.

    Quota state is keyed on ``(provider, date)`` and resets automatically
    across UTC midnight boundaries — no cron job required.

    Example:
        >>> backend = InMemoryQuotaBackend()
        >>> await backend.increment("groq")
        >>> await backend.is_exhausted("groq")
        False
        >>> await backend.mark_exhausted("groq")
        >>> await backend.is_exhausted("groq")
        True
    """

    def __init__(self) -> None:
        """Initialise an empty in-memory quota backend."""
        self._lock = asyncio.Lock()
        # Keys: (provider, date_str); values: ProviderUsage
        self._store: dict[tuple[str, str], ProviderUsage] = {}

    def _today(self) -> str:
        """Return today's UTC date as an ISO 8601 string."""
        return date.today().isoformat()

    def _get_or_create(self, provider: str) -> ProviderUsage:
        """Return (or create) today's usage record for *provider*.

        Must be called while holding ``self._lock``.

        Args:
            provider: Provider name.

        Returns:
            Mutable :class:`ProviderUsage` for today.
        """
        today = self._today()
        key = (provider, today)
        if key not in self._store:
            self._store[key] = ProviderUsage(
                provider=provider,
                usage_date=today,
            )
        return self._store[key]

    async def is_exhausted(self, provider: str) -> bool:
        """Return ``True`` when *provider* is quota-exhausted today.

        Args:
            provider: Provider name.

        Returns:
            Whether the provider is currently exhausted.
        """
        async with self._lock:
            record = self._store.get((provider, self._today()))
            if record is None or record.exhausted_until is None:
                return False
            return datetime.now(UTC) < record.exhausted_until

    async def increment(self, provider: str) -> None:
        """Record one successful completion for *provider* today.

        Args:
            provider: Provider name.
        """
        async with self._lock:
            record = self._get_or_create(provider)
            record.success_count += 1

    async def mark_exhausted(
        self, provider: str, *, until: datetime | None = None
    ) -> None:
        """Mark *provider* exhausted until *until*.

        Args:
            provider: Cascade-entry key (``name:model``) or provider name.
            until: Exhaustion expiry; ``None`` means the rest of today (UTC).
        """
        expiry = until or end_of_utc_day()
        async with self._lock:
            record = self._get_or_create(provider)
            record.is_exhausted = True
            record.exhausted_until = expiry
            logger.info(
                "llm.quota.memory: %s marked exhausted until %s",
                provider,
                expiry.isoformat(),
            )

    async def record_error(self, provider: str) -> None:
        """Record a non-exhaustion error for *provider* today.

        Args:
            provider: Provider name.
        """
        async with self._lock:
            record = self._get_or_create(provider)
            record.error_count += 1

    async def get_usage(self, provider: str) -> ProviderUsage | None:
        """Return today's usage record for *provider*.

        Args:
            provider: Provider name.

        Returns:
            :class:`ProviderUsage` or ``None`` if no activity recorded today.
        """
        async with self._lock:
            return self._store.get((provider, self._today()))

    async def get_all_usage(self) -> list[ProviderUsage]:
        """Return all today's usage records.

        Returns:
            List of :class:`ProviderUsage` for every provider active today.
        """
        today = self._today()
        async with self._lock:
            return [
                record
                for (provider, date_str), record in self._store.items()
                if date_str == today
            ]
