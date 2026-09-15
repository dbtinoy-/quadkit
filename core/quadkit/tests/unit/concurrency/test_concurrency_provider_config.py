"""Tests for ConcurrencyProvider wiring of ConcurrencyConfig fields."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.concurrency.channels import BoundedChannel
from quadkit.concurrency.config import ConcurrencyConfig
from quadkit.concurrency.di.provider import ConcurrencyProvider


class TestConcurrencyProviderConfigWiring:
    """Boot applies default_channel_capacity; shutdown drains with a timeout."""

    @pytest.mark.asyncio
    async def test_boot_configures_channel_default(self) -> None:
        provider = ConcurrencyProvider(
            ConcurrencyConfig(default_channel_capacity=42)
        )
        previous = BoundedChannel._default_capacity
        try:
            await provider.boot(MagicMock())
            assert BoundedChannel._default_capacity == 42
            assert BoundedChannel().capacity == 42
        finally:
            BoundedChannel._default_capacity = previous

    @pytest.mark.asyncio
    async def test_shutdown_passes_drain_timeout(self) -> None:
        provider = ConcurrencyProvider(
            ConcurrencyConfig(dispatcher_shutdown_timeout=7.5)
        )
        dispatcher = MagicMock()
        dispatcher.shutdown = AsyncMock()
        provider._dispatcher = dispatcher
        provider._task_manager = None

        await provider.shutdown()

        dispatcher.shutdown.assert_awaited_once_with(
            wait=True, drain=True, drain_timeout=7.5
        )
