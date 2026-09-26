"""Unit tests for AdapterRegistry."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.events.adapters.registry import AdapterRegistry


class TestAdapterRegistry:
    """Tests for AdapterRegistry."""

    def test_empty_registry_has_no_keys(self) -> None:
        """Empty registry should have no keys."""
        registry = AdapterRegistry()
        assert registry.keys() == []

    def test_register_adds_key(self) -> None:
        """Registering a wirer should add its key."""
        registry = AdapterRegistry()
        registry.register("test", AsyncMock())
        assert "test" in registry.keys()

    def test_register_multiple_keys(self) -> None:
        """Multiple wirers can be registered."""
        registry = AdapterRegistry()
        registry.register("kafka", AsyncMock())
        registry.register("rabbitmq", AsyncMock())
        assert set(registry.keys()) == {"kafka", "rabbitmq"}

    @pytest.mark.asyncio
    async def test_wire_all_calls_wirer_when_config_present(self) -> None:
        """wire_all should call wirer when adapter config is not None."""
        registry = AdapterRegistry()
        mock_wirer = AsyncMock()
        registry.register("kafka", mock_wirer)

        mock_config = MagicMock()
        mock_config.kafka = MagicMock()  # not None → should wire

        await registry.wire_all(mock_config, MagicMock(), MagicMock())
        mock_wirer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_wire_all_skips_when_config_absent(self) -> None:
        """wire_all should skip wirer when adapter config is None."""
        registry = AdapterRegistry()
        mock_wirer = AsyncMock()
        registry.register("kafka", mock_wirer)

        mock_config = MagicMock()
        mock_config.kafka = None  # None → skip

        await registry.wire_all(mock_config, MagicMock(), MagicMock())
        mock_wirer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_wire_all_calls_multiple_wirers(self) -> None:
        """wire_all should call all wirers whose configs are present."""
        registry = AdapterRegistry()
        mock_kafka_wirer = AsyncMock()
        mock_rabbitmq_wirer = AsyncMock()
        registry.register("kafka", mock_kafka_wirer)
        registry.register("rabbitmq", mock_rabbitmq_wirer)

        mock_config = MagicMock()
        mock_config.kafka = MagicMock()
        mock_config.rabbitmq = MagicMock()

        await registry.wire_all(mock_config, MagicMock(), MagicMock())
        mock_kafka_wirer.assert_awaited_once()
        mock_rabbitmq_wirer.assert_awaited_once()

    def test_with_defaults_has_kafka_and_rabbitmq(self) -> None:
        """with_defaults should create registry with kafka and rabbitmq."""
        registry = AdapterRegistry.with_defaults()
        assert "kafka" in registry.keys()
        assert "rabbitmq" in registry.keys()

    def test_with_defaults_has_only_two_keys(self) -> None:
        """with_defaults should have exactly kafka and rabbitmq."""
        registry = AdapterRegistry.with_defaults()
        assert set(registry.keys()) == {"kafka", "rabbitmq"}
