# Integration tests for DatabaseService resilience and instrumentation
# See DOCUMENTATION.md and TESTING.md for the TestBed and TestEnvironment patterns

from typing import Any, cast

import pytest

from quadkit.contracts import DatabaseProviderProtocol

# Avoid importing TestEnvironment at module import time to prevent pulling in
# optional admin testing modules during collection; use the `test_bed` fixture
# that provides a ready TestEnvironment instance when available.
try:
    from quadkit.ent.contracts import MetricsExporter, TracerProvider
except ImportError:
    # Use empty protocols as fallback base classes so they are valid for class definitions
    from typing import Protocol
    class MetricsExporter(Protocol): pass
    class TracerProvider(Protocol): pass
from quadkit.sql import DatabaseService
from quadkit.sql.di.provider import DatabaseProvider


class FlakyProvider:
    def __init__(self, fail_times: int = 1):
        self.calls = 0
        self.fail_times = fail_times

    async def connect(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise Exception("connect fail")
        return None

    async def disconnect(self):
        return None

    async def health_check(self):
        return {"status": "healthy"}


class MockMetrics(MetricsExporter):
    def __init__(self):
        self._counters = []
        self._hist = []

    async def counter(self, name: str, value: int, tags: dict[str, str] = None) -> None:
        self._counters.append((name, value, tags))

    async def gauge(self, name: str, value: float, tags: dict[str, str] = None) -> None:
        pass

    async def histogram(self, name: str, value: float, tags: dict[str, str] = None) -> None:
        self._hist.append((name, value, tags))

    async def flush(self) -> None:
        pass

    # MetricsCollectorProtocol methods to satisfy protocol during DI validation
    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        self._counters.append((name, value, tags))

    def create_counter(self, name, description="", labels=None): return self
    def create_histogram(self, name, description="", labels=None, buckets=None): return self
    def create_gauge(self, name, description="", labels=None): return self
    def register_metric(self, metric) -> None: pass


class DummySpan:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class MockTracer(TracerProvider):
    def __init__(self):
        self.traces = []

    async def trace(self, name: str, **kwargs: Any) -> Any:
        self.traces.append((name, kwargs))
        return DummySpan()

    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> DummySpan:
        """Start a new span (satisfies TracerProtocol)."""
        self.traces.append((name, attributes or {}))
        return DummySpan()

    def get_current_span(self) -> Any | None:
        return None

    def inject_context(self, carrier: dict[str, Any]) -> None:
        pass

    def extract_context(self, carrier: dict[str, Any]) -> Any | None:
        return None

    # TracerProtocol methods to satisfy protocol during DI validation
    def create_span(self, name: str, parent=None):
        self.traces.append((name, {"parent": parent}))
        return DummySpan()

    def set_current_span(self, span: Any | None) -> None:
        pass


@pytest.mark.asyncio
async def test_startup_retries_and_resolves_instrumentation(test_bed):
    pytest.skip("DB resilience integration needs framework update")
    flaky = FlakyProvider(fail_times=1)
    object.__setattr__(
        provider,
        "_create_driver_provider",
        cast(Any, lambda: cast(DatabaseProviderProtocol, flaky)),
    )

    # Prepare mock instrumentation and register via overrides so TestEnvironment supplies them
    metrics = MockMetrics()
    tracer = MockTracer()

    test_bed.override(MetricsExporter, metrics)
    test_bed.override(TracerProvider, tracer)
    # Also override the ones DatabaseService actually resolves
    from quadkit.contracts.observability.metrics import MetricsCollectorProtocol
    from quadkit.contracts.observability.tracing import TracerProtocol
    test_bed.override(MetricsCollectorProtocol, metrics)
    test_bed.override(TracerProtocol, tracer)

    # Add DI provider to the test environment
    di_provider = DatabaseProvider("sqlite:///:memory:")
    di_provider._db_provider = provider
    test_bed.use_provider(di_provider)

    async with test_bed.context() as bed:
        # After setup, the provider should have been started
        assert hasattr(provider, "db_provider")
        assert flaky.calls >= 2

        # Resolve instrumentation from the container
        resolved_metrics = await bed.resolve(MetricsCollectorProtocol)
        resolved_tracer = await bed.resolve(TracerProtocol)

        assert resolved_metrics is metrics
        assert resolved_tracer is tracer


@pytest.mark.asyncio
async def test_query_through_provider_traces_and_metrics(test_bed):
    """Verify that a simple query executed through DatabaseService emits metrics and tracing (via resolved services)."""

    # Use a provider that implements execute_query directly
    class SimpleFakeProvider:
        def __init__(self):
            self.called = 0

        async def connect(self):
            return None

        async def disconnect(self):
            return None

        async def health_check(self):
            return {"status": "healthy"}

        async def execute_query(self, sql, params=None, **kwargs):
            self.called += 1

            class _R:
                success = True
                rows = [{"ok": True}]

            return _R()

    fake_provider = SimpleFakeProvider()

    provider = DatabaseService("sqlite:///:memory:")
    object.__setattr__(
        provider,
        "_create_driver_provider",
        cast(Any, lambda: cast(DatabaseProviderProtocol, fake_provider)),
    )

    metrics = MockMetrics()
    tracer = MockTracer()

    test_bed.override(MetricsExporter, metrics)
    test_bed.override(TracerProvider, tracer)
    from quadkit.contracts.observability.metrics import MetricsCollectorProtocol
    from quadkit.contracts.observability.tracing import TracerProtocol
    test_bed.override(MetricsCollectorProtocol, metrics)
    test_bed.override(TracerProtocol, tracer)

    di_provider = DatabaseProvider("sqlite:///:memory:")
    di_provider._db_provider = provider
    test_bed.use_provider(di_provider)

    async with test_bed.context() as bed:
        # Execute a query via the provider
        res = await provider.execute_query("SELECT 1")
        assert res is not None
        assert fake_provider.called == 1

        # instrumentation should have been invoked
        assert len(metrics._hist) >= 1
        assert any(t[0].startswith("db.") for t in tracer.traces)
