"""Database-persisted inbox store implementation.

Uses :class:`~quadkit.contracts.data.sql.database.DatabaseProviderProtocol`
so the underlying engine (PostgreSQL, MySQL, SQLite …) is fully decoupled.
"""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.data.sql.database import (
    DatabaseProviderProtocol,
    provider_dialect,
)
from quadkit.contracts.mailer import MessageDeliveryReceipt
from quadkit.contracts.notification.inbox import InboxMessage
from quadkit.logging import get_logger
from quadkit.notification.dialect import translate_placeholders

logger = get_logger(__name__)

_DEFAULT_TABLE = "notification_inbox_messages"
_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _require_success(result: Any) -> None:
    """Do not turn a provider-reported database failure into success."""
    if getattr(result, "success", None) is not True:
        raise RuntimeError("inbox database operation failed")


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table} (
    id          TEXT        PRIMARY KEY,
    user_id     TEXT        NOT NULL,
    title       TEXT        NOT NULL,
    body        TEXT        NOT NULL,
    read        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL,
    metadata    JSONB       NOT NULL DEFAULT '{{}}'
);
CREATE INDEX IF NOT EXISTS {table}_user_created_idx
    ON {table} (user_id, created_at DESC);
"""


class DatabaseInboxStore:
    """SQL-backed :class:`InboxStoreProtocol` implementation.

    Reads and writes to a single flat table.  The table is created
    automatically on first use if it does not exist::

        CREATE TABLE notification_inbox_messages (
            id          TEXT        PRIMARY KEY,
            user_id     TEXT        NOT NULL,
            title       TEXT        NOT NULL,
            body        TEXT        NOT NULL,
            read        BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL,
            metadata    JSONB       NOT NULL DEFAULT '{}'
        );
        CREATE INDEX ON notification_inbox_messages (user_id, created_at DESC);

    Statements are written in the SQLite ``?`` placeholder style and
    translated per provider dialect (see ``quadkit.notification.dialect``);
    supported providers: SQLite and PostgreSQL.

    Args:
        db: Database provider injected via DI.
        table: Table name. Defaults to ``notification_inbox_messages``.
    """

    supports_inbox_send_once_v1: bool = True

    def __init__(
        self,
        db: DatabaseProviderProtocol,
        *,
        table: str = _DEFAULT_TABLE,
    ) -> None:
        if not isinstance(table, str) or not _TABLE_NAME.fullmatch(table):
            raise ValueError("inbox table must be a plain SQL identifier")
        self._db = db
        self._table = table

    def _sql(self, sql: str) -> str:
        """Translate ``?`` placeholders to the provider dialect style."""
        dialect = provider_dialect(self._db)
        return translate_placeholders(sql, dialect)

    # ------------------------------------------------------------------
    # InboxStoreProtocol implementation
    # ------------------------------------------------------------------

    async def _ensure_table(self) -> None:
        """Create the inbox table (and index) if it does not exist."""
        sql = _CREATE_TABLE_SQL.format(table=self._table)
        for statement in sql.split(";"):
            stmt = statement.strip()
            if stmt:
                _require_success(await self._db.execute_query(stmt))

    async def save(self, message: InboxMessage) -> None:
        """Persist *message* in the database.

        Args:
            message: The inbox message to store.
        """
        await self._ensure_table()
        result = await self._db.execute_insert(
            self._table,
            {
                "id": message.id,
                "user_id": message.user_id,
                "title": message.title,
                "body": message.body,
                "read": message.read,
                "created_at": message.created_at,
                "metadata": message.metadata,
            },
        )
        _require_success(result)
        logger.debug("inbox.db.saved", message_id=message.id, user_id=message.user_id)

    async def save_once(
        self, key: str, message: InboxMessage
    ) -> tuple[MessageDeliveryReceipt, bool]:
        """Commit one inbox insert and a content-free receipt atomically.

        Receipt IDs/timestamps/digests survive inbox deletion, not duplicate
        copies of body/metadata. Use only after the business transaction commits.
        """
        from quadkit.contracts.data.sql.committed_reads import (
            CommittedReadGuardProtocol,
            CommittedReadState,
        )
        from quadkit.notification.inbox.idempotency import fingerprint, validate_key

        validate_key(key)
        intent = fingerprint(message)
        if (
            not isinstance(self._db, CommittedReadGuardProtocol)
            or self._db.supports_committed_read_guard_v1 is not True
            or self._db.committed_read_state() != CommittedReadState.SAFE
        ):
            raise RuntimeError(
                "send_once requires a trusted committed-only database scope"
            )
        await self._ensure_table()
        _require_success(
            await self._db.execute_query(
                f"CREATE TABLE IF NOT EXISTS {self._table}_receipts (delivery_key TEXT PRIMARY KEY, payload_digest TEXT NOT NULL, message_id TEXT NOT NULL, created_at TEXT NOT NULL)"  # noqa: S608
            )
        )
        async with self._db.transaction():
            inserted = await self._db.execute_query(
                self._sql(
                    f"INSERT INTO {self._table}_receipts (delivery_key, payload_digest, message_id, created_at) VALUES (?, ?, ?, ?) ON CONFLICT (delivery_key) DO NOTHING RETURNING delivery_key"
                ),  # noqa: S608
                [key, intent, message.id, message.created_at.isoformat()],
            )
            _require_success(inserted)
            if inserted.rows:
                await self.save(message)
                return MessageDeliveryReceipt(
                    message.id, "inbox", "inbox", message.created_at
                ), True
            previous = await self._db.execute_query(
                self._sql(
                    f"SELECT payload_digest, message_id, created_at FROM {self._table}_receipts WHERE delivery_key = ?"
                ),  # noqa: S608
                [key],
            )
            _require_success(previous)
            if len(previous.rows) != 1:
                raise RuntimeError("inbox delivery receipt missing after conflict")
            row = previous.rows[0]
            if row["payload_digest"] != intent:
                raise ValueError("inbox delivery key conflicts with an existing intent")
            return MessageDeliveryReceipt(
                row["message_id"],
                "inbox",
                "inbox",
                datetime.fromisoformat(row["created_at"]),
            ), False

    async def get(self, message_id: str) -> InboxMessage | None:
        """Return the message with *message_id*, or ``None``.

        Args:
            message_id: ID to look up.
        """
        await self._ensure_table()
        result = await self._db.execute_query(
            self._sql(  # noqa: S608
                f"SELECT * FROM {self._table} WHERE id = ?"
            ),
            [message_id],
        )
        _require_success(result)
        if not result.rows:
            return None
        return self._row_to_message(result.rows[0])

    async def get_for_user(self, message_id: str, user_id: str) -> InboxMessage | None:
        """Fetch a message using an owner predicate in the database query.

        This optional store capability does not authenticate the caller. The
        ``user_id`` must still come from a trusted, verified identity.
        """
        await self._ensure_table()
        result = await self._db.execute_query(
            self._sql(  # noqa: S608 -- table identifier validated in __init__
                f"SELECT * FROM {self._table} WHERE id = ? AND user_id = ?"
            ),
            [message_id, user_id],
        )
        _require_success(result)
        if not result.rows:
            return None
        return self._row_to_message(result.rows[0])

    async def list_for_user(
        self,
        user_id: str,
        *,
        unread_only: bool = False,
    ) -> list[InboxMessage]:
        """Return messages for *user_id* in reverse-chronological order.

        Args:
            user_id: Filter to this user.
            unread_only: When ``True`` only unread messages are returned.
        """
        await self._ensure_table()
        if unread_only:
            result = await self._db.execute_query(
                self._sql(  # noqa: S608
                    f"SELECT * FROM {self._table}"
                    " WHERE user_id = ? AND read = FALSE"
                    " ORDER BY created_at DESC, id DESC"
                ),
                [user_id],
            )
        else:
            result = await self._db.execute_query(
                self._sql(  # noqa: S608
                    f"SELECT * FROM {self._table}"
                    " WHERE user_id = ?"
                    " ORDER BY created_at DESC, id DESC"
                ),
                [user_id],
            )
        _require_success(result)
        return [self._row_to_message(row) for row in result.rows]

    async def list_page_for_user(
        self,
        user_id: str,
        *,
        unread_only: bool = False,
        limit: int,
        offset: int,
    ) -> list[InboxMessage]:
        """Read a bounded page, filtered to a trusted recipient in SQL."""
        if limit < 1 or offset < 0:
            raise ValueError("limit must be positive and offset non-negative")
        await self._ensure_table()
        unread = " AND read = FALSE" if unread_only else ""
        query = self._sql(  # noqa: S608 -- identifier validated in __init__
            f"SELECT * FROM {self._table} WHERE user_id = ?{unread}"
            " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
        )
        result = await self._db.execute_query(query, [user_id, limit, offset])
        _require_success(result)
        return [self._row_to_message(row) for row in result.rows]

    async def mark_read(self, message_id: str, user_id: str) -> None:
        """Mark *message_id* as read, guarded by *user_id* ownership.

        Args:
            message_id: ID of the message to mark.
            user_id: Expected owner.
        """
        await self._ensure_table()
        result = await self._db.execute_update(
            self._table,
            {"read": True},
            self._sql("id = ? AND user_id = ?"),
            [message_id, user_id],
        )
        _require_success(result)
        logger.debug("inbox.db.marked_read", message_id=message_id, user_id=user_id)

    async def mark_all_read(self, user_id: str) -> None:
        """Mark every unread message for *user_id* as read.

        Args:
            user_id: Target user.
        """
        await self._ensure_table()
        result = await self._db.execute_update(
            self._table,
            {"read": True},
            self._sql("user_id = ? AND read = FALSE"),
            [user_id],
        )
        _require_success(result)
        logger.debug("inbox.db.all_marked_read", user_id=user_id)

    async def delete(self, message_id: str, user_id: str) -> None:
        """Delete *message_id*, guarded by *user_id* ownership.

        Args:
            message_id: ID to remove.
            user_id: Expected owner.
        """
        await self._ensure_table()
        result = await self._db.execute_delete(
            self._table,
            self._sql("id = ? AND user_id = ?"),
            [message_id, user_id],
        )
        _require_success(result)
        logger.debug("inbox.db.deleted", message_id=message_id, user_id=user_id)

    async def count_unread(self, user_id: str) -> int:
        """Return unread message count for *user_id*.

        Args:
            user_id: Target user.
        """
        await self._ensure_table()
        result = await self._db.execute_query(
            self._sql(  # noqa: S608
                f"SELECT COUNT(*) AS cnt FROM {self._table}"
                " WHERE user_id = ? AND read = FALSE"
            ),
            [user_id],
        )
        _require_success(result)
        if not result.rows:
            return 0
        return int(result.rows[0].get("cnt", 0))

    async def clear_all(self, user_id: str) -> int:
        """Delete all messages for *user_id*.

        Args:
            user_id: Target user.

        Returns:
            Number of messages deleted.
        """
        await self._ensure_table()
        count_result = await self._db.execute_query(
            self._sql(  # noqa: S608
                f"SELECT COUNT(*) AS cnt FROM {self._table} WHERE user_id = ?"
            ),
            [user_id],
        )
        _require_success(count_result)
        count = int(count_result.rows[0].get("cnt", 0)) if count_result.rows else 0
        result = await self._db.execute_delete(
            self._table,
            self._sql("user_id = ?"),
            [user_id],
        )
        _require_success(result)
        logger.debug("inbox.db.cleared_all", user_id=user_id, count=count)
        return count

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Run a lightweight read-only database probe for inbox storage."""
        try:
            result = await self._db.execute_query(
                f"SELECT 1 FROM {self._table} LIMIT 1",  # noqa: S608
                [],
            )
            _require_success(result)
        except Exception as exc:  # noqa: BLE001 — health probe must never raise
            return HealthCheckResult(
                component="inbox_store",
                status=HealthStatus.UNHEALTHY,
                error=str(exc),
                details={"backend": "database", "table": self._table},
            )

        return HealthCheckResult(
            component="inbox_store",
            status=HealthStatus.HEALTHY,
            details={"backend": "database", "table": self._table},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_message(row: dict[str, Any]) -> InboxMessage:
        """Convert a raw DB row dict to an :class:`InboxMessage`.

        Args:
            row: Raw row returned by the database driver.

        Returns:
            Hydrated :class:`InboxMessage` instance.
        """
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif not isinstance(created_at, datetime):
            created_at = datetime.now(UTC)

        # The native SQL binding contract stores aware datetimes as naive UTC.
        # Restore the timezone on hydration; InboxMessage promises UTC, not a
        # local/naive timestamp. Drivers returning offsets normalize as well.
        created_at = (
            created_at.replace(tzinfo=UTC)
            if created_at.tzinfo is None
            else created_at.astimezone(UTC)
        )

        metadata = row.get("metadata") or {}
        if isinstance(metadata, str):
            # JSON columns come back as text on drivers that do not decode
            # them (SQLite) and as a mapping on drivers that do (Postgres
            # JSONB via asyncpg). Both are valid reads of the same row, so the
            # store decodes the text form instead of dropping the metadata —
            # the delivery store's ``due_deliveries`` does the same for its
            # ``message`` payload, and a store that only accepted the mapping
            # silently lost data on the default SQLite deployment.
            from quadkit.serialization import loads

            try:
                metadata = loads(metadata)
            except Exception:  # noqa: BLE001 — unreadable payload => empty
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}

        return InboxMessage(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            title=str(row["title"]),
            body=str(row["body"]),
            read=bool(row.get("read", False)),
            created_at=created_at,
            metadata=metadata,
        )


__all__ = ["DatabaseInboxStore"]
