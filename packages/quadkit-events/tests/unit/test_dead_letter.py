"""Tests for dead letter queue."""

import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from quadkit.events.buses.dead_letter import (
    DeadLetterEntry,
    DeadLetterStore,
    InMemoryDeadLetterStore,
)


class TestDeadLetterEntry:
    """Tests for DeadLetterEntry."""

    def test_dead_letter_entry_defaults(self) -> None:
        """Test DeadLetterEntry has correct defaults."""
        entry = DeadLetterEntry(
            event_type="TestEvent",
            event_data={"key": "value"},
            handler_name="test_handler",
            error="Test error",
        )

        assert entry.entry_id is not None
        assert entry.event_type == "TestEvent"
        assert entry.event_data == {"key": "value"}
        assert entry.handler_name == "test_handler"
        assert entry.error == "Test error"
        assert entry.failed_at is not None
        assert entry.attempts == 0
        assert entry.replayed is False
        assert entry.replayed_at is None


class TestDeadLetterStore:
    """Tests for DeadLetterStore (abstract)."""

    @pytest.mark.asyncio
    async def test_dead_letter_store_is_abstract(self) -> None:
        """Test DeadLetterStore cannot be instantiated directly."""
        store = DeadLetterStore()

        with pytest.raises(NotImplementedError):
            await store.save(MagicMock())

    @pytest.mark.asyncio
    async def test_dead_letter_store_list_entries_not_implemented(self) -> None:
        """Test list_entries raises NotImplementedError."""
        store = DeadLetterStore()

        with pytest.raises(NotImplementedError):
            await store.list_entries()

    @pytest.mark.asyncio
    async def test_dead_letter_store_get_count_not_implemented(self) -> None:
        """Test get_count raises NotImplementedError."""
        store = DeadLetterStore()

        with pytest.raises(NotImplementedError):
            await store.get_count()

    @pytest.mark.asyncio
    async def test_dead_letter_store_mark_replayed_not_implemented(self) -> None:
        """Test mark_replayed raises NotImplementedError."""
        store = DeadLetterStore()

        with pytest.raises(NotImplementedError):
            await store.mark_replayed("entry-id")

    @pytest.mark.asyncio
    async def test_dead_letter_store_delete_not_implemented(self) -> None:
        """Test delete raises NotImplementedError."""
        store = DeadLetterStore()

        with pytest.raises(NotImplementedError):
            await store.delete("entry-id")

    @pytest.mark.asyncio
    async def test_dead_letter_store_replay_not_implemented(self) -> None:
        """Test replay raises NotImplementedError."""
        store = DeadLetterStore()

        with pytest.raises(NotImplementedError):
            await store.replay("entry-id", MagicMock())


class TestInMemoryDeadLetterStore:
    """Tests for InMemoryDeadLetterStore."""

    @pytest.mark.asyncio
    async def test_save_entry(self) -> None:
        """Test saving an entry."""
        store = InMemoryDeadLetterStore()
        entry = DeadLetterEntry(
            event_type="TestEvent",
            event_data={"key": "value"},
            handler_name="test_handler",
            error="Test error",
        )

        await store.save(entry)

        assert entry.entry_id in store._entries

    @pytest.mark.asyncio
    async def test_list_entries_empty(self) -> None:
        """Test listing entries when empty."""
        store = InMemoryDeadLetterStore()

        entries = await store.list_entries()

        assert entries == []

    @pytest.mark.asyncio
    async def test_list_entries_with_data(self) -> None:
        """Test listing entries with saved data."""
        store = InMemoryDeadLetterStore()
        entry = DeadLetterEntry(event_type="TestEvent")
        await store.save(entry)

        entries = await store.list_entries()

        assert len(entries) == 1
        assert entries[0].event_type == "TestEvent"

    @pytest.mark.asyncio
    async def test_list_entries_filter_by_event_type(self) -> None:
        """Test filtering entries by event type."""
        store = InMemoryDeadLetterStore()
        await store.save(DeadLetterEntry(event_type="EventA"))
        await store.save(DeadLetterEntry(event_type="EventB"))
        await store.save(DeadLetterEntry(event_type="EventA"))

        entries = await store.list_entries(event_type="EventA")

        assert len(entries) == 2
        assert all(e.event_type == "EventA" for e in entries)

    @pytest.mark.asyncio
    async def test_get_count_empty(self) -> None:
        """Test get_count when empty."""
        store = InMemoryDeadLetterStore()

        count = await store.get_count()

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_count_with_entries(self) -> None:
        """Test get_count with entries."""
        store = InMemoryDeadLetterStore()
        await store.save(DeadLetterEntry(event_type="EventA"))
        await store.save(DeadLetterEntry(event_type="EventB"))

        count = await store.get_count()

        assert count == 2

    @pytest.mark.asyncio
    async def test_delete_entry(self) -> None:
        """Test deleting an entry."""
        store = InMemoryDeadLetterStore()
        entry = DeadLetterEntry(event_type="TestEvent")
        await store.save(entry)

        result = await store.delete(entry.entry_id)

        assert result is True
        assert entry.entry_id not in store._entries

    @pytest.mark.asyncio
    async def test_delete_nonexistent_entry(self) -> None:
        """Test deleting nonexistent entry returns False."""
        store = InMemoryDeadLetterStore()

        result = await store.delete("nonexistent-id")

        assert result is False
