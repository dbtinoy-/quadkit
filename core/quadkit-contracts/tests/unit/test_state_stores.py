"""Unit tests for quadkit.contracts.infra stores protocol."""

from __future__ import annotations

import pytest
from typing import Any

from quadkit.contracts.infra.state import StateStoreProtocol


class FakeStateStore:
    """Fake implementation of StateStoreProtocol for testing."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        """Get a value by key."""
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value with optional TTL."""
        self._store[key] = value

    async def delete(self, key: str) -> None:
        """Delete a key."""
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._store


class TestStateStoreProtocol:
    """Tests for StateStoreProtocol."""

    def test_fake_store_has_required_methods(self) -> None:
        """Verify fake store has all required protocol methods."""
        store = FakeStateStore()
        # Check required methods exist
        assert hasattr(store, "get")
        assert hasattr(store, "set")
        assert hasattr(store, "delete")
        assert hasattr(store, "exists")
        # Verify they are callable
        assert callable(store.get)
        assert callable(store.set)
        assert callable(store.delete)
        assert callable(store.exists)

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        """Verify set and get operations."""
        store = FakeStateStore()
        await store.set("key1", {"data": "value"})
        result = await store.get("key1")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self) -> None:
        """Verify get returns None for missing keys."""
        store = FakeStateStore()
        result = await store.get("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        """Verify delete removes the key."""
        store = FakeStateStore()
        await store.set("key1", "value")
        await store.delete("key1")
        result = await store.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_exists(self) -> None:
        """Verify exists check."""
        store = FakeStateStore()
        await store.set("key1", "value")
        assert await store.exists("key1") is True
        assert await store.exists("missing") is False

    @pytest.mark.asyncio
    async def test_set_with_ttl(self) -> None:
        """Verify set accepts ttl parameter."""
        store = FakeStateStore()
        # Just verify it doesn't raise - TTL handling is implementation-specific
        await store.set("key1", "value", ttl=3600)
        result = await store.get("key1")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_overwrite_value(self) -> None:
        """Verify overwriting a key replaces the value."""
        store = FakeStateStore()
        await store.set("key1", "first")
        await store.set("key1", "second")
        result = await store.get("key1")
        assert result == "second"