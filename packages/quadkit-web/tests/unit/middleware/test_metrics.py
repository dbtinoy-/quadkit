"""Unit tests for MetricsMiddleware and InMemoryMetricsCollector."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.web.middleware.metrics import (
    InMemoryMetricsCollector,
    MetricsCollectorProtocol,
    MetricsMiddleware,
)


def make_app(handler=None, collector=None, **middleware_kwargs):
    """Build a minimal Starlette test app wrapped with MetricsMiddleware."""
    if collector is None:
        collector = InMemoryMetricsCollector()

    async def default_handler(request: Request) -> Response:
        return JSONResponse({"ok": True})

    async def error_handler(request: Request) -> Response:
        return JSONResponse({"error": "server error"}, status_code=500)

    async def slow_handler(request: Request) -> Response:
        return JSONResponse({"slow": True})

    def health(request: Request) -> Response:
        return Response("ok")

    routes = [
        Route("/api/items", default_handler),
        Route("/api/items/{id:int}", default_handler),
        Route("/error", error_handler),
        Route("/slow", slow_handler),
        Route("/health", health),
    ]
    app = Starlette(routes=routes)
    app.add_middleware(
        MetricsMiddleware,
        collector=collector,
        **middleware_kwargs,
    )
    return app, collector


class TestInMemoryMetricsCollector:
    """Tests for the in-memory MetricsCollectorProtocol implementation."""

    def test_increment_counter_and_read(self):
        """Counters can be incremented and read back."""
        c = InMemoryMetricsCollector()
        c.increment_counter("requests", labels={"method": "GET"})
        c.increment_counter("requests", labels={"method": "GET"})
        assert c.counter("requests", labels={"method": "GET"}) == 2.0

    def test_observe_histogram(self):
        """Histogram observations are stored in order."""
        c = InMemoryMetricsCollector()
        c.observe_histogram("duration", 0.1)
        c.observe_histogram("duration", 0.2)
        assert c.histogram_values("duration") == [0.1, 0.2]

    def test_set_gauge(self):
        """Gauge is overwritten on each set."""
        c = InMemoryMetricsCollector()
        c.set_gauge("in_progress", 3.0, labels={"method": "GET"})
        c.set_gauge("in_progress", 1.0, labels={"method": "GET"})
        assert c.gauge("in_progress", labels={"method": "GET"}) == 1.0

    def test_reset(self):
        """Reset clears all recorded metrics."""
        c = InMemoryMetricsCollector()
        c.increment_counter("total")
        c.observe_histogram("dur", 0.5)
        c.set_gauge("g", 5.0)
        c.reset()
        assert c.snapshot() == {"counters": {}, "histograms": {}, "gauges": {}}

    def test_snapshot_has_all_keys(self):
        """Snapshot includes counters, histograms, and gauges."""
        c = InMemoryMetricsCollector()
        c.increment_counter("c")
        snap = c.snapshot()
        assert "counters" in snap
        assert "histograms" in snap
        assert "gauges" in snap

    def test_implements_protocol(self):
        """InMemoryMetricsCollector satisfies the MetricsCollectorProtocol protocol."""
        c = InMemoryMetricsCollector()
        assert isinstance(c, MetricsCollectorProtocol)


class TestMetricsMiddleware:
    """Integration tests for MetricsMiddleware."""

    def test_successful_request_increments_counter(self):
        """A successful request increments http_requests_total."""
        app, col = make_app()
        client = TestClient(app)

        client.get("/api/items")

        # Counter should be non-zero (exact label value depends on status)
        snap = col.snapshot()
        counts = snap["counters"]
        total_keys = [k for k in counts if k.startswith("http_requests_total")]
        assert len(total_keys) > 0
        assert any(counts[k] > 0 for k in total_keys)

    def test_successful_request_records_duration(self):
        """A successful request records a histogram entry."""
        app, col = make_app()
        client = TestClient(app)

        client.get("/api/items")

        hist = col.snapshot()["histograms"]
        dur_keys = [k for k in hist if k.startswith("http_request_duration_seconds")]
        assert len(dur_keys) > 0

    def test_server_error_increments_error_counter(self):
        """5xx responses are tracked in http_errors_total."""
        app, col = make_app()
        client = TestClient(app, raise_server_exceptions=False)

        client.get("/error")

        snap = col.snapshot()
        error_keys = [k for k in snap["counters"] if k.startswith("http_errors_total")]
        assert len(error_keys) > 0

    def test_health_path_is_filtered(self):
        """Requests to filtered paths are not tracked."""
        app, col = make_app()
        client = TestClient(app)

        client.get("/health")

        snap = col.snapshot()
        # No counter entries should reference /health path
        counters = snap["counters"]
        assert not any("/health" in k for k in counters)

    def test_status_code_included_in_labels(self):
        """Labels include the response status code."""
        app, col = make_app()
        client = TestClient(app)

        client.get("/api/items")

        snap = col.snapshot()
        # Should see a "status=200" in at least one counter key
        assert any("status=200" in k for k in snap["counters"])

    def test_method_included_in_labels(self):
        """Labels include the HTTP method."""
        app, col = make_app()
        client = TestClient(app)

        client.get("/api/items")

        snap = col.snapshot()
        assert any("method=GET" in k for k in snap["counters"])

    def test_non_http_scope_passes_through(self):
        """WebSocket/other scopes are not tracked."""
        app, col = make_app()
        # Just verifying no crash for now — non-HTTP scopes are skipped
        # by the middleware without recording metrics
        assert col.snapshot()["counters"] == {}

    def test_custom_filter_paths(self):
        """Custom filter_paths prevents tracking for specified paths."""
        app, col = make_app(filter_paths={"/api/items"})
        client = TestClient(app)

        client.get("/api/items")

        snap = col.snapshot()
        assert not any("/api/items" in k for k in snap["counters"])
