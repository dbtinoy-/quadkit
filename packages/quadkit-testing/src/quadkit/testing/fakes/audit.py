"""Fake audit logger implementation for testing."""

from __future__ import annotations

from datetime import datetime

from quadkit.contracts.audit import (
    AuditEntry,
    AuditQuery,
)

__all__ = ["FakeAuditLogger"]


class FakeAuditLogger:
    """In-memory fake implementing AuditLoggerProtocol and AuditStoreProtocol.

    Exposes ``entries`` list for test assertions.

    Example::

        fake = FakeAuditLogger()
        await fake.log(AuditEntry(action="user.login", actor_id="u-1"))
        assert len(fake.entries) == 1
        assert fake.entries[0].action == "user.login"
    """

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    async def log(self, entry: AuditEntry) -> None:
        """Implement AuditLoggerProtocol.log."""
        self.entries.append(entry)

    async def query(self, query: AuditQuery) -> list[AuditEntry]:
        """Implement AuditLoggerProtocol.query — filter entries by query fields."""
        results: list[AuditEntry] = list(self.entries)
        if query.actor_id:
            results = [e for e in results if e.actor_id == query.actor_id]
        if query.action:
            results = [e for e in results if e.action == query.action]
        if query.resource_type:
            results = [e for e in results if e.resource_type == query.resource_type]
        if query.resource_id:
            results = [e for e in results if e.resource_id == query.resource_id]
        if query.severity:
            results = [e for e in results if e.severity == query.severity]
        if query.source:
            results = [e for e in results if e.source == query.source]
        if query.outcome:
            results = [e for e in results if e.outcome == query.outcome]
        if query.tenant_id:
            results = [e for e in results if e.tenant_id == query.tenant_id]
        if query.since:
            results = [e for e in results if e.occurred_at >= query.since]
        if query.until:
            results = [e for e in results if e.occurred_at <= query.until]
        results = list(reversed(results))
        return results[query.offset : query.offset + query.limit]

    async def append(self, entry: AuditEntry) -> None:
        """Implement AuditStoreProtocol.append."""
        self.entries.append(entry)

    async def count(self, query: AuditQuery) -> int:
        """Implement AuditStoreProtocol.count."""
        return len(await self.query(query))

    async def delete_expired(self, cutoff: datetime) -> int:
        """Implement AuditStoreProtocol.delete_expired."""
        expired: list[AuditEntry] = []
        for entry in self.entries:
            stamp = entry.metadata.get("__expires_at")
            if stamp is None:
                continue
            try:
                expires = datetime.fromisoformat(stamp)
            except (TypeError, ValueError):
                continue
            if expires <= cutoff:
                expired.append(entry)
        for entry in expired:
            self.entries.remove(entry)
        return len(expired)

    def clear(self) -> None:
        """Clear all entries (test helper)."""
        self.entries.clear()
