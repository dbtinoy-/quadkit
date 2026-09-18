"""Inbox notification contracts — model and store protocol.

Defines the canonical ``InboxMessage`` value object and the
``InboxStoreProtocol`` that all inbox backends must satisfy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core import HealthCheckResult
import uuid

INBOX_SENT_HOOK = "notification.inbox.sent"


@dataclass(frozen=True)
class InboxMessage:
    """A persisted inbox notification for a single user.

    Attributes:
        id: Unique message identifier (UUID4 string).
        user_id: Recipient user ID.
        title: Short display title shown in notification lists.
        body: Full notification body text.
        read: Whether the recipient has read this message.
        created_at: UTC timestamp of creation.
        metadata: Opaque key-value payload for application-level use.
    """

    id: str
    user_id: str
    title: str
    body: str
    read: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        user_id: str,
        title: str,
        body: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> InboxMessage:
        """Factory that auto-generates ``id`` and ``created_at``.

        Args:
            user_id: Recipient user ID.
            title: Short notification title.
            body: Full notification body.
            metadata: Optional key-value payload.

        Returns:
            A new unsaved :class:`InboxMessage` instance.
        """
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            body=body,
            metadata=metadata or {},
        )


@runtime_checkable
class InboxStoreProtocol(Protocol):
    """Structural protocol for inbox message persistence backends.

    All async methods are I/O-bound; implementations must not block the
    event loop.  Callers may use either :class:`InMemoryInboxStore` (for
    tests or simple deployments) or :class:`DatabaseInboxStore` (for
    production SQL-backed storage).
    """

    async def save(self, message: InboxMessage) -> None:
        """Persist *message*.

        Args:
            message: The inbox message to store.
        """
        ...

    async def get(self, message_id: str) -> InboxMessage | None:
        """Return the message with *message_id*, or ``None`` if not found.

        Args:
            message_id: The unique message ID to look up.
        """
        ...

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
        ...

    async def mark_read(self, message_id: str, user_id: str) -> None:
        """Mark *message_id* as read, guarded by *user_id* ownership.

        Args:
            message_id: ID of the message to mark read.
            user_id: Owner of the message (for authorisation).
        """
        ...

    async def mark_all_read(self, user_id: str) -> None:
        """Mark every unread message for *user_id* as read.

        Args:
            user_id: Target user.
        """
        ...

    async def delete(self, message_id: str, user_id: str) -> None:
        """Delete *message_id*, guarded by *user_id* ownership.

        Args:
            message_id: ID of the message to remove.
            user_id: Owner of the message (for authorisation).
        """
        ...

    async def count_unread(self, user_id: str) -> int:
        """Return the number of unread messages for *user_id*.

        Args:
            user_id: Target user.

        Returns:
            Unread message count.
        """
        ...

    async def clear_all(self, user_id: str) -> int:
        """Delete all messages for *user_id*.

        Args:
            user_id: Target user.

        Returns:
            Number of messages deleted.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return backend health for inbox storage.

        Args:
            timeout: Maximum seconds to wait for the health probe.
        """
        ...


__all__ = ["INBOX_SENT_HOOK", "InboxMessage", "InboxStoreProtocol"]
