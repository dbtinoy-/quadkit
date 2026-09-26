from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.events.stores.registry import EventStoreRegistry


class TestEventStoreRegistry:
    def test_empty_registry_has_no_keys(self) -> None:
        registry = EventStoreRegistry()
        assert registry.keys() == []

    @pytest.mark.asyncio
    async def test_register_and_create(self) -> None:
        registry = EventStoreRegistry()
        mock_store = MagicMock()
        mock_factory = AsyncMock(return_value=mock_store)
        registry.register("test", mock_factory)

        result = await registry.create("test", MagicMock(), MagicMock())
        assert result is mock_store
        mock_factory.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_unknown_key_raises_keyerror(self) -> None:
        registry = EventStoreRegistry()
        with pytest.raises(KeyError, match="unknown"):
            await registry.create("unknown", MagicMock(), MagicMock())

    def test_with_defaults_has_all_backends(self) -> None:
        registry = EventStoreRegistry.with_defaults()
        keys = registry.keys()
        assert "memory" in keys
        assert "postgres" in keys
        assert "mongodb" in keys
        assert "sqlite" in keys

    @pytest.mark.asyncio
    async def test_with_defaults_can_override(self) -> None:
        registry = EventStoreRegistry.with_defaults()
        mock_store = MagicMock()
        mock_factory = AsyncMock(return_value=mock_store)
        registry.register("memory", mock_factory)

        await registry.create("memory", MagicMock(), MagicMock())
        mock_factory.assert_awaited_once()
