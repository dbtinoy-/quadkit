"""Unit tests for InboxService."""

from __future__ import annotations

import pytest

from quadkit.notification.inbox.memory import InMemoryInboxStore
from quadkit.notification.inbox.service import InboxService


async def _boom(**kwargs: object) -> None:
    """Hook handler that always raises, for error-isolation tests."""
    raise RuntimeError("hook handler failed")


class TestInboxService:
    """InboxService tests use InMemoryInboxStore as the injected backend."""

    @pytest.fixture
    def store(self) -> InMemoryInboxStore:
        return InMemoryInboxStore()

    @pytest.fixture
    def service(self, store: InMemoryInboxStore) -> InboxService:
        return InboxService(store=store)

    # ------------------------------------------------------------------
    # send
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_send_returns_inbox_message(self, service: InboxService) -> None:
        """send() returns a persisted InboxMessage."""
        msg = await service.send("user-1", "Welcome", "You are in!")
        assert msg.user_id == "user-1"
        assert msg.title == "Welcome"
        assert msg.body == "You are in!"
        assert msg.read is False
        assert msg.id  # non-empty UUID

    @pytest.mark.asyncio
    async def test_send_stores_metadata_kwargs(self, service: InboxService) -> None:
        """Extra keyword arguments are stored in message.metadata."""
        msg = await service.send(
            "user-1",
            "Order",
            "Shipped!",
            order_id="ORD-42",
            tracking_url="https://track.example.com",
        )
        assert msg.metadata["order_id"] == "ORD-42"
        assert msg.metadata["tracking_url"] == "https://track.example.com"

    @pytest.mark.asyncio
    async def test_send_without_metadata_gives_empty_dict(
        self, service: InboxService
    ) -> None:
        """send() without extra kwargs produces an empty metadata dict."""
        msg = await service.send("user-1", "Plain", "No extras")
        assert msg.metadata == {}

    # ------------------------------------------------------------------
    # get_inbox
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_inbox_returns_all_messages(self, service: InboxService) -> None:
        """get_inbox() returns every message for the user."""
        await service.send("user-1", "A", "body")
        await service.send("user-1", "B", "body")
        await service.send("user-2", "C", "body")  # different user

        inbox = await service.get_inbox("user-1")
        assert len(inbox) == 2

    @pytest.mark.asyncio
    async def test_get_inbox_unread_only(self, service: InboxService) -> None:
        """get_inbox(unread_only=True) filters out read messages."""
        m1 = await service.send("user-1", "A", "body")
        await service.send("user-1", "B", "body")
        await service.mark_read(m1.id, "user-1")

        unread = await service.get_inbox("user-1", unread_only=True)
        assert len(unread) == 1
        assert unread[0].title == "B"

    # ------------------------------------------------------------------
    # get_message
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_message_returns_message_by_id(
        self, service: InboxService
    ) -> None:
        """get_message() retrieves a specific message."""
        msg = await service.send("user-1", "Hello", "World")
        retrieved = await service.get_message(msg.id)
        assert retrieved is not None
        assert retrieved.id == msg.id

    @pytest.mark.asyncio
    async def test_get_message_returns_none_for_missing(
        self, service: InboxService
    ) -> None:
        """get_message() returns None for unknown IDs."""
        result = await service.get_message("no-such-id")
        assert result is None

    # ------------------------------------------------------------------
    # mark_read
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_mark_read_updates_message(self, service: InboxService) -> None:
        """mark_read() marks the specified message as read."""
        msg = await service.send("user-1", "Hi", "there")
        assert msg.read is False

        await service.mark_read(msg.id, "user-1")

        updated = await service.get_message(msg.id)
        assert updated is not None
        assert updated.read is True

    # ------------------------------------------------------------------
    # mark_all_read
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_mark_all_read_marks_all_messages(
        self, service: InboxService
    ) -> None:
        """mark_all_read() sets read=True on every unread message."""
        await service.send("user-1", "A", "")
        await service.send("user-1", "B", "")

        await service.mark_all_read("user-1")

        inbox = await service.get_inbox("user-1")
        assert all(m.read for m in inbox)

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_removes_message(self, service: InboxService) -> None:
        """delete() removes a message; subsequent get returns None."""
        msg = await service.send("user-1", "Bye", "body")
        await service.delete(msg.id, "user-1")
        assert await service.get_message(msg.id) is None

    # ------------------------------------------------------------------
    # count_unread
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_count_unread_reflects_read_state(
        self, service: InboxService
    ) -> None:
        """count_unread() returns correct count before and after mark_read."""
        m1 = await service.send("user-1", "A", "")
        await service.send("user-1", "B", "")

        assert await service.count_unread("user-1") == 2

        await service.mark_read(m1.id, "user-1")

        assert await service.count_unread("user-1") == 1

    # ------------------------------------------------------------------
    # default store
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_default_store_is_in_memory(self) -> None:
        """InboxService() without a store argument uses InMemoryInboxStore."""
        svc = InboxService()
        msg = await svc.send("user-x", "Test", "body")
        assert msg.id

    @pytest.mark.asyncio
    async def test_send_fires_inbox_sent_hook(self, service: InboxService) -> None:
        """send() fires the INBOX_SENT_HOOK with the persisted message."""
        from quadkit.contracts.notification.inbox import INBOX_SENT_HOOK
        from quadkit.hooks.ambient import use as use_hooks
        from quadkit.hooks.registry import HookRegistry

        registry = HookRegistry("test-inbox-sent")
        calls: list[dict] = []

        async def capture(**kwargs: object) -> None:
            calls.append(kwargs)

        registry.register_action(INBOX_SENT_HOOK, capture)

        with use_hooks(registry):
            msg = await service.send("user-1", "Ready", "Go now")

        assert len(calls) == 1
        assert calls[0]["user_id"] == "user-1"
        assert calls[0]["title"] == "Ready"
        assert calls[0]["body"] == "Go now"
        assert calls[0]["message"] is msg

    @pytest.mark.asyncio
    async def test_send_tolerates_failing_hook_handlers(
        self, service: InboxService
    ) -> None:
        """A raising hook handler must not break send()."""
        from quadkit.contracts.notification.inbox import INBOX_SENT_HOOK
        from quadkit.hooks.ambient import use as use_hooks
        from quadkit.hooks.registry import HookRegistry

        registry = HookRegistry("test-inbox-sent-error")
        registry.register_action(INBOX_SENT_HOOK, _boom)

        with use_hooks(registry):
            msg = await service.send("user-1", "Ready", "Go now")

        assert msg.user_id == "user-1"
