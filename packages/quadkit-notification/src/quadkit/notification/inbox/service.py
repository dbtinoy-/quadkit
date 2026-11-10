"""Inbox service — high-level user-facing inbox operations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from quadkit.contracts.notification.inbox import INBOX_SENT_HOOK, InboxMessage
from quadkit.hooks.ambient import fire as fire_hook
from quadkit.logging import get_logger
from quadkit.notification.inbox.memory import InMemoryInboxStore

if TYPE_CHECKING:
    from quadkit.contracts.mailer import MessageDeliveryReceipt
    from quadkit.contracts.notification.inbox import InboxStoreProtocol
    from quadkit.notification.config import InboxConfig

logger = get_logger(__name__)


def _require_owner(messages: list[InboxMessage], user_id: str) -> None:
    """Fail closed when a store returns messages outside the requested inbox."""
    if any(message.user_id != user_id for message in messages):
        raise RuntimeError("inbox store returned a message for another user")


class InboxService:
    """High-level service for managing per-user inbox notifications.

    Wraps an :class:`InboxStoreProtocol` backend and exposes a clean API
    consumed by controllers, event handlers, or a notification bell widget.

    Defaults to :class:`InMemoryInboxStore` when no *store* is supplied so
    that the service can be used without DI wiring in simple scenarios (e.g.
    tests, CLI tools).  Production deployments should inject a
    :class:`DatabaseInboxStore` via the DI container.

    Args:
        store: Persistence backend.  Defaults to ``InMemoryInboxStore()``.
        config: Inbox settings — page-size ceiling and whether fetching marks
            messages read.  ``InboxConfig`` existed with nothing reading it;
            the service is where both settings belong, so a deployment can set
            them and see the effect.
    """

    def __init__(
        self,
        store: InboxStoreProtocol | None = None,
        config: InboxConfig | None = None,
    ) -> None:
        self._store: InboxStoreProtocol = (
            store if store is not None else InMemoryInboxStore()
        )
        if config is None:
            from quadkit.notification.config import InboxConfig as _InboxConfig

            config = _InboxConfig()
        # Never ``None`` past this point, so the readers below need no guard.
        self._config: InboxConfig = config

    async def send(
        self,
        user_id: str,
        title: str,
        body: str,
        **metadata: Any,
    ) -> InboxMessage:
        """Create and persist an inbox notification for *user_id*.

        Keyword arguments beyond *body* are collected into the message
        ``metadata`` dict so callers can attach arbitrary context::

            await inbox.send(
                user_id="u1",
                title="Order shipped",
                body="Your order #123 is on the way.",
                order_id="123",
                tracking_url="https://example.com/track/123",
            )

        Args:
            user_id: Recipient user ID.
            title: Short notification title shown in list views.
            body: Full message body.
            **metadata: Arbitrary key-value pairs stored in ``metadata``.

        Returns:
            The newly created and persisted :class:`InboxMessage`.
        """
        message = InboxMessage.create(
            user_id=user_id,
            title=title,
            body=body,
            metadata=dict(metadata) if metadata else None,
        )
        await self._store.save(message)
        logger.info(
            "inbox.sent",
            message_id=message.id,
            user_id=user_id,
            title=title,
        )
        await fire_hook(
            INBOX_SENT_HOOK,
            message=message,
            user_id=user_id,
            title=title,
            body=body,
        )
        return message

    async def send_once(
        self, key: str, user_id: str, title: str, body: str, **metadata: Any
    ) -> MessageDeliveryReceipt:
        """Send one server-owned effect safely across retries and restarts.

        Callers must resolve a real recipient using trusted server authority.
        This is NOT an HTTP recipient resolver. Reuse an immutable effect key;
        changing recipient or content under it fails rather than redirects a
        retry. Legacy stores without the atomic capability fail closed. SQL
        receipts survive read/delete/clear; hooks fire only on the first insert
        and remain best-effort, not a retryable delivery channel. Call after the
        originating business transaction commits, not inside its outer scope.
        """
        from quadkit.contracts.notification.inbox import IdempotentInboxStoreProtocol
        from quadkit.notification.inbox.idempotency import fingerprint, validate_key

        validate_key(key)
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("a resolved recipient user ID is required")
        if (
            not isinstance(self._store, IdempotentInboxStoreProtocol)
            or self._store.supports_inbox_send_once_v1 is not True
        ):
            raise TypeError("inbox store does not support atomic send_once")
        candidate = InboxMessage.create(user_id, title, body, metadata=metadata)
        fingerprint(candidate)  # Validate before copying or suspending.
        candidate = replace(candidate, metadata=deepcopy(candidate.metadata))
        receipt, created = await self._store.save_once(key, candidate)
        if created:
            await fire_hook(
                INBOX_SENT_HOOK,
                message=candidate,
                user_id=user_id,
                title=title,
                body=body,
            )
        return receipt

    async def get_inbox(
        self,
        user_id: str,
        *,
        unread_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[InboxMessage]:
        """Return inbox messages for *user_id*, newest first.

        Stores may optionally implement ``list_page_for_user`` for bounded
        reads. Legacy stores retain the original list-and-slice fallback.
        ``InboxConfig.max_page_size`` clamps *limit*. Returned rows must belong
        to the requested user and paged stores must honor the page size;
        violations raise instead of returning a potentially unsafe page. This
        does not authenticate the caller or validate store mutation behavior.

        Args:
            user_id: User whose inbox to fetch.
            unread_only: When ``True`` only unread messages are returned.
            limit: Maximum messages to return. ``None`` returns every message
                up to the configured page size.
            offset: Number of newest messages to skip.

        Returns:
            Messages in reverse-chronological order.

        Raises:
            ValueError: If *offset* is negative.
        """
        if offset < 0:
            raise ValueError("offset must not be negative")
        ceiling = self._config.max_page_size
        size = ceiling if limit is None else max(1, min(limit, ceiling))
        paged_list = getattr(self._store, "list_page_for_user", None)
        if callable(paged_list):
            messages = await paged_list(
                user_id, unread_only=unread_only, limit=size, offset=offset
            )
        else:
            messages = await self._store.list_for_user(user_id, unread_only=unread_only)
        # Protect the HTTP boundary even if a custom store violates its owner
        # filter. Check before slicing or marking anything as read; silently
        # filtering would conceal an incomplete or incorrectly scoped page.
        _require_owner(messages, user_id)
        if not callable(paged_list):
            messages = messages[offset : offset + size]
        elif len(messages) > size:
            raise RuntimeError("inbox store exceeded the requested page size")
        if self._config.mark_read_on_fetch:
            updated: list[InboxMessage] = []
            for message in messages:
                if message.read:
                    updated.append(message)
                    continue
                await self._store.mark_read(message.id, user_id)
                # `InboxMessage` is frozen: the returned page reflects the
                # write, the caller's view does not mutate underneath it.
                updated.append(replace(message, read=True))
            messages = updated
        return messages

    async def get_message(self, message_id: str) -> InboxMessage | None:
        """Return a single inbox message by ID without an ownership check.

        This is a trusted-internal operation. Request handlers must use
        :meth:`get_message_for_user` with a server-authenticated subject.

        Args:
            message_id: Message to retrieve.

        Returns:
            The message, or ``None`` if not found.
        """
        return await self._store.get(message_id)

    async def get_message_for_user(
        self, message_id: str, user_id: str
    ) -> InboxMessage | None:
        """Return a message only when it belongs to the trusted user ID.

        The caller must obtain ``user_id`` from the authenticated request,
        never from request input. Cross-user and missing IDs both return None.
        This check does not authenticate the caller or authorize inbox sending.
        """
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("a non-empty authenticated user ID is required")
        # Newer stores can scope the query itself. Keep older third-party
        # InboxStoreProtocol implementations compatible, but still verify the
        # returned owner even when a store advertises the optional capability.
        scoped_get = getattr(self._store, "get_for_user", None)
        if callable(scoped_get):
            message = await scoped_get(message_id, user_id)
        else:
            message = await self._store.get(message_id)
        if message is None or message.user_id != user_id or message.id != message_id:
            return None
        return message

    async def mark_read(self, message_id: str, user_id: str) -> None:
        """Mark *message_id* as read.

        The *user_id* guard ensures a user can only mark their own messages.

        Args:
            message_id: ID of the message to mark.
            user_id: Owning user (authorisation guard).
        """
        await self._store.mark_read(message_id, user_id)

    async def mark_all_read(self, user_id: str) -> None:
        """Mark all of *user_id*'s messages as read.

        Args:
            user_id: Target user.
        """
        await self._store.mark_all_read(user_id)

    async def delete(self, message_id: str, user_id: str) -> None:
        """Delete a message owned by *user_id*.

        Args:
            message_id: ID of the message to remove.
            user_id: Owning user (authorisation guard).
        """
        await self._store.delete(message_id, user_id)

    async def count_unread(self, user_id: str) -> int:
        """Return the unread message count for *user_id*.

        Args:
            user_id: Target user.

        Returns:
            Number of unread messages.
        """
        return await self._store.count_unread(user_id)

    async def count(self, user_id: str, *, unread_only: bool = False) -> int:
        """Count *user_id*'s messages, optionally only the unread ones.

        The pagination envelope an API returns needs a total that does not
        depend on the current page, and ``count_unread`` only answers the
        unread half of that question.

        Args:
            user_id: Target user.
            unread_only: Count only unread messages.

        Returns:
            Number of matching messages.
        """
        if unread_only:
            return await self._store.count_unread(user_id)
        # No filtered-count method on the store protocol: a per-user inbox is a
        # small set, and counting its rows must not force a new method (and a
        # new implementation) into every store.
        messages = await self._store.list_for_user(user_id)
        _require_owner(messages, user_id)
        return len(messages)

    async def clear_all(self, user_id: str) -> int:
        """Delete all messages for *user_id*.

        Args:
            user_id: Target user.

        Returns:
            Number of messages deleted.
        """
        count = await self._store.clear_all(user_id)
        logger.info("inbox.cleared_all", user_id=user_id, count=count)
        return count


__all__ = ["InboxService"]
