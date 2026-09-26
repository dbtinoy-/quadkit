# tests/conftest.py
import os
import sys
from pathlib import Path

import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

# Resolve dependencies via uv workspace
BASE_DIR = Path(__file__).parent

try:
    from quadkit.testing import TestEnvironment
except ImportError:
    # Fallback/stub if really needed, but with correct path it should work
    class TestEnvironment:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def context(self):
            return self


@ pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def test_bed():
    """Async TestEnvironment fixture for testing."""
    bed = TestEnvironment()
    async with bed.context():
        yield bed
