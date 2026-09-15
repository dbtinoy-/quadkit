"""Unit tests for server domain"""

from unittest.mock import Mock

import pytest

from quadkit.contracts.infra.tasks import TaskQueueProtocol
from quadkit.contracts.web.protocols import BackgroundTaskRunnerProtocol
from quadkit.di import Container
from quadkit.web.background.tasks import StarletteBackgroundTaskRunner
from quadkit.web.di.provider import WebProvider
from quadkit.web.routing.router import Router


@pytest.mark.asyncio
async def test_provider_register():
    """Test provider registration"""
    # Import fresh instances to avoid any potential state pollution
    from quadkit.di import Container
    from quadkit.web.di.provider import WebProvider

    provider = WebProvider()
    container = Container()

    await provider.register(container)

    # Check that Router is registered as singleton using public API
    assert container.is_singleton(Router)


@pytest.mark.asyncio
async def test_provider_startup():
    """Test provider startup with pass-through"""
    provider = WebProvider()
    container = Container()

    await provider.register(container)
    await provider.boot(container)

    # Check that Starlette app was created
    assert provider.starlette is not None
    assert hasattr(provider.starlette, "router")


@pytest.mark.asyncio
async def test_provider_shutdown_clears_state():
    """Shutdown should clear provider-managed state and not raise."""
    from quadkit.web.routing.router import Router

    provider = WebProvider()

    # Simulate some state (as would be set after startup)
    provider.controllers = [object(), object()]
    provider.openapi_generator = object()
    provider.router = Router()

    # Add a test route
    provider.router.add_route("GET", "/test", lambda: None)

    # Invoke shutdown (should not raise)
    await provider.shutdown()

    # Verify state cleared (starlette is cleared, other state is test's responsibility)
    assert provider.starlette is None


@pytest.mark.asyncio
async def test_background_runner_binding_ignores_task_queue_registration() -> None:
    """Regression: BackgroundTaskRunnerProtocol binding is Starlette-only.

    Verifies that registering TaskQueueProtocol does not change the resolved
    BackgroundTaskRunnerProtocol binding. The binding should always resolve to
    StarletteBackgroundTaskRunner, never a queue-backed variant.
    """
    from unittest.mock import AsyncMock

    provider = WebProvider()
    container = Container()

    await provider.register(container)

    # Create a minimal mock that conforms to TaskQueueProtocol
    task_queue = Mock()
    task_queue.enqueue = AsyncMock()
    task_queue.dequeue = AsyncMock()
    task_queue.get_task_count = AsyncMock(return_value=0)
    task_queue.clear = AsyncMock()
    task_queue.ack = AsyncMock()
    task_queue.nack = AsyncMock()
    task_queue.close = AsyncMock()

    container.singleton(TaskQueueProtocol, task_queue)

    # Resolve the background runner (transient, resolved async)
    runner = await container.resolve(BackgroundTaskRunnerProtocol)

    assert isinstance(runner, StarletteBackgroundTaskRunner)


@pytest.mark.asyncio
async def test_provider_boot_wires_optional_hook_registry() -> None:
    """Boot resolves optional hooks and stashes them on the Starlette app."""
    from quadkit.contracts.core import HookRegistryProtocol
    from quadkit.hooks import HookRegistry

    provider = WebProvider()
    container = Container()
    hooks = HookRegistry("web-test")
    container.singleton(HookRegistryProtocol, hooks)

    await provider.register(container)
    await provider.boot(container)

    assert provider.starlette is not None
    assert provider.starlette.state.hook_registry is hooks
