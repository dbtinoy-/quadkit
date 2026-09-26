from pathlib import Path
import sys

import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

# Import from the consolidated testing package
from quadkit.testing import TestEnvironment

# Load core testing fixtures
try:
    import importlib

    importlib.import_module("quadkit.testing.fixtures.core")
except ImportError:
    pass

# Load integration fixtures for infrastructure services


@pytest.fixture
def app():
    """Returns a fresh Application instance for every test."""
    from quadkit.app import Application

    return Application()


@ pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def test_bed(app):
    """Returns a TestBed with in-memory drivers pre-configured."""
    async with TestEnvironment(app) as bed:
        yield bed
