"""Shared test configuration and fixtures for quadkit-middleware."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.middleware.core.chain import MiddlewareChain
from quadkit.middleware.core.exception_filters import ExceptionFilterChain
from quadkit.middleware.core.registry import MiddlewareRegistry


@pytest.fixture
def middleware_chain() -> MiddlewareChain:
    return MiddlewareChain()


@pytest.fixture
def middleware_registry() -> MiddlewareRegistry:
    return MiddlewareRegistry()


@pytest.fixture
def filter_chain() -> ExceptionFilterChain:
    return ExceptionFilterChain()


@pytest.fixture
def dummy_context() -> dict[str, Any]:
    return {"request_id": "test-123", "path": "/test"}


@pytest.fixture
def passthrough_handler() -> Any:
    async def handler(ctx: Any) -> Any:
        return ctx

    return handler
