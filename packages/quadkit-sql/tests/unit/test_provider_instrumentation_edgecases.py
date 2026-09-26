import pytest

from quadkit.sql.di.provider import DatabaseProvider
from quadkit.sql.providers import DatabaseService


class _MetricsRaises:
    async def histogram(self, *args, **kwargs):
        raise RuntimeError("metrics fail")

    async def counter(self, *args, **kwargs):
        raise RuntimeError("metrics fail")


class _Container:
    def __init__(self, metrics=None, tracer=None):
        self._metrics = metrics
        self._tracer = tracer
        self._singletons = {}

    async def resolve(self, protocol):
        """Resolve a protocol from the container."""
        if getattr(protocol, "__name__", "").endswith("MetricsCollectorProtocol"):
            return self._metrics
        name = getattr(protocol, "__name__", "")
        if name in ("TraceProvider", "TracerProtocol") or name.endswith(
            "TraceProvider"
        ):
            return self._tracer
        return None

    def singleton(self, key, instance=None, *, factory=None, validate=True):
        """Store created instance for optional later use."""
        if instance is not None:
            self._singletons[key] = instance
        elif factory is not None:
            self._singletons[key] = factory() if callable(factory) else factory
        elif callable(key):
            self._singletons[key] = key()

    def scoped(self, key, factory, validate=True, *, name=None):
        """Emulate scoped registration as singleton for tests."""
        self._singletons[key] = factory

    def transient(self, key, factory, validate=True):
        """Emulate transient registration as singleton for tests."""
        self._singletons[key] = factory

    def has(self, service_type):
        """Check if a service is registered."""
        return service_type in self._singletons


@pytest.mark.asyncio
async def test_register_resolves_metrics_and_tracer(fake_metrics, fake_tracer):
    from unittest.mock import AsyncMock, patch

    di_provider = DatabaseProvider("sqlite:///:memory:")
    container = _Container(metrics=fake_metrics, tracer=fake_tracer)

    await di_provider.register(container)

    # The underlying DatabaseService should not have metrics/tracer yet
    db_provider = di_provider._db_provider
    assert db_provider.metrics is None
    assert db_provider.tracer is None

    # boot() resolves metrics/tracer from the container
    with patch.object(di_provider, "_boot_admin_widgets", AsyncMock()):
        await di_provider.boot(container)

    assert db_provider.metrics is fake_metrics
    assert db_provider.tracer is fake_tracer


@pytest.mark.asyncio
async def test_wrap_operation_swallows_metrics_exceptions(fake_tracer):
    provider = DatabaseService("sqlite:///:memory:")
    provider.tracer = fake_tracer
    provider.metrics = _MetricsRaises()

    class _DB:
        async def execute_query(self, sql, params=None, **kwargs):
            return [{"ok": True}]

    provider.db_provider = _DB()

    # Should not raise even if metrics methods fail
    res = await provider.execute_query("select 1")
    assert res.rows == [{"ok": True}]


@pytest.mark.asyncio
async def test_wrap_operation_without_tracer_still_records_metrics(fake_metrics):
    provider = DatabaseService("sqlite:///:memory:")
    provider.tracer = None
    provider.metrics = fake_metrics

    class _DB:
        async def execute_query(self, sql, params=None, **kwargs):
            return [{"ok": True}]

    provider.db_provider = _DB()

    res = await provider.execute_query("select 1")
    assert res.rows == [{"ok": True}]
    assert fake_metrics.counters.get("db.query.count") == 1
