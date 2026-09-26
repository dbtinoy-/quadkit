"""DLQ backend protocol and implementations for Dead Letter Queue storage.

This module provides the backend abstraction that allows ``DeadLetterQueue``
to persist failed job records beyond process restarts.

Available backends:

- :class:`InMemoryDLQBackend` — default, process-local, no persistence
- :class:`StateStoreDLQBackend` — persistent, uses any :class:`~quadkit.contracts.StateStoreProtocol`

Example (persistent DLQ with Redis)::

    from quadkit.tasks.dlq.backend import StateStoreDLQBackend
    from quadkit.tasks.dlq.persistent import PersistentDeadLetterQueue

    backend = StateStoreDLQBackend(state_store=redis_state_store)
    dlq = PersistentDeadLetterQueue(backend=backend)

    await dlq.add(job, error="timeout")
    records = await dlq.list_failed(limit=10)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit import serialization as json

if TYPE_CHECKING:
    from quadkit.contracts import StateStoreProtocol

__all__ = [
    "DLQBackend",
    "InMemoryDLQBackend",
    "StateStoreDLQBackend",
]

_DLQ_KEY_PREFIX = "dlq:"
_DLQ_INDEX_KEY = "dlq:__index__"


@runtime_checkable
class DLQBackend(Protocol):
    """Protocol for Dead Letter Queue storage backends.

    Implement this to enable persistent Dead Letter Queue storage
    across process restarts and multiple nodes.
    """

    async def add(self, record_id: str, record_data: dict[str, Any]) -> None:
        """Persist a failure record.

        Args:
            record_id: Unique identifier (job ID).
            record_data: SerializableProtocol dict representation of the record.
        """
        ...

    async def get(self, record_id: str) -> dict[str, Any] | None:
        """Retrieve a single failure record by ID.

        Args:
            record_id: Unique identifier (job ID).

        Returns:
            Record dict if found, otherwise ``None``.
        """
        ...

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all stored failure records (newest-first ordering optional).

        Returns:
            List of record dicts.
        """
        ...

    async def remove(self, record_id: str) -> bool:
        """Delete a failure record.

        Args:
            record_id: Unique identifier (job ID).

        Returns:
            ``True`` if the record existed and was removed, ``False`` otherwise.
        """
        ...

    async def clear(self) -> int:
        """Delete all failure records.

        Returns:
            Number of records deleted.
        """
        ...


class InMemoryDLQBackend:
    """In-memory DLQ backend. Data is lost when the process exits."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}

    async def add(self, record_id: str, record_data: dict[str, Any]) -> None:
        """Store a failure record in memory."""
        self._records[record_id] = record_data

    async def get(self, record_id: str) -> dict[str, Any] | None:
        """Return a stored failure record or ``None``."""
        return self._records.get(record_id)

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all records in insertion order."""
        return list(self._records.values())

    async def remove(self, record_id: str) -> bool:
        """Remove and return whether the record existed."""
        return self._records.pop(record_id, None) is not None

    async def clear(self) -> int:
        """Remove all records and return the count removed."""
        count = len(self._records)
        self._records.clear()
        return count


class StateStoreDLQBackend:
    """Persistent DLQ backend backed by a :class:`~quadkit.contracts.StateStoreProtocol`.

    Serialises each :class:`~quadkit.tasks.dlq.core.FailureRecord` as JSON and
    stores it under the key ``"dlq:<job_id>"``.  A separate index key
    ``"dlq:__index__"`` keeps an ordered list of record IDs so that
    :meth:`list_all` can reconstruct insertion order without a full-scan.

    Example::

        backend = StateStoreDLQBackend(state_store=redis_state_store)
        dlq = PersistentDeadLetterQueue(backend=backend)

    Args:
        state_store: Any :class:`~quadkit.contracts.StateStoreProtocol` implementation
            (e.g. Redis-backed).
        ttl: Time-to-live for each record in seconds. Defaults to 7 days.
            Set to ``None`` to disable expiry.
    """

    def __init__(
        self,
        state_store: StateStoreProtocol,
        ttl: int | None = 604_800,  # 7 days
    ) -> None:
        self._store = state_store
        self._ttl = ttl

    def _record_key(self, record_id: str) -> str:
        return f"{_DLQ_KEY_PREFIX}{record_id}"

    async def _load_index(self) -> list[str]:
        raw = await self._store.get(_DLQ_INDEX_KEY)
        if raw is None:
            return []
        parsed: list[str] = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        return parsed

    async def _save_index(self, index: list[str]) -> None:
        await self._store.set(_DLQ_INDEX_KEY, json.dumps(index), self._ttl)

    async def add(self, record_id: str, record_data: dict[str, Any]) -> None:
        """Persist a failure record and update the index."""
        await self._store.set(
            self._record_key(record_id), json.dumps(record_data), self._ttl
        )
        index = await self._load_index()
        if record_id not in index:
            index.append(record_id)
            await self._save_index(index)

    async def get(self, record_id: str) -> dict[str, Any] | None:
        """Retrieve a single failure record."""
        raw = await self._store.get(self._record_key(record_id))
        if raw is None:
            return None
        parsed: dict[str, Any] | None = (
            json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        )
        return parsed

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all stored failure records in insertion order."""
        index = await self._load_index()
        records = []
        for record_id in index:
            record = await self.get(record_id)
            if record is not None:
                records.append(record)
        return records

    async def remove(self, record_id: str) -> bool:
        """Remove a failure record and update the index."""
        raw = await self._store.get(self._record_key(record_id))
        if raw is None:
            return False
        await self._store.delete(self._record_key(record_id))
        index = await self._load_index()
        if record_id in index:
            index.remove(record_id)
            await self._save_index(index)
        return True

    async def clear(self) -> int:
        """Remove all DLQ records from the store."""
        index = await self._load_index()
        count = 0
        for record_id in index:
            await self._store.delete(self._record_key(record_id))
            count += 1
        await self._store.delete(_DLQ_INDEX_KEY)
        return count
