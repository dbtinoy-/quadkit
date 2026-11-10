"""Pytest configuration for Result pattern tests."""

import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

if pytest_asyncio:
    pytestmark = pytest.mark.asyncio
