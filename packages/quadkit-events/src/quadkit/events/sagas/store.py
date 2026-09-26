"""SagaProtocol storage interfaces."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.events.sagas.types import SagaRecord


class SagaStore:
    """Abstract interface for persisting saga state."""

    async def save(self, record: SagaRecord) -> None:
        """Persist a saga record."""
        raise NotImplementedError

    async def load(self, saga_id: str) -> SagaRecord | None:
        """Load a saga record by ID."""
        raise NotImplementedError

    async def list_by_name(self, saga_name: str) -> list[SagaRecord]:
        """List all records for a saga name."""
        raise NotImplementedError

    async def delete(self, saga_id: str) -> bool:
        """Delete a saga record."""
        raise NotImplementedError


class InMemorySagaStore(SagaStore):
    """In-memory saga store for testing and single-node deployments."""

    def __init__(self) -> None:
        self._records: dict[str, SagaRecord] = {}

    async def save(self, record: SagaRecord) -> None:
        record.updated_at = datetime.now(UTC)
        self._records[record.saga_id] = record

    async def load(self, saga_id: str) -> SagaRecord | None:
        return self._records.get(saga_id)

    async def list_by_name(self, saga_name: str) -> list[SagaRecord]:
        return [r for r in self._records.values() if r.saga_name == saga_name]

    async def delete(self, saga_id: str) -> bool:
        return self._records.pop(saga_id, None) is not None

    def clear(self) -> None:
        """Clear all records (for testing)."""
        self._records.clear()
