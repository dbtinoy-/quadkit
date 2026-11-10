"""Delivery-state stores for the framework-owned notification outbox.

- :class:`MemoryDeliveryStore` is intended for tests and local development.
- :class:`SqlDeliveryStore` persists outbox records and attempts through the
  injected :class:`DatabaseProviderProtocol`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import Any

from quadkit.contracts.data.sql.database import (
    DatabaseProviderProtocol,
    provider_dialect,
)
from quadkit.contracts.mailer.types import EmailMessage
from quadkit.contracts.notification.delivery import (
    DeliveryRecord,
    DeliveryStatus,
)
from quadkit.contracts.notification.types import DeliveryMessage
from quadkit.identity import ambient as identity
from quadkit.logging import get_logger
from quadkit.notification.dialect import translate_placeholders
from quadkit.primitives import clock

logger = get_logger(__name__)


def _utc_timestamp(value: Any) -> datetime | None:
    """Restore native SQL naive-UTC timestamps and normalize aware driver values."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


_DEFAULT_TABLE = "notification_delivery_state"
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table} (
    delivery_id TEXT        PRIMARY KEY,
    channel     TEXT        NOT NULL DEFAULT 'email',
    recipient   TEXT        NOT NULL DEFAULT '',
    subject     TEXT        NOT NULL DEFAULT '',
    body        TEXT        NOT NULL DEFAULT '',
    status      TEXT        NOT NULL DEFAULT 'pending',
    attempts    INTEGER     NOT NULL DEFAULT 0,
    last_error  TEXT        NOT NULL DEFAULT '',
    message     JSONB       NOT NULL DEFAULT '{{}}',
    created_at  TIMESTAMPTZ NOT NULL,
    retry_after TIMESTAMPTZ,
    lease_until TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS {table}_status_idx ON {table} (status, retry_after);
CREATE TABLE IF NOT EXISTS {table}_attempts (
    delivery_id    TEXT        NOT NULL,
    recipient      TEXT        NOT NULL DEFAULT '',
    subject        TEXT        NOT NULL DEFAULT '',
    attempt_number INTEGER     NOT NULL,
    attempted_at   TIMESTAMPTZ NOT NULL,
    outcome        TEXT        NOT NULL DEFAULT 'started',
    error          TEXT        NOT NULL DEFAULT '',
    PRIMARY KEY (delivery_id, attempt_number)
);
"""

_ATTEMPT_COLUMNS = {
    "outcome": "TEXT NOT NULL DEFAULT 'started'",
    "error": "TEXT NOT NULL DEFAULT ''",
}
_STATE_COLUMNS = {
    "channel": "TEXT NOT NULL DEFAULT 'email'",
    "lease_until": "TIMESTAMPTZ",
    "delivered_at": "TIMESTAMPTZ",
}


def _normalize_message(message: DeliveryMessage | EmailMessage) -> DeliveryMessage:
    """Convert mailer values into the durable channel-neutral envelope."""
    if isinstance(message, DeliveryMessage):
        return message
    return DeliveryMessage(
        channel="email",
        recipient=", ".join(message.to),
        subject=message.subject,
        body=message.body,
        metadata={
            "email": {
                "html_body": message.html_body,
                "from_email": message.from_email,
                "from_name": message.from_name,
                "reply_to": message.reply_to,
                "cc": list(message.cc),
                "bcc": list(message.bcc),
                "headers": dict(message.headers),
            }
        },
    )


def _record_from_state(state: dict[str, Any]) -> DeliveryRecord:
    """Build a typed record from a store's normalized state mapping."""
    return DeliveryRecord(
        delivery_id=str(state["delivery_id"]),
        message=DeliveryMessage(
            channel=str(state.get("channel") or "email"),
            recipient=str(state.get("recipient") or ""),
            subject=str(state.get("subject") or ""),
            body=str(state.get("body") or ""),
            metadata=dict(state.get("metadata") or {}),
        ),
        status=DeliveryStatus(str(state.get("status") or "pending")),
        attempts=int(state.get("attempts") or 0),
        created_at=state.get("created_at") or clock.now(),
        retry_after=state.get("retry_after"),
        last_error=str(state.get("last_error") or ""),
    )


class MemoryDeliveryStore:
    """In-process :class:`DeliveryStoreProtocol` for tests and development."""

    def __init__(self) -> None:
        """Initialize empty delivery and attempt state."""
        self._state: dict[str, dict[str, Any]] = {}
        self._attempts: dict[str, list[dict[str, Any]]] = {}

    async def create_pending(self, message: DeliveryMessage | EmailMessage) -> str:
        """Persist a new pending delivery in memory."""
        delivery = _normalize_message(message)
        delivery_id = identity.new_uuid()
        self._state[delivery_id] = {
            "delivery_id": delivery_id,
            "channel": delivery.channel,
            "recipient": delivery.recipient,
            "subject": delivery.subject,
            "body": delivery.body,
            "metadata": dict(delivery.metadata),
            "status": DeliveryStatus.PENDING.value,
            "attempts": 0,
            "last_error": "",
            "created_at": clock.now(),
            "retry_after": None,
            "lease_until": None,
            "delivered_at": None,
        }
        return delivery_id

    async def due_deliveries(self, limit: int = 50) -> list[DeliveryRecord]:
        """Return eligible rows in creation order, including expired leases."""
        now = clock.now()
        due = [
            entry
            for entry in self._state.values()
            if (
                entry["status"]
                in (DeliveryStatus.PENDING.value, DeliveryStatus.RETRYING.value)
                and (entry["retry_after"] is None or entry["retry_after"] <= now)
            )
            or (
                entry["status"] == DeliveryStatus.PROCESSING.value
                and entry["lease_until"] is not None
                and entry["lease_until"] <= now
            )
        ]
        due.sort(key=lambda entry: entry["created_at"])
        return [_record_from_state(dict(entry)) for entry in due[:limit]]

    async def get_delivery(self, delivery_id: str) -> DeliveryRecord | None:
        """Return one persisted delivery by identifier, if present."""
        entry = self._state.get(delivery_id)
        return _record_from_state(dict(entry)) if entry is not None else None

    async def claim_delivery(
        self, delivery_id: str, lease_seconds: float = 300.0
    ) -> bool:
        """Lease one due row; no await occurs between check and state update."""
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        entry = self._state.get(delivery_id)
        if entry is None:
            return False
        now = clock.now()
        is_due = (
            entry["status"]
            in (DeliveryStatus.PENDING.value, DeliveryStatus.RETRYING.value)
            and (entry["retry_after"] is None or entry["retry_after"] <= now)
        ) or (
            entry["status"] == DeliveryStatus.PROCESSING.value
            and entry["lease_until"] is not None
            and entry["lease_until"] <= now
        )
        if not is_due:
            return False
        entry["status"] = DeliveryStatus.PROCESSING.value
        entry["lease_until"] = now + timedelta(seconds=lease_seconds)
        return True

    async def record_attempt(
        self, delivery_id: str, recipient: str, subject: str, attempt_number: int
    ) -> None:
        """Record one attempt and monotonically update the attempt counter."""
        attempts = self._attempts.setdefault(delivery_id, [])
        attempts.append(
            {
                "recipient": recipient,
                "subject": subject,
                "attempt_number": attempt_number,
                "attempted_at": clock.now(),
                "outcome": "started",
                "error": "",
            }
        )
        entry = self._state.get(delivery_id)
        if entry is not None:
            entry["attempts"] = max(int(entry["attempts"]), attempt_number)

    async def complete_attempt(
        self,
        delivery_id: str,
        attempt_number: int,
        outcome: str,
        error: str = "",
    ) -> None:
        """Attach the transport outcome to a recorded attempt."""
        for attempt in self._attempts.get(delivery_id, []):
            if attempt["attempt_number"] == attempt_number:
                attempt["outcome"] = outcome
                attempt["error"] = error
                entry = self._state.get(delivery_id)
                if entry is not None and outcome == "failed":
                    entry["last_error"] = error
                return

    async def mark_delivered(self, delivery_id: str) -> None:
        """Mark a delivery as accepted by its backend."""
        entry = self._state.get(delivery_id)
        if entry is not None:
            entry["status"] = DeliveryStatus.DELIVERED.value
            entry["delivered_at"] = clock.now()
            entry["retry_after"] = None
            entry["lease_until"] = None

    async def schedule_retry(self, delivery_id: str, delay_seconds: float) -> None:
        """Schedule a transient failure for a later worker pass."""
        entry = self._state.get(delivery_id)
        if entry is not None:
            entry["status"] = DeliveryStatus.RETRYING.value
            entry["retry_after"] = clock.now() + timedelta(seconds=delay_seconds)
            entry["lease_until"] = None

    async def mark_failed(
        self, delivery_id: str, reason: str = "", final: bool = True
    ) -> None:
        """Move a delivery into the terminal dead-letter state."""
        del final
        entry = self._state.get(delivery_id)
        if entry is not None:
            entry["status"] = DeliveryStatus.FAILED.value
            entry["last_error"] = reason
            entry["retry_after"] = None
            entry["lease_until"] = None


class SqlDeliveryStore:
    """SQL-backed :class:`DeliveryStoreProtocol` implementation.

    Statements use qmark placeholders and are translated for the injected
    provider's dialect. Existing mail-tracking tables are upgraded in place so
    the same provider-owned store can become the channel-neutral outbox.

    Args:
        db: Database provider injected through DI.
        table: Backing table; defaults to ``notification_delivery_state``.
    """

    def __init__(
        self,
        db: DatabaseProviderProtocol,
        *,
        table: str = _DEFAULT_TABLE,
    ) -> None:
        """Initialize the store and validate its configured table identifier."""
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            raise ValueError(f"invalid delivery table name: {table!r}")
        self._db = db
        self._table = table
        self._initialized = False

    def _sql(self, sql: str) -> str:
        """Translate qmark placeholders to the provider's dialect style."""
        return translate_placeholders(sql, provider_dialect(self._db))

    @staticmethod
    def _assert_success(result: Any, operation: str) -> None:
        """Raise when a provider reports a failed operation as a result value."""
        if getattr(result, "success", True) is False:
            error = getattr(result, "error_message", None) or getattr(
                result, "error", None
            )
            raise RuntimeError(
                f"delivery store {operation} failed: {error or 'unknown error'}"
            )

    @classmethod
    def _assert_affected(cls, result: Any, operation: str) -> None:
        """Raise when a successful write matched no persisted delivery row."""
        cls._assert_success(result, operation)
        affected_rows = getattr(result, "affected_rows", None)
        if affected_rows is not None and int(affected_rows) == 0:
            raise RuntimeError(f"delivery store {operation} affected no rows")

    async def _column_names(self, table: str) -> set[str]:
        """Read a table's columns on SQLite or PostgreSQL."""
        dialect = provider_dialect(self._db)
        if dialect == "sqlite":
            result = await self._db.execute_query(f"PRAGMA table_info({table})")
            self._assert_success(result, "inspect schema")
            return {str(row["name"]) for row in getattr(result, "rows", [])}
        result = await self._db.execute_query(
            self._sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = ? AND table_schema = current_schema()"
            ),
            [table],
        )
        self._assert_success(result, "inspect schema")
        return {str(row["column_name"]) for row in getattr(result, "rows", [])}

    async def initialize(self) -> None:
        """Ensure queue schema; call outside business transactions at startup.

        Lazy callers remain supported. Schema created in an outer transaction
        is not cached as durable: rollback must not poison this store instance.
        """
        await self._ensure_table()

    async def _ensure_table(self) -> None:
        """Create or upgrade the delivery and attempt tables idempotently."""
        if self._initialized:
            return
        for statement in _CREATE_TABLE_SQL.format(table=self._table).split(";"):
            if statement.strip():
                result = await self._db.execute_query(statement)
                self._assert_success(result, "create schema")

        state_columns = await self._column_names(self._table)
        for name, definition in _STATE_COLUMNS.items():
            if name not in state_columns:
                result = await self._db.execute_query(
                    f"ALTER TABLE {self._table} ADD COLUMN {name} {definition}"
                )
                self._assert_success(result, f"add {self._table}.{name}")

        attempts_table = f"{self._table}_attempts"
        attempt_columns = await self._column_names(attempts_table)
        for name, definition in _ATTEMPT_COLUMNS.items():
            if name not in attempt_columns:
                result = await self._db.execute_query(
                    f"ALTER TABLE {attempts_table} ADD COLUMN {name} {definition}"
                )
                self._assert_success(result, f"add {attempts_table}.{name}")
        from quadkit.contracts.data.sql.committed_reads import (
            CommittedReadGuardProtocol,
            CommittedReadState,
        )

        # DDL may still belong to an outer business UOW and be rolled back.
        # Unknown/unobservable adapters cannot certify a durable schema cache.
        self._initialized = (
            isinstance(self._db, CommittedReadGuardProtocol)
            and self._db.supports_committed_read_guard_v1 is True
            and self._db.committed_read_state() == CommittedReadState.SAFE
        )

    @staticmethod
    def _row_to_record(row: Any) -> DeliveryRecord:
        """Normalize a driver row into the public channel-neutral record."""
        raw_message = row.get("message") or {}
        if isinstance(raw_message, str):
            from quadkit import serialization

            try:
                raw_message = serialization.loads(raw_message)
            except (TypeError, ValueError, UnicodeDecodeError):
                logger.warning(
                    "delivery_store_invalid_payload",
                    delivery_id=row.get("delivery_id"),
                )
                raw_message = {}
        if not isinstance(raw_message, dict):
            raw_message = {}
        metadata = raw_message.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        from datetime import UTC, datetime

        created_at = row.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = None
        if isinstance(created_at, datetime):
            created_at = (
                created_at.replace(tzinfo=UTC)
                if created_at.tzinfo is None
                else created_at.astimezone(UTC)
            )
        retry_after = row.get("retry_after")
        if isinstance(retry_after, str):
            try:
                retry_after = datetime.fromisoformat(retry_after)
            except ValueError:
                retry_after = None
        if isinstance(retry_after, datetime):
            retry_after = (
                retry_after.replace(tzinfo=UTC)
                if retry_after.tzinfo is None
                else retry_after.astimezone(UTC)
            )
        status = str(row.get("status") or DeliveryStatus.PENDING.value)
        return DeliveryRecord(
            delivery_id=str(row["delivery_id"]),
            message=DeliveryMessage(
                channel=str(
                    row.get("channel") or raw_message.get("channel") or "email"
                ),
                recipient=str(row.get("recipient") or ""),
                subject=str(row.get("subject") or raw_message.get("subject") or ""),
                body=str(row.get("body") or raw_message.get("body") or ""),
                metadata=metadata,
            ),
            status=DeliveryStatus(status),
            attempts=int(row.get("attempts") or 0),
            created_at=created_at or clock.now(),
            retry_after=retry_after,
            last_error=str(row.get("last_error") or ""),
        )

    async def create_pending(self, message: DeliveryMessage | EmailMessage) -> str:
        """Insert a pending outbox row and return its identifier."""
        await self._ensure_table()
        delivery = _normalize_message(message)
        delivery_id = identity.new_uuid()
        result = await self._db.execute_insert(
            self._table,
            {
                "delivery_id": delivery_id,
                "channel": delivery.channel,
                "recipient": delivery.recipient,
                "subject": delivery.subject,
                "body": delivery.body,
                "status": DeliveryStatus.PENDING.value,
                "attempts": 0,
                "last_error": "",
                "message": {"metadata": delivery.metadata},
                "created_at": clock.now(),
            },
        )
        self._assert_affected(result, "create pending delivery")
        return delivery_id

    async def due_deliveries(self, limit: int = 50) -> list[DeliveryRecord]:
        """Fetch due rows and expired leases in FIFO order."""
        await self._ensure_table()
        now = clock.now()
        result = await self._db.execute_query(
            self._sql(
                f"SELECT * FROM {self._table} WHERE "
                "((status IN ('pending', 'retrying')) "
                "AND (retry_after IS NULL OR retry_after <= ?)) "
                "OR (status = 'processing' AND lease_until IS NOT NULL "
                "AND lease_until <= ?) "
                "ORDER BY created_at ASC LIMIT ?"
            ),
            [now, now, max(0, int(limit))],
        )
        self._assert_success(result, "list due deliveries")
        return [self._row_to_record(row) for row in getattr(result, "rows", [])]

    async def get_delivery(self, delivery_id: str) -> DeliveryRecord | None:
        """Read one delivery and its persisted channel-neutral envelope."""
        await self._ensure_table()
        result = await self._db.execute_query(
            self._sql(f"SELECT * FROM {self._table} WHERE delivery_id = ?"),
            [delivery_id],
        )
        self._assert_success(result, "get delivery")
        rows = getattr(result, "rows", [])
        return self._row_to_record(rows[0]) if rows else None

    async def claim_delivery(
        self, delivery_id: str, lease_seconds: float = 300.0
    ) -> bool:
        """Atomically claim a due delivery using a conditional update."""
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        await self._ensure_table()
        now = clock.now()
        result = await self._db.execute_update(
            self._table,
            {
                "status": DeliveryStatus.PROCESSING.value,
                "lease_until": now + timedelta(seconds=lease_seconds),
            },
            self._sql(
                "delivery_id = ? AND (((status IN ('pending', 'retrying')) "
                "AND (retry_after IS NULL OR retry_after <= ?)) "
                "OR (status = 'processing' AND lease_until IS NOT NULL "
                "AND lease_until <= ?))"
            ),
            [delivery_id, now, now],
        )
        self._assert_success(result, "claim delivery")
        return int(getattr(result, "affected_rows", 0)) > 0

    async def record_attempt(
        self, delivery_id: str, recipient: str, subject: str, attempt_number: int
    ) -> None:
        """Persist an attempt row and update the delivery attempt counter."""
        await self._ensure_table()
        async with self._db.transaction():
            inserted = await self._db.execute_insert(
                f"{self._table}_attempts",
                {
                    "delivery_id": delivery_id,
                    "recipient": recipient,
                    "subject": subject,
                    "attempt_number": attempt_number,
                    "attempted_at": clock.now(),
                    "outcome": "started",
                    "error": "",
                },
            )
            self._assert_affected(inserted, "insert attempt")
            result = await self._db.execute_update(
                self._table,
                {"attempts": attempt_number},
                self._sql("delivery_id = ? AND attempts < ?"),
                [delivery_id, attempt_number],
            )
            self._assert_affected(result, "record attempt")

    async def complete_attempt(
        self,
        delivery_id: str,
        attempt_number: int,
        outcome: str,
        error: str = "",
    ) -> None:
        """Persist the transport outcome for one attempt-history row."""
        await self._ensure_table()
        async with self._db.transaction():
            result = await self._db.execute_update(
                f"{self._table}_attempts",
                {"outcome": outcome, "error": error},
                self._sql("delivery_id = ? AND attempt_number = ?"),
                [delivery_id, attempt_number],
            )
            self._assert_affected(result, "complete attempt")
            if outcome == "failed":
                state_result = await self._db.execute_update(
                    self._table,
                    {"last_error": error},
                    self._sql("delivery_id = ?"),
                    [delivery_id],
                )
                self._assert_affected(state_result, "persist last delivery error")

    async def mark_delivered(self, delivery_id: str) -> None:
        """Mark a delivery as accepted and release its lease."""
        await self._ensure_table()
        result = await self._db.execute_update(
            self._table,
            {
                "status": DeliveryStatus.DELIVERED.value,
                "delivered_at": clock.now(),
                "retry_after": None,
                "lease_until": None,
            },
            self._sql("delivery_id = ?"),
            [delivery_id],
        )
        self._assert_affected(result, "mark delivered")

    async def schedule_retry(self, delivery_id: str, delay_seconds: float) -> None:
        """Set retry state, next eligibility and release the current lease."""
        await self._ensure_table()
        result = await self._db.execute_update(
            self._table,
            {
                "status": DeliveryStatus.RETRYING.value,
                "retry_after": clock.now() + timedelta(seconds=delay_seconds),
                "lease_until": None,
            },
            self._sql("delivery_id = ?"),
            [delivery_id],
        )
        self._assert_affected(result, "schedule retry")

    async def mark_failed(
        self, delivery_id: str, reason: str = "", final: bool = True
    ) -> None:
        """Move an exhausted or invalid message to terminal dead-letter state."""
        del final
        await self._ensure_table()
        result = await self._db.execute_update(
            self._table,
            {
                "status": DeliveryStatus.FAILED.value,
                "last_error": reason,
                "retry_after": None,
                "lease_until": None,
            },
            self._sql("delivery_id = ?"),
            [delivery_id],
        )
        self._assert_affected(result, "mark failed")


__all__ = ["MemoryDeliveryStore", "SqlDeliveryStore"]
