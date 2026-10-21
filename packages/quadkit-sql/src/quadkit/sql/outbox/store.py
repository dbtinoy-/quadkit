"""SQL-backed outbox store for transactional event delivery."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from quadkit.contracts.data.outbox import OutboxStoreProtocol
from quadkit.contracts.domain.events import DomainEvent
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.serialization import dumps_str as json_dumps

if TYPE_CHECKING:
    from quadkit.contracts.core.identity import IdGeneratorProtocol

logger = get_logger(__name__)


class SQLOutboxStore:
    """SQL implementation of the transactional outbox.

    Args:
        db: Database provider for query execution.
        table: Outbox table name. Defaults to ``outbox_events``.

    The table must exist before use: call :meth:`create_table` once at
    startup (mirrors the admin audit store pattern) or create it yourself
    with at least the columns ``id``, ``event_type``, ``payload``,
    ``status``, ``created_at`` and ``error``.
    """

    def __init__(
        self,
        db: Any,
        table: str = "outbox_events",
        id_generator: IdGeneratorProtocol | None = None,
    ) -> None:
        self._db = db
        self._table = table
        self._id_generator = id_generator

    def bound(self, db: Any) -> SQLOutboxStore:
        """The same outbox over a different executor — the caller's transaction.

        A store is built once, at boot, over the application's database.
        The write that makes an outbox *transactional* has to happen on the
        connection that holds the business row, which is only known inside
        the transaction. ``store.bound(SessionExecutor(session))`` is how a
        service says "this table, this id generator, *that* transaction".
        """
        return SQLOutboxStore(db, table=self._table, id_generator=self._id_generator)

    async def create_table(self) -> None:
        """Create the outbox table if it does not already exist.

        Call once at application startup before appending events.
        """
        await self._db.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table} ("  # noqa: S608 -- self._table set at init (default "outbox_events")
            "id TEXT PRIMARY KEY, event_type TEXT NOT NULL, "
            "payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', "
            "created_at TEXT NOT NULL, error TEXT)"
        )
        logger.info("outbox_table_ensured", table=self._table)

    async def append_batch(self, events: list[DomainEvent]) -> None:
        """Write events to the outbox table inside the active transaction."""
        if not events:
            return
        for event in events:
            # The event's public representation, which ``from_dict`` can
            # rebuild on the other side; ``__dict__`` is whatever the
            # instance happens to hold.
            payload = json_dumps(
                event.to_dict() if hasattr(event, "to_dict") else event.__dict__
            )
            event_id = (
                str(self._id_generator.generate())
                if self._id_generator
                else str(uuid.uuid4())
            )
            created_at = ambient_clock.now().isoformat()
            await self._db.execute(
                f"INSERT INTO {self._table} (id, event_type, payload, status, created_at) "  # noqa: S608 -- self._table set at init (default "outbox_events"), values parameterized
                "VALUES (:id, :event_type, :payload, 'pending', :created_at)",
                {
                    "id": event_id,
                    "event_type": type(event).__name__,
                    "payload": payload,
                    "created_at": created_at,
                },
            )
        logger.debug("outbox_events_written", count=len(events))

    async def fetch_pending(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch undelivered outbox events ordered by creation time."""
        rows = await self._db.fetch_all(
            f"SELECT id, event_type, payload, status, created_at FROM {self._table} "  # noqa: S608 -- self._table set at init (default "outbox_events"), values parameterized
            "WHERE status = 'pending' ORDER BY created_at ASC LIMIT :limit",
            {"limit": limit},
        )
        return [dict(row) for row in rows]

    async def mark_delivered(self, event_id: str) -> None:
        """Mark an outbox event as delivered."""
        await self._db.execute(
            f"UPDATE {self._table} SET status = 'delivered' WHERE id = :id",  # noqa: S608 -- self._table set at init (default "outbox_events"), values parameterized
            {"id": event_id},
        )

    async def mark_failed(self, event_id: str, error: str = "") -> None:
        """Mark an outbox event as permanently failed."""
        await self._db.execute(
            f"UPDATE {self._table} SET status = 'failed', error = :error WHERE id = :id",  # noqa: S608 -- self._table set at init (default "outbox_events"), values parameterized
            {"id": event_id, "error": error},
        )


__all__ = ["SQLOutboxStore"]

# Verify protocol compliance at import time (fails fast if signature drifts)
_: OutboxStoreProtocol = SQLOutboxStore.__new__(SQLOutboxStore)
