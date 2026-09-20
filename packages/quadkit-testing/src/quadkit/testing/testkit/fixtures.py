"""Pytest fixtures for common unit test setups.

Import this module in your ``conftest.py`` or test files to obtain
pre-configured in-memory fakes without manual setup.

Example ``conftest.py``::

    from quadkit.testing.testkit.fixtures import test_environment, test_event_bus  # noqa: F401

Or use directly in tests::

    from quadkit.testing.testkit.fixtures import test_container

    async def test_something(test_container):
        service = await test_container.resolve(MyService)
        ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from quadkit.testing.testkit.environment import TestEnvironment

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from quadkit.di.container import Container
    from quadkit.testing.memory.event_bus import InMemoryEventBus


@pytest_asyncio.fixture
async def test_environment() -> AsyncGenerator[TestEnvironment, None]:
    """Yield a :class:`TestEnvironment` set up with all in-memory fakes.

    The environment is torn down (handlers cleared) after the test.
    """
    env = await TestEnvironment().setup()
    yield env
    env.teardown()


@pytest.fixture
def test_container(test_environment: TestEnvironment) -> Container:
    """Yield the :class:`~quadkit.di.container.Container` from the test environment."""
    return test_environment.container


@pytest.fixture
def test_event_bus(test_environment: TestEnvironment) -> InMemoryEventBus:
    """Yield the :class:`~quadkit.memory.event_bus.InMemoryEventBus` from the test environment."""
    return test_environment.event_bus


__all__ = [
    "test_container",
    "test_environment",
    "test_event_bus",
]
