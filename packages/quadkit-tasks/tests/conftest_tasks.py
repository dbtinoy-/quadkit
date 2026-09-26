# tests/conftest.py
import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None
from quadkit.testing import TestEnvironment


@ pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def test_bed():
    """Async TestBed fixture for testing."""
    bed = TestEnvironment()
    async with bed.context():
        yield bed


@ pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def tasks_test_bed():
    """Async TestBed fixture specifically for tasks testing."""
    bed = TestEnvironment()
    async with bed.context():
        yield bed
