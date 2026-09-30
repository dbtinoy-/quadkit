# tests/conftest.py
import os
import sys

import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None  # type: ignore[assignment]

# Resolve dependencies via uv workspace
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ensure local packages are importable when running tests directly
# this mirrors the similar logic in other quadkit packages and is
# intentionally simple so that pytest can find `quadkit.sql` and
# `quadkit.contracts` even though they live outside the tests
# directory during development.
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "..", "quadkit-contracts", "src"))

# Import TestEnvironment lazily inside the fixture to avoid importing
# optional test utilities (e.g., admin mocks) at module import time which
# may pull in optional packages that are not available in all test
# environments.

# The fixtures the test suite expects (clean_database, seeded_database, etc.)
# are provided by quadkit.testing.fixtures.db; import them lazily below in
# a guarded manner where possible.
_lazy_testing_imported = False
_clean_database = None
_db_test_bed = None
_mock_connection = None
_mock_connection_pool = None
_sample_order_data = None
_sample_product_data = None
_sample_user_data = None
_seeded_database = None
_test_database_client = None

try:
    # Try to import fixtures early but don't fail if optional packages aren't present.
    from quadkit.testing.fixtures.db import (
        clean_database,
        db_test_bed,
        mock_connection,
        mock_connection_pool,
        sample_order_data,
        sample_product_data,
        sample_user_data,
        seeded_database,
        test_database_client,
    )

    _lazy_testing_imported = True
    _clean_database = clean_database
    _db_test_bed = db_test_bed
    _mock_connection = mock_connection
    _mock_connection_pool = mock_connection_pool
    _sample_order_data = sample_order_data
    _sample_product_data = sample_product_data
    _sample_user_data = sample_user_data
    _seeded_database = seeded_database
    _test_database_client = test_database_client
except (ImportError, AttributeError):
    # Best-effort: some developer environments don't have quadkit-testing avail.
    pass

# If fixtures were successfully imported, expose them under their expected names
if _lazy_testing_imported:
    clean_database = _clean_database
    db_test_bed = _db_test_bed
    mock_connection = _mock_connection
    mock_connection_pool = _mock_connection_pool
    sample_order_data = _sample_order_data
    sample_product_data = _sample_product_data
    sample_user_data = _sample_user_data
    seeded_database = _seeded_database
    test_database_client = _test_database_client


@ pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def test_bed():
    """Returns a TestBed with in-memory drivers pre-configured.

    Importing `TestEnvironment` lazily ensures we don't try to import heavy
    admin/testing modules at collection time (which can pull optional
    dependencies that are not installed). If `quadkit.testing` isn't
    available in this environment, skip the dependent tests gracefully.
    """
    try:
        import importlib

        testing = importlib.import_module("quadkit.testing.fixtures.bed")
        TestEnvironment = getattr(testing, "TestEnvironment")
    except (ImportError, AttributeError):
        pytest.skip(
            "quadkit.testing.TestEnvironment not available in this environment",
        )

    async with TestEnvironment("test-db") as bed:
        yield bed


# --- In-process database fixtures (no live services, no Docker) ---
# These fixtures let provider/repository tests run against an in-memory
# SQLite database, with a real PostgreSQL preferred when one is reachable.


@pytest.fixture(scope="session")
def integration_config():
    """Return integration service configuration from the environment."""
    from quadkit.testing.integration.config import IntegrationTestConfig

    return IntegrationTestConfig.from_env()


@ pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def sqlite_provider():
    """Yield a connected in-memory SQLite provider (no external services)."""
    from quadkit.sql.providers.sqlite_provider import SQLiteProvider

    provider = SQLiteProvider(":memory:")
    await provider.connect()
    try:
        yield provider
    finally:
        await provider.disconnect()


@ pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def postgres_provider(integration_config):
    """Yield PostgreSQL when reachable, else an in-process SQLite provider.

    The Docker-free fallback keeps PostgreSQL-flavoured integration tests
    runnable without a pre-started Docker Compose stack.
    """
    from quadkit.sql.providers.postgres_provider import PostgresProvider
    from quadkit.sql.providers.sqlite_provider import SQLiteProvider
    from quadkit.testing.integration.probes import ServiceProbe

    if await ServiceProbe.check_postgres(integration_config.postgres_dsn_raw):
        provider = PostgresProvider(integration_config.postgres_dsn_raw)
    else:
        provider = SQLiteProvider(":memory:")
    await provider.connect()
    try:
        yield provider
    finally:
        await provider.disconnect()


