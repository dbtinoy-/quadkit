"""Unit tests for InMemoryInboxStore."""

from __future__ import annotations

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.notification.inbox import InboxMessage
from quadkit.notification.inbox.memory import InMemoryInboxStore


class TestInMemoryInboxStore:
    """Covers all InboxStoreProtocol operations via the in-memory backend."""

    @pytest.fixture
    def store(self) -> InMemoryInboxStore:
        return InMemoryInboxStore()

    @pytest.fixture
    def message(self) -> InboxMessage:
        return InboxMessage.create(user_id="user-1", title="Hello", body="World")

    # ------------------------------------------------------------------
    # save / get
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_save_persists_message(
        self, store: InMemoryInboxStore, message: InboxMessage
    ) -> None:
        """save() stores the message; get() retrieves it by ID."""
        await store.save(message)
        retrieved = await store.get(message.id)
        assert retrieved is not None
        assert retrieved.id == message.id
        assert retrieved.title == "Hello"
        assert retrieved.body == "World"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_unknown_id(
        self, store: InMemoryInboxStore
    ) -> None:
        """get() returns None when message_id is not found."""
        result = await store.get("nonexistent-id")
        assert result is None

    # ------------------------------------------------------------------
    # list_for_user
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_for_user_returns_all_messages(
        self, store: InMemoryInboxStore
    ) -> None:
        """list_for_user() returns all messages for the user."""
        m1 = InboxMessage.create(user_id="user-1", title="A", body="1")
        m2 = InboxMessage.create(user_id="user-1", title="B", body="2")
        m3 = InboxMessage.create(user_id="user-2", title="C", body="3")
        await store.save(m1)
        await store.save(m2)
        await store.save(m3)

        results = await store.list_for_user("user-1")
        assert len(results) == 2
        ids = {r.id for r in results}
        assert m1.id in ids
        assert m2.id in ids
        assert m3.id not in ids

    @pytest.mark.asyncio
    async def test_list_for_user_unread_only_filters_read(
        self, store: InMemoryInboxStore
    ) -> None:
        """list_for_user(unread_only=True) excludes read messages."""
        m1 = InboxMessage.create(user_id="user-1", title="Unread", body="x")
        m2 = InboxMessage.create(user_id="user-1", title="Read", body="y")
        await store.save(m1)
        await store.save(m2)
        await store.mark_read(m2.id, "user-1")

        results = await store.list_for_user("user-1", unread_only=True)
        assert len(results) == 1
        assert results[0].id == m1.id

    @pytest.mark.asyncio
    async def test_list_for_user_empty_for_unknown_user(
        self, store: InMemoryInboxStore
    ) -> None:
        """list_for_user() returns an empty list for an unknown user."""
        results = await store.list_for_user("ghost")
        assert results == []

    # ------------------------------------------------------------------
    # mark_read
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_mark_read_flips_read_flag(
        self, store: InMemoryInboxStore, message: InboxMessage
    ) -> None:
        """mark_read() creates a replacement with read=True."""
        await store.save(message)
        assert not message.read

        await store.mark_read(message.id, message.user_id)

        updated = await store.get(message.id)
        assert updated is not None
        assert updated.read is True

    @pytest.mark.asyncio
    async def test_mark_read_ignores_wrong_user_id(
        self, store: InMemoryInboxStore, message: InboxMessage
    ) -> None:
        """mark_read() does nothing when user_id doesn't match."""
        await store.save(message)
        await store.mark_read(message.id, "wrong-user")

        unchanged = await store.get(message.id)
        assert unchanged is not None
        assert unchanged.read is False

    @pytest.mark.asyncio
    async def test_mark_read_already_read_is_idempotent(
        self, store: InMemoryInboxStore, message: InboxMessage
    ) -> None:
        """mark_read() on an already-read message is safe."""
        await store.save(message)
        await store.mark_read(message.id, message.user_id)
        await store.mark_read(message.id, message.user_id)  # second call

        result = await store.get(message.id)
        assert result is not None
        assert result.read is True

    # ------------------------------------------------------------------
    # mark_all_read
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_mark_all_read_marks_every_unread(
        self, store: InMemoryInboxStore
    ) -> None:
        """mark_all_read() marks every unread message for the user."""
        m1 = InboxMessage.create(user_id="user-1", title="A", body="")
        m2 = InboxMessage.create(user_id="user-1", title="B", body="")
        m3 = InboxMessage.create(user_id="user-2", title="C", body="")
        await store.save(m1)
        await store.save(m2)
        await store.save(m3)

        await store.mark_all_read("user-1")

        r1 = await store.get(m1.id)
        r2 = await store.get(m2.id)
        r3 = await store.get(m3.id)
        assert r1 is not None
        assert r1.read is True
        assert r2 is not None
        assert r2.read is True
        # user-2's message must not be touched
        assert r3 is not None
        assert r3.read is False

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_removes_message(
        self, store: InMemoryInboxStore, message: InboxMessage
    ) -> None:
        """delete() removes the message; subsequent get() returns None."""
        await store.save(message)
        await store.delete(message.id, message.user_id)
        assert await store.get(message.id) is None

    @pytest.mark.asyncio
    async def test_delete_ignores_wrong_user_id(
        self, store: InMemoryInboxStore, message: InboxMessage
    ) -> None:
        """delete() does nothing when user_id doesn't match."""
        await store.save(message)
        await store.delete(message.id, "wrong-user")
        assert await store.get(message.id) is not None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_id_is_safe(
        self, store: InMemoryInboxStore
    ) -> None:
        """delete() on an unknown ID does not raise."""
        await store.delete("ghost-id", "user-1")  # must not raise

    # ------------------------------------------------------------------
    # count_unread
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_count_unread_returns_correct_count(
        self, store: InMemoryInboxStore
    ) -> None:
        """count_unread() returns the number of unread messages."""
        m1 = InboxMessage.create(user_id="user-1", title="A", body="")
        m2 = InboxMessage.create(user_id="user-1", title="B", body="")
        m3 = InboxMessage.create(user_id="user-1", title="C", body="")
        await store.save(m1)
        await store.save(m2)
        await store.save(m3)
        await store.mark_read(m1.id, "user-1")

        count = await store.count_unread("user-1")
        assert count == 2

    @pytest.mark.asyncio
    async def test_count_unread_zero_for_unknown_user(
        self, store: InMemoryInboxStore
    ) -> None:
        """count_unread() returns 0 for a user with no messages."""
        count = await store.count_unread("ghost")
        assert count == 0

    # ------------------------------------------------------------------
    # health_check
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(
        self, store: InMemoryInboxStore
    ) -> None:
        """health_check() reports healthy for the in-memory backend."""
        result = await store.health_check()

        assert result.component == "inbox_store"
        assert result.status == HealthStatus.HEALTHY
        assert result.details == {"backend": "memory", "message_count": 0}
