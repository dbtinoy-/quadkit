from pathlib import Path
import sys

import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

# Import from the consolidated testing package
try:
    from quadkit.testing import TestEnvironment
except ImportError:
    TestEnvironment = None

# Load core testing fixtures
try:
    import importlib

    importlib.import_module("quadkit.testing.fixtures.core")
except ImportError:
    pass

# Lightweight 'mocker' fixture for environments without pytest-mock installed
# Many tests rely on the 'mocker' fixture; if pytest-mock isn't available in
# the execution environment, provide a minimal compatible helper using
# unittest.mock so tests can still run.
import unittest.mock as _mock

from quadkit.app import Application


class _SimpleMocker:
    MagicMock = _mock.MagicMock
    AsyncMock = _mock.AsyncMock

    def __init__(self):
        self._started_patches: list[_mock._patch] = []

    def patch(self, *args, **kwargs):
        # Start the patch immediately and return the mocked object (similar to pytest-mock)
        p = _mock.patch(*args, **kwargs)
        started = p.start()
        # Keep track so we can stop them at test teardown if needed
        self._started_patches.append(p)
        return started

    def stop_all(self):
        for p in reversed(self._started_patches):
            try:
                p.stop()
            except (RuntimeError, AttributeError):
                pass
        self._started_patches.clear()


@pytest.fixture
def mocker(request):
    m = _SimpleMocker()

    # Ensure any started patches are stopped after each test
    def _finalizer():
        m.stop_all()

    request.addfinalizer(_finalizer)
    return m


@pytest.fixture
def app():
    """Returns a fresh Application instance for every test."""
    return Application()


@pytest.fixture
async def test_bed(app):
    """Returns a TestBed with in-memory drivers pre-configured."""
    if TestEnvironment is None:
        # Fallback if TestEnvironment not available
        yield None
    else:
        async with TestEnvironment(app) as bed:
            yield bed
