"""Pytest fixtures for testing.

Provides composable, minimal fixtures based on :mod:`quadkit.testing.fakes`
and :class:`~quadkit.testing.fixtures.bed.TestEnvironment`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import suppress
from typing import Any

import pytest

pytest_asyncio: Any = None
try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

# Async fixtures must use pytest_asyncio.fixture in strict asyncio mode.
_async_fixture: Callable[..., Any] = (
    pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
)

from quadkit.testing.fakes import (
    FakeCache,
    FakeClock,
    FakeCommandBus,
    FakeConfig,
    FakeEventBus,
    FakeLogger,
    FakeMetricsCollector,
    FakeQueryBus,
    FakeStateStore,
    FakeUnitOfWork,
)
from quadkit.testing.fixtures.bed import TestEnvironment
from quadkit.testing.fixtures.container import ContainerTestFixture
from quadkit.testing.lib import (
    test_assertions,
    test_data_factory,
)


@_async_fixture
async def test_bed() -> Any:
    """Yield a fresh :class:`TestEnvironment` (not yet started).

    The environment is torn down automatically after the test.
    """
    bed = TestEnvironment()
    try:
        yield bed
    finally:
        with suppress(Exception):
            await bed.teardown()


@_async_fixture
async def test_container() -> AsyncGenerator[ContainerTestFixture, None]:
    """Yield an isolated :class:`ContainerTestFixture` for the duration of a test.

    Every test receives a fresh container pre-loaded with mock implementations
    for all common Quadkit protocols.  The container is disposed automatically
    after the test, releasing any held resources.

    Example usage::

        @pytest.mark.asyncio
        async def test_service(test_container: ContainerTestFixture) -> None:
            test_container.mock(UserRepository, FakeUserRepository())
            service = await test_container.get(UserService)
            result = await service.create(email="a@b.com")
            assert result.is_ok()
    """
    fixture = ContainerTestFixture()
    try:
        yield fixture
    finally:
        await fixture.dispose()


# ---------------------------------------------------------------------------
# Fake service fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_event_bus() -> FakeEventBus:
    """Return a fresh :class:`FakeEventBus` for each test."""
    return FakeEventBus()


@pytest.fixture
def fake_logger() -> FakeLogger:
    """Return a fresh :class:`FakeLogger` for each test."""
    return FakeLogger()


@pytest.fixture
def fake_cache() -> FakeCache:
    """Return a fresh :class:`FakeCache` for each test."""
    return FakeCache()


@pytest.fixture
def fake_command_bus() -> FakeCommandBus:
    """Return a fresh :class:`FakeCommandBus` for each test."""
    return FakeCommandBus()


@pytest.fixture
def fake_query_bus() -> FakeQueryBus:
    """Return a fresh :class:`FakeQueryBus` for each test."""
    return FakeQueryBus()


@pytest.fixture
def fake_state_store() -> FakeStateStore:
    """Return a fresh :class:`FakeStateStore` for each test."""
    return FakeStateStore()


@pytest.fixture
def fake_metrics() -> FakeMetricsCollector:
    """Return a fresh :class:`FakeMetricsCollector` for each test."""
    return FakeMetricsCollector()


@pytest.fixture
def fake_clock() -> FakeClock:
    """Return a fresh :class:`FakeClock` frozen at the current time."""
    return FakeClock()


@pytest.fixture
def fake_unit_of_work() -> FakeUnitOfWork:
    """Return a fresh :class:`FakeUnitOfWork` for each test."""
    return FakeUnitOfWork()


@pytest.fixture
def fake_config(request: pytest.FixtureRequest) -> FakeConfig:
    """Return a :class:`FakeConfig` pre-populated from ``pytest.param`` markers.

    Usage::

        @pytest.mark.parametrize("fake_config", [{"feature.enabled": True}], indirect=True)
        def test_feature_flag(fake_config: FakeConfig) -> None:
            assert fake_config.get("feature.enabled") is True
    """
    data: dict[str, Any] = getattr(request, "param", {})
    return FakeConfig(data)


# ---------------------------------------------------------------------------
# Utility fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_data() -> Any:
    """Pytest fixture for test data factory."""
    return test_data_factory


@pytest.fixture
def assertions() -> Any:
    """Pytest fixture for test assertions."""
    return test_assertions


__all__ = [
    "ContainerTestFixture",
    "assertions",
    "fake_cache",
    "fake_clock",
    "fake_command_bus",
    "fake_config",
    "fake_event_bus",
    "fake_logger",
    "fake_metrics",
    "fake_query_bus",
    "fake_state_store",
    "fake_unit_of_work",
    "test_bed",
    "test_container",
    "test_data",
]
