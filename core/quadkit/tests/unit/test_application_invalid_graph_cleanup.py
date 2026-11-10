"""Failed dependency validation must not prevent empty lifecycle cleanup."""

from unittest.mock import AsyncMock

import pytest

from quadkit.app.base import Application, AppState
from quadkit.di.provider import Provider, ProviderState


@pytest.mark.parametrize("cycle", [False, True])
async def test_invalid_graph_start_can_stop_and_dispose(cycle: bool) -> None:
    app = Application()
    first = Provider(name="first", dependencies=("second",))
    app.add_provider(first)
    if cycle:
        app.add_provider(Provider(name="second", dependencies=("first",)))
    dispose = AsyncMock(wraps=app.container.dispose)
    app.container.dispose = dispose
    with pytest.raises(
        ValueError, match="Circular dependency" if cycle else "depends on"
    ):
        await app.start()
    assert first.state is ProviderState.CREATED
    await app.stop()
    assert app.state is AppState.STOPPED
    dispose.assert_awaited_once()
    await app.stop()
    dispose.assert_awaited_once()


async def test_cleanup_error_does_not_replace_original_start_failure() -> None:
    app = Application()
    app.add_provider(Provider(name="first", dependencies=("missing",)))
    app._orchestrator.shutdown = AsyncMock(side_effect=ValueError("cleanup failure"))
    dispose = AsyncMock(wraps=app.container.dispose)
    app.container.dispose = dispose
    with pytest.raises(ValueError, match="depends on 'missing'"):
        await app.start()
    assert app.state is AppState.STOPPED
    dispose.assert_awaited_once()


async def test_normal_shutdown_error_still_disposes_container() -> None:
    from quadkit.app.exceptions import AppShutdownError

    app = Application()
    await app.start()
    app._orchestrator.shutdown = AsyncMock(side_effect=ValueError("cleanup failure"))
    dispose = AsyncMock(wraps=app.container.dispose)
    app.container.dispose = dispose
    with pytest.raises(AppShutdownError, match="Application shutdown failed") as raised:
        await app.stop()
    assert isinstance(raised.value.__cause__, ValueError)
    assert app.state is AppState.STOPPED
    dispose.assert_awaited_once()
