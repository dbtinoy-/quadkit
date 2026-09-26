import pytest

from quadkit.sql.providers import DatabaseService


class _DummyDBProvider:
    def __init__(self, result=None, raise_exc: Exception | None = None):
        self.result = result
        self.raise_exc = raise_exc

    async def execute_query(self, sql, params=None, **kwargs):
        if self.raise_exc:
            raise self.raise_exc
        return self.result


@pytest.mark.asyncio
async def test_wrap_operation_emits_metrics_and_tracing(fake_metrics, fake_tracer):
    provider = DatabaseService("sqlite:///:memory:")
    provider.db_provider = _DummyDBProvider(result=[{"id": 1}])
    provider.metrics = fake_metrics
    provider.tracer = fake_tracer

    res = await provider.execute_query("select 1")
    assert res.rows == [{"id": 1}]

    # metrics: some db.query histogram and at least one db.query counter
    assert any("db.query" in n for n, _ in fake_metrics.histograms)
    assert any(k.startswith("db.query") for k in fake_metrics.counters.keys())

    # tracer: one span created
    assert len(fake_tracer.spans) == 1
    span = fake_tracer.spans[0]
    assert span.entered and span.exited


@pytest.mark.asyncio
async def test_wrap_operation_emits_error_counter_on_exception(
    fake_metrics, fake_tracer,
):
    provider = DatabaseService("sqlite:///:memory:")
    provider.db_provider = _DummyDBProvider(raise_exc=RuntimeError("boom"))
    provider.metrics = fake_metrics
    provider.tracer = fake_tracer

    with pytest.raises(RuntimeError):
        await provider.execute_query("select 1")

    assert fake_metrics.counters.get("db.query.errors", 0) == 1
    # tracer still created even on error
    assert len(fake_tracer.spans) == 1
