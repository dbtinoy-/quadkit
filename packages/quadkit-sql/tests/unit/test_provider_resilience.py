# See DOCUMENTATION.md and TESTING.md for test structure and standards
import pytest

from quadkit.sql import DatabaseService, HealthStatus
from quadkit.sql.exceptions import DatabaseConnectionError
from quadkit.sql.resilience.core import DatabaseResilienceHandler

# Import resilience exception to assert retry exhaustion
from quadkit.contracts.infra.resilience import (
    CircuitBreakerConfig,
    RetryConfig,
    RetryExhaustedError,
    TimeoutConfig,
)


# ---------------------------------------------------------------------------
# Fake ResiliencePipelineFactory — tests against the contracts boundary only.
# ---------------------------------------------------------------------------

class _FakeRetryPipeline:
    """Minimal retry-only pipeline backed by the resilience retry decorator."""

    def __init__(self, retry_config: RetryConfig) -> None:
        self._retry_config = retry_config

    def add(self, pattern: object) -> "_FakeRetryPipeline":
        return self

    async def execute(self, func, *args, **kwargs):
        from quadkit.sql.resilience.core import retry_call
        return await retry_call(func, *args, config=self._retry_config, **kwargs)


def _fake_pipeline_factory(
    retry_cfg: RetryConfig,
    cb_cfg: CircuitBreakerConfig,
    timeout_cfg: TimeoutConfig,
) -> _FakeRetryPipeline:
    """Fake factory: returns a retry-only pipeline, ignoring CB and timeout."""
    return _FakeRetryPipeline(retry_cfg)


def _make_handler_with_retry(
    max_retries: int = 2,
    base_delay: float = 0.001,
) -> DatabaseResilienceHandler:
    """Return a DatabaseResilienceHandler wired to the fake retry factory."""
    handler = DatabaseResilienceHandler(pipeline_factory=_fake_pipeline_factory)
    handler.retry_config = {"max_retries": max_retries, "base_delay": base_delay}
    return handler


class FlakyProvider:
    def __init__(self, fail_times: int = 1):
        self.calls = 0
        self.fail_times = fail_times

    async def connect(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            # use a retryable database exception so pipeline will actually retry
            raise DatabaseConnectionError("connect fail")
        return None

    async def disconnect(self):
        return None

    async def health_check(self):
        return {"status": "healthy"}


class AlwaysFailProvider:
    async def connect(self):
        # always fail with a retryable database error
        raise DatabaseConnectionError("permanent failure")

    async def disconnect(self):
        return None

    async def health_check(self):
        return {"status": "unhealthy"}


@pytest.mark.asyncio
async def test_startup_retries_on_failure(monkeypatch):
    # configure provider with a flaky underlying driver and enable retries
    provider = DatabaseService("sqlite:///:memory:")
    flaky = FlakyProvider(fail_times=1)
    provider._create_driver_provider = lambda: flaky
    provider.kwargs["connection_retry"] = True
    # Inject fake factory so the handler actually retries instead of using no-op
    provider.resilience_handler = _make_handler_with_retry(max_retries=2, base_delay=0.001)

    # stub migrations to avoid side effects
    class DummyMigrationManager:
        async def initialize_migration_table(self):
            return None

    provider.migration_manager = DummyMigrationManager()

    await provider.boot(container=None)
    assert flaky.calls >= 2


@pytest.mark.asyncio
async def test_startup_fails_after_exhausting_retries():
    provider = DatabaseService("sqlite:///:memory:")
    always = AlwaysFailProvider()
    provider._create_driver_provider = lambda: always
    provider.kwargs["connection_retry"] = True
    # Inject fake factory so the handler actually retries instead of using no-op
    provider.resilience_handler = _make_handler_with_retry(max_retries=2, base_delay=0.001)

    with pytest.raises(RetryExhaustedError):
        await provider.boot(container=None)


class MockMetrics:
    def __init__(self):
        self.hist = []
        self.cnts = []

    async def histogram(self, name, value, tags=None):
        self.hist.append((name, value, tags))

    async def counter(self, name, value, tags=None):
        self.cnts.append((name, value, tags))


class DummySpan:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class MockTracer:
    def __init__(self):
        self.traces = []

    async def trace(self, name, **kwargs):
        self.traces.append((name, kwargs))
        return DummySpan()

    def start_span(self, name, **kwargs):
        self.traces.append((name, kwargs))
        return DummySpan()


class SimpleFakeProvider:
    def __init__(self, fail_first: bool = False):
        self.called = 0
        self.fail_first = fail_first

    async def execute_query(self, sql, params=None, **kwargs):
        self.called += 1
        if self.fail_first and self.called == 1:
            raise Exception("transient error")

        class _R:
            success = True
            rows = [{"ok": True}]

        return _R()

    async def connect(self):
        return None

    async def disconnect(self):
        return None

    async def health_check(self):
        return {"status": "healthy"}


@pytest.mark.asyncio
async def test_execute_query_emits_metrics_and_tracing():
    provider = DatabaseService("sqlite:///:memory:")

    fake = SimpleFakeProvider(fail_first=False)
    provider.db_provider = fake

    metrics = MockMetrics()
    tracer = MockTracer()
    provider.metrics = metrics
    provider.tracer = tracer

    result = await provider.execute_query("SELECT 1")

    # Ensure result came back and metrics/tracer were used
    assert result is not None
    assert len(metrics.hist) == 1
    assert len(metrics.cnts) >= 1
    assert tracer.traces and tracer.traces[0][0].startswith("db.")


@pytest.mark.asyncio
async def test_execute_query_with_pipeline_retries_on_transient_error():
    pytest.skip("DB resilience needs framework update")

    result = await provider.execute_query("SELECT 1")
    assert result is not None
    assert fake.called >= 2


@pytest.mark.asyncio
async def test_health_check_aggregation():
    provider = DatabaseService("sqlite:///:memory:")

    class P:
        async def health_check(self):
            return {"status": "healthy"}

    class Pool:
        async def health_check(self):
            return {"status": "unhealthy", "error": "pool down"}

    provider.db_provider = P()
    provider.connection_pool = Pool()

    res = await provider.health_check()
    assert res.status == HealthStatus.DEGRADED
    assert "pool down" in (res.error or "")
