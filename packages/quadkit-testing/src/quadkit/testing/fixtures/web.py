from __future__ import annotations

"""Pytest fixtures for Quadkit Web testing."""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import pytest

from quadkit.testing.clients.web import WebTestBed, WebTestClient

# Prefer pytest-asyncio's async fixtures when available; fall back to pytest.fixture.
_async_fixture: Callable[..., Any] = pytest.fixture
try:
    import pytest_asyncio
except ImportError:
    pass
else:
    _async_fixture = pytest_asyncio.fixture


@_async_fixture
async def web_test_bed() -> Any:
    """Fixture for WebTestBed backed by a real (headless) WebProvider."""
    from quadkit.web.di.provider import WebProvider

    test_bed = WebTestBed(WebProvider())
    async with test_bed as tb:
        yield tb


@pytest.fixture
def web_test_client() -> Any:
    """Fixture for WebTestClient."""
    mock_app = Mock()
    return WebTestClient(mock_app)


@pytest.fixture
def mock_web_request() -> Any:
    """Fixture for mock request."""
    mock_starlette_request = Mock()
    mock_starlette_request.method = "GET"
    mock_starlette_request.url = "http://testserver/test"
    mock_starlette_request.headers = {"Content-Type": "application/json"}
    mock_starlette_request.query_params = {}
    mock_starlette_request.path_params = {}
    mock_starlette_request.state = Mock()

    return mock_starlette_request


@pytest.fixture
def mock_web_response() -> Any:
    """Fixture for mock response."""
    from quadkit.web import JSONResponse

    return JSONResponse({"test": "data"})


@_async_fixture
async def authenticated_web_client(web_test_client: WebTestClient) -> Any:
    """Fixture for authenticated test client."""
    # Simulation based on WebTestClient.as_user
    web_test_client.as_user("test-user")
    return web_test_client


@pytest.fixture
def sample_web_user_data() -> Any:
    """Sample user data for testing."""
    return {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "roles": ["user"],
    }


@pytest.fixture
def sample_web_post_data() -> Any:
    """Sample POST data for testing."""
    return {
        "title": "Test Post",
        "content": "This is a test post content",
        "author_id": 1,
    }


@_async_fixture
async def app_bed() -> Any:
    """Yield an :class:`~quadkit.testing.testbed.AppTestBed` for the default app.

    Auto-detects ``create_app`` from ``src/*/app.py`` (same convention as
    ``quadkit run``).  Tests that need a specific factory should call
    :meth:`~quadkit.testing.testbed.AppTestBed.from_factory` directly::

        async with AppTestBed.from_factory("my_app.app:create_app") as bed:
            resp = await bed.client.get("/health")

    Yields:
        A booted :class:`~quadkit.testing.testbed.AppTestBed` or ``None``
        when no entry point can be found.
    """
    from quadkit.cli.registry.server import discover_entry_point
    from quadkit.testing.harness.testbed import AppTestBed

    file_path = discover_entry_point()
    if file_path is None:
        yield None
        return

    import ast
    from pathlib import Path

    source = Path(file_path).read_text()
    tree = ast.parse(source)
    attr = next(
        (
            node.name
            for node in ast.iter_child_nodes(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == "create_app"
        ),
        None,
    )
    if attr is None:
        yield None
        return

    # Convert file path to dotted module: src/my_app/app.py → my_app.app
    parts = list(Path(file_path).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    module_path = ".".join(parts)
    factory_target = f"{module_path}:{attr}"

    async with AppTestBed.from_factory(factory_target) as bed:
        yield bed


__all__ = [
    "app_bed",
    "authenticated_web_client",
    "mock_web_request",
    "mock_web_response",
    "sample_web_post_data",
    "sample_web_user_data",
    "web_test_bed",
    "web_test_client",
]
