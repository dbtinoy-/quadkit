"""Unit tests for exporters"""

import pytest

from quadkit.monitor.backends.exporters import (
    HAS_PROMETHEUS,
    PrometheusMetricsExporter,
)


@pytest.mark.skipif(not HAS_PROMETHEUS, reason="prometheus-client not installed")
@pytest.mark.asyncio
async def test_prometheus_exporter_counter():
    exp = PrometheusMetricsExporter()
    await exp.counter("test_counter", 1, {"env": "test"})
    await exp.counter("test_counter", 2, {"env": "test"})


@pytest.mark.skipif(not HAS_PROMETHEUS, reason="prometheus-client not installed")
@pytest.mark.asyncio
async def test_prometheus_exporter_gauge_and_histogram():
    exp = PrometheusMetricsExporter()
    await exp.gauge("test_gauge", 3.14, {})
    await exp.histogram("test_hist", 0.5, {})


@pytest.mark.skipif(not HAS_PROMETHEUS, reason="prometheus-client not installed")
@pytest.mark.asyncio
async def test_prometheus_exporter_label_schema_backfill():
    """Later calls with missing label keys are back-filled with empty strings."""
    exp = PrometheusMetricsExporter()
    # First call establishes schema: ["env", "region"]
    await exp.counter("backfill_counter", 1, {"env": "prod", "region": "us-east-1"})
    # Second call omits "region" — must not raise; "region" is back-filled with ""
    await exp.counter("backfill_counter", 1, {"env": "prod"})


@pytest.mark.skipif(not HAS_PROMETHEUS, reason="prometheus-client not installed")
@pytest.mark.asyncio
async def test_prometheus_exporter_no_labels():
    """Metrics without labels should work correctly."""
    exp = PrometheusMetricsExporter()
    await exp.counter("no_label_counter", 5, None)
    await exp.counter("no_label_counter", 3, {})


@pytest.mark.skipif(not HAS_PROMETHEUS, reason="prometheus-client not installed")
def test_prometheus_exporter_metrics_app_returns_asgi_callable():
    """metrics_app property returns an ASGI-callable application."""
    exp = PrometheusMetricsExporter()
    app = exp.metrics_app
    # ASGI apps are callables (their __call__ takes scope, receive, send)
    assert callable(app)


@pytest.mark.skipif(not HAS_PROMETHEUS, reason="prometheus-client not installed")
@pytest.mark.asyncio
async def test_prometheus_exporter_metrics_app_registered_in_container():
    """`prometheus_metrics_app` is registered in the DI container by MonitorProvider."""
    from unittest.mock import AsyncMock, MagicMock

    from quadkit.di.container import Container
    from quadkit.monitor.di.provider import MonitorProvider

    prom_exp = PrometheusMetricsExporter()
    backend = MagicMock()
    backend.initialize = AsyncMock()
    provider = MonitorProvider(backend=backend, exporter=prom_exp)

    container = Container()
    await provider.register(container)

    metrics_app = await container.resolve("prometheus_metrics_app")
    assert callable(metrics_app)
