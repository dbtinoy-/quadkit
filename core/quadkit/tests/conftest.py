# tests/conftest.py
from typing import Any

import pytest

pytest_asyncio: Any = None
try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

# ``quadkit.testing`` is also imported lazily (inside the ``test_bed``
# fixture): its ``fixtures.bed`` module imports ``quadkit.app.base`` at
# module level, which would pull the whole app chain in before coverage
# starts measuring (see the ``app`` fixture docstring for the full rationale).
# find_spec probes availability without executing the package.
import importlib.util

_testing_available = importlib.util.find_spec("quadkit.testing") is not None


def _get_test_environment():
    """Lazily import TestEnvironment after coverage has started."""
    from quadkit.testing import TestEnvironment

    return TestEnvironment


@pytest.fixture
def app():
    """Returns a fresh Application instance for every test.

    The heavy ``quadkit.app`` import is deferred into the fixture body so it
    executes *after* coverage starts measuring (pytest-cov starts after
    conftest import). Importing it at module level would leave the whole
    app-import chain's module-level statements uncounted, deflating the
    coverage gate without the tests ever touching those lines.
    """
    from quadkit.app import Application

    return Application()


if _testing_available:
    _fixture = pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture

    @_fixture
    async def test_bed(app):
        """Returns a TestBed with in-memory drivers pre-configured."""
        test_environment = _get_test_environment()
        async with test_environment(app) as bed:
            yield bed
