"""Pytest fixtures for Quadkit Tasks testing."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest

from quadkit.testing.clients.tasks import (
    TaskTestBed,
    TaskTestClient,
    TaskTestData,
)

pytest_asyncio: Any = None
try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

# pytest_asyncio is optional, so the decorator is resolved at runtime and
# mypy cannot see through the conditional; Any keeps it from marking every
# decorated fixture untyped.
_fixture: Any = pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture


@_fixture
async def task_test_bed() -> AsyncGenerator[TaskTestBed, None]:
    """Fixture for a fully set-up TaskTestBed (torn down after the test)."""
    bed = TaskTestBed()
    await bed.setup()
    try:
        yield bed
    finally:
        await bed.teardown()


@_fixture
async def task_test_client(
    task_test_bed: TaskTestBed,
) -> AsyncGenerator[TaskTestClient, None]:
    """Fixture for a TaskTestClient bound to the bed."""
    client = task_test_bed.create_test_client()
    try:
        yield client
    finally:
        await client.stop_provider()


@pytest.fixture
def sample_task_data() -> list[dict[str, Any]]:
    """Fixture for sample task data."""
    return TaskTestData.sample_tasks()


__all__ = ["sample_task_data", "task_test_bed", "task_test_client"]
