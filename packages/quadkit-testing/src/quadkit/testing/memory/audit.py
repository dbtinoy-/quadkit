"""In-memory audit logger for development and testing.

Provides a :class:`~quadkit.contracts.audit.AuditLoggerProtocol`-compatible
implementation that retains audit entries in a bounded :class:`collections.deque`.
Intended for unit tests and local development; swap in a database-backed
logger for production use.
"""

from __future__ import annotations

import asyncio
from collections import deque

from quadkit.contracts.audit import AuditEntry, AuditLoggerProtocol, AuditQuery
from quadkit.logging import get_logger

logger = get_logger(__name__)


class InMemoryAuditLogger(AuditLoggerProtocol):
    """In-memory implementation of :class:`AuditLoggerProtocol`.

    Retains up to *max_entries* most recent audit entries in a deque.
    All writes are serialised via an ``asyncio.Lock``; reads acquire no lock
    for performance (safe for single event loop usage).

    Args:
        max_entries: Maximum capacity of the entry buffer. Oldest entries
            are dropped when the buffer is full. Defaults to ``10_000``.

    Example::

        audit = InMemoryAuditLogger(max_entries=500)
        await audit.log(
            AuditEntry(action="user.login", actor_id="u-123", outcome="success")
        )
        recent = await audit.query(actor_id="u-123", limit=10)
    """

    def __init__(self, max_entries: int = 10_000) -> None:
        self._entries: deque[AuditEntry] = deque(maxlen=max_entries)
        self._lock = asyncio.Lock()

    # -- AuditLoggerProtocol --

    async def log(self, entry: AuditEntry) -> None:
        """Append an audit entry to the buffer.

        Args:
            entry: The audit event to record.
        """
        async with self._lock:
            self._entries.append(entry)
        logger.debug(
            "audit.log",
            action=entry.action,
            actor=entry.actor_id,
            resource=entry.resource_type,
            outcome=entry.outcome,
        )

    async def query(
        self,
        query: AuditQuery,
    ) -> list[AuditEntry]:
        """Return audit entries matching all provided filters, newest-first.

        Args:
            query: Filter criteria encapsulated in an AuditQuery object.

        Returns:
            List of matching AuditEntry objects, newest-first.
        """
        results: list[AuditEntry] = []
        for entry in reversed(self._entries):
            if query.actor_id is not None and entry.actor_id != query.actor_id:
                continue
            if query.action is not None and entry.action != query.action:
                continue
            if (
                query.resource_type is not None
                and entry.resource_type != query.resource_type
            ):
                continue
            if query.resource_id is not None and entry.resource_id != query.resource_id:
                continue
            if query.source is not None and entry.source != query.source:
                continue
            if query.severity is not None and entry.severity != query.severity:
                continue
            if query.outcome is not None and entry.outcome != query.outcome:
                continue
            if query.since is not None and entry.occurred_at < query.since:
                continue
            if query.until is not None and entry.occurred_at > query.until:
                continue
            results.append(entry)
            if len(results) >= query.offset + query.limit:
                break
        return results[query.offset : query.offset + query.limit]

    # -- Extended helpers --

    async def clear(self) -> None:
        """Remove all stored audit entries (useful for test teardown)."""
        async with self._lock:
            self._entries.clear()

    async def count(self) -> int:
        """Return the number of currently stored audit entries.

        Returns:
            Count of entries in the buffer.
        """
        return len(self._entries)

    async def all(self) -> list[AuditEntry]:
        """Return all stored entries, oldest-first.

        Returns:
            List of all audit entries in chronological order.
        """
        return list(self._entries)


__all__ = ["InMemoryAuditLogger"]