# --- Test utilities for resilience & instrumentation ---
class _FakeMetrics:
    def __init__(self):
        self.histograms: list[tuple[str, float]] = []
        self.counters: dict[str, int] = {}

    async def histogram(
        self, name: str, value: float, tags: dict | None = None,
    ) -> None:
        self.histograms.append((name, value))

    async def counter(self, name: str, value: int, tags: dict | None = None) -> None:
        self.counters[name] = self.counters.get(name, 0) + value


class _DummySpan:
    def __init__(self, trace_name: str, op: str | None = None):
        self.trace_name = trace_name
        self.op = op
        self.entered = False
        self.exited = False

    # Async context manager (used by old tracer.trace())
    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True

    # Sync context manager (used by tracer.start_span())
    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited = True


class _FakeTracer:
    def __init__(self):
        self.spans: list[_DummySpan] = []

    async def trace(self, name: str, op: str | None = None):
        span = _DummySpan(name, op)
        self.spans.append(span)
        return span

    def start_span(self, name: str, **kwargs):
        """Synchronous context-manager facade used by DatabaseService."""
        span = _DummySpan(name, None)
        self.spans.append(span)
        span.entered = True  # Mark entered immediately for the 'with' block.
        return span


class _FakePipeline:
    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.calls = 0

    async def execute(self, fn):
        """Execute the callable, retrying up to `fail_times` on exception."""
        attempts = 0
        while True:
            self.calls += 1
            attempts += 1
            try:
                return await fn()
            except (RuntimeError, OSError, ConnectionError, ValueError, TypeError):
                if attempts > self.fail_times:
                    raise
                # transient error, retry immediately
                continue


@pytest.fixture
def fake_metrics():
    return _FakeMetrics()


@pytest.fixture
def fake_tracer():
    return _FakeTracer()


@pytest.fixture
def make_fake_pipeline():
    def _make(fail_times: int = 0):
        return _FakePipeline(fail_times=fail_times)

    return _make


# Ensure any real aiosqlite connections created during tests are closed at session teardown
@pytest.fixture(scope="session", autouse=True)
def _aiosqlite_connection_tracker():
    try:
        import aiosqlite
    except ImportError:
        # aiosqlite not installed; nothing to track
        yield
        return

    created: list = []
    original_connect = getattr(aiosqlite, "connect", None)

    if original_connect is None:
        yield
        return

    def _tracked_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        created.append(conn)
        return conn

    # Monkeypatch connect globally for the test session
    setattr(aiosqlite, "connect", _tracked_connect)

    try:
        yield
    finally:
        # Close all tracked connections
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)

            async def _close_all():
                for c in created:
                    try:
                        await c.close()
                    except (RuntimeError, OSError, ConnectionError):
                        pass

            loop.run_until_complete(_close_all())
        finally:
            try:
                loop.close()
            except RuntimeError:
                pass


@pytest.fixture(scope="session", autouse=True)
def _shorten_pool_poll_interval():
    """Shorten AbstractConnectionPool.DEFAULT_POLL_INTERVAL for tests to speed up waiting loops."""
    try:
        from quadkit.sql.pool.connection import AbstractConnectionPool
    except ImportError:
        yield
        return

    orig = getattr(AbstractConnectionPool, "DEFAULT_POLL_INTERVAL", None)
    AbstractConnectionPool.DEFAULT_POLL_INTERVAL = 0.01
    try:
        yield
    finally:
        if orig is None:
            delattr(AbstractConnectionPool, "DEFAULT_POLL_INTERVAL")
        else:
            AbstractConnectionPool.DEFAULT_POLL_INTERVAL = orig


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db_artifacts():
    """Remove stray test.db files created by sqlite fixture providers during test runs."""
    import os
    from pathlib import Path

    yield

    # Remove any test.db files that tests may have left in common locations
    candidates = [
        Path(__file__).resolve().parent / "test.db",
        Path(__file__).resolve().parents[1] / "test.db",
        Path.cwd() / "test.db",
    ]
    for candidate in candidates:
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass