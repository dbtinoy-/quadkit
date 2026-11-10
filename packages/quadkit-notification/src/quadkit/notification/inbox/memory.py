"""In-memory inbox store implementation.

Suitable for unit tests and single-process deployments that do not
require durable notification persistence.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer import MessageDeliveryReceipt
from quadkit.contracts.notification.inbox import InboxMessage
from quadkit.logging import get_logger

logger = get_logger(__name__)


class InMemoryInboxStore:
    """In-process :class:`InboxStoreProtocol` implementation backed by a dict.

    Thread-safety note: this store is *not* thread-safe.  Within a single
    async event loop it is safe; for multi-threaded scenarios inject a
    SQL-backed :class:`DatabaseInboxStore` instead.
    """

    supports_inbox_send_once_v1: bool = True

    def __init__(self) -> None:
        self._store: dict[str, InboxMessage] = {}
        self._receipts: dict[str, tuple[str, MessageDeliveryReceipt]] = {}

    async def save(self, message: InboxMessage) -> None:
        """Persist *message* in memory.

        Args:
            message: The inbox message to store.
        """
        self._store[message.id] = message
        logger.debug("inbox.saved", message_id=message.id, user_id=message.user_id)

    async def save_once(
        self, key: str, message: InboxMessage
    ) -> tuple[MessageDeliveryReceipt, bool]:
        """Record one intent per key without retaining a second private body."""
        from quadkit.notification.inbox.idempotency import fingerprint, validate_key

        validate_key(key)
        intent = fingerprint(message)
        previous = self._receipts.get(key)
        if previous is not None:
            if previous[0] != intent:
                raise ValueError("inbox delivery key conflicts with an existing intent")
            return replace(previous[1]), False
        if message.id in self._store:
            raise ValueError("inbox message ID already exists")
        receipt = MessageDeliveryReceipt(
            message.id, "inbox", "inbox", message.created_at
        )
        # No suspension between lookup and both writes: one event-loop operation.
        self._store[message.id] = deepcopy(message)
        self._receipts[key] = (intent, receipt)
        return replace(receipt), True

    async def get(self, message_id: str) -> InboxMessage | None:
        """Return the message with *message_id*, or ``None``.

        Args:
            message_id: ID to look up.
        """
        return self._store.get(message_id)

    async def get_for_user(self, message_id: str, user_id: str) -> InboxMessage | None:
        """Return a message only when it belongs to the supplied user."""
        message = self._store.get(message_id)
        if message is None or message.user_id != user_id:
            return None
        return message

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
        results = [
            m
            for m in self._store.values()
            if m.user_id == user_id and (not unread_only or not m.read)
        ]
        results.sort(key=lambda m: (m.created_at, m.id), reverse=True)
        return results

    async def list_page_for_user(
        self,
        user_id: str,
        *,
        unread_only: bool = False,
        limit: int,
        offset: int,
    ) -> list[InboxMessage]:
        """Return one page with the same ordering as the database store."""
        if limit < 1 or offset < 0:
            raise ValueError("limit must be positive and offset non-negative")
        messages = await self.list_for_user(user_id, unread_only=unread_only)
        return messages[offset : offset + limit]

    async def mark_read(self, message_id: str, user_id: str) -> None:
        """Mark *message_id* as read if it belongs to *user_id*.

        ``InboxMessage`` is frozen; we create a replacement with
        ``read=True`` and update the store in-place.

        Args:
            message_id: ID of the message to mark.
            user_id: Expected owner.
        """
        msg = self._store.get(message_id)
        if msg is not None and msg.user_id == user_id and not msg.read:
            self._store[message_id] = replace(msg, read=True)
            logger.debug("inbox.marked_read", message_id=message_id, user_id=user_id)

    async def mark_all_read(self, user_id: str) -> None:
        """Mark every unread message for *user_id* as read.

        Args:
            user_id: Target user.
        """
        now = datetime.now(UTC)
        for mid, msg in list(self._store.items()):
            if msg.user_id == user_id and not msg.read:
                self._store[mid] = replace(msg, read=True)
        logger.debug("inbox.all_marked_read", user_id=user_id, ts=now.isoformat())

    async def delete(self, message_id: str, user_id: str) -> None:
        """Delete *message_id* if it belongs to *user_id*.

        Args:
            message_id: ID to remove.
            user_id: Expected owner.
        """
        msg = self._store.get(message_id)
        if msg is not None and msg.user_id == user_id:
            del self._store[message_id]
            logger.debug("inbox.deleted", message_id=message_id, user_id=user_id)

    async def count_unread(self, user_id: str) -> int:
        """Return unread message count for *user_id*.

        Args:
            user_id: Target user.
        """
        return sum(
            1 for m in self._store.values() if m.user_id == user_id and not m.read
        )

    async def clear_all(self, user_id: str) -> int:
        """Delete all messages for *user_id*.

        Args:
            user_id: Target user.

        Returns:
            Number of messages deleted.
        """
        ids = [mid for mid, m in self._store.items() if m.user_id == user_id]
        for mid in ids:
            del self._store[mid]
        logger.debug("inbox.cleared_all", user_id=user_id, count=len(ids))
        return len(ids)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return health for the in-memory inbox backend."""
        _ = timeout
        return HealthCheckResult(
            component="inbox_store",
            status=HealthStatus.HEALTHY,
            details={"backend": "memory", "message_count": len(self._store)},
        )


__all__ = ["InMemoryInboxStore"]
