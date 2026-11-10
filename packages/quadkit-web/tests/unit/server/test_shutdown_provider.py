"""Unit tests for ``quadkit.web.GracefulShutdownProvider``."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.di import Container
from quadkit.web import (
    GracefulShutdownManager,
    GracefulShutdownProvider,
    ShutdownMiddleware,
)


@pytest.mark.asyncio
async def test_graceful_shutdown_provider_registers_manager_and_drains() -> None:
    container = Container()
    manager = GracefulShutdownManager(timeout=1.0)
    manager.wait_for_drain = AsyncMock(return_value=True)  # type: ignore[method-assign]

    provider = GracefulShutdownProvider(shutdown_manager=manager)
    await provider.register(container)
    await provider.boot(container)

    resolved = await container.resolve(GracefulShutdownManager)
    assert resolved is manager
    assert provider.manager is manager
    mw_cls, mw_opts = provider.middleware
    assert mw_cls is ShutdownMiddleware
    assert mw_opts == {"shutdown_manager": manager}

    async with manager.track_connection():
        await provider.on_before_shutdown("SIGTERM")

    assert manager.is_shutting_down is True
    manager.wait_for_drain.assert_awaited_once()
    await provider.shutdown()
