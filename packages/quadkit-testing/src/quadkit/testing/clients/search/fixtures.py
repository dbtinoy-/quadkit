"""
Pytest fixtures for search testing.

Provides comprehensive fixtures for testing search components,
indexing, querying, and backend operations.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

try:
    import pytest_asyncio
except ImportError:
    # Optional dev dependency
    pytest_asyncio = None  # type: ignore[assignment]

from quadkit.testing.clients.search.client import (
    MockSearchBackend,
    SearchTestBed,
    SearchTestClient,
)


@pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def search_test_bed() -> AsyncGenerator[SearchTestBed, None]:
    """Pytest fixture for search test bed."""
    test_bed = SearchTestBed()
    await test_bed.setup()
    try:
        yield test_bed
    finally:
        await test_bed.teardown()


@pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def search_test_client(
    search_test_bed: SearchTestBed,
) -> AsyncGenerator[SearchTestClient, None]:
    """Pytest fixture for search test client."""
    client = SearchTestClient(search_test_bed)
    yield client
    await client.stop_provider()


@pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def search_backend(
    search_test_client: SearchTestClient,
) -> AsyncGenerator[MockSearchBackend, None]:
    """Pytest fixture for search backend."""
    async with search_test_client.search_context() as backend:
        yield backend


@pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def mock_search_engine(
    search_test_client: SearchTestClient,
) -> AsyncGenerator[MockSearchBackend, None]:
    """Pytest fixture for mock search engine."""
    engine = await search_test_client.create_search_engine()
    yield engine
