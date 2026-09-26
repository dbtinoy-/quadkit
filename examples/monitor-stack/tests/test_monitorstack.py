"""Tests — real composition root, no mocks.

Every test boots a real Application with the actual DI container.
Services are tested through their public API, not by mocking internals.
"""

from __future__ import annotations

import pytest
import httpx


class TestHealthChecks:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_health(self, client: httpx.AsyncClient) -> None:
        """GET /api/monitor/health returns status."""
        resp = await client.get("/api/monitor/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_health_self(self, client: httpx.AsyncClient) -> None:
        """GET /api/monitor/health/self returns self check."""
        resp = await client.get("/api/monitor/health/self")
        assert resp.status_code == 200
        data = resp.json()
        assert data["component"] == "self"
        assert data["status"] == "healthy"


class TestMetrics:
    """Test metrics endpoints."""

    @pytest.mark.asyncio
    async def test_get_metrics(self, client: httpx.AsyncClient) -> None:
        """GET /api/monitor/metrics returns metrics."""
        resp = await client.get("/api/monitor/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "counters" in data
        assert "gauges" in data
        assert "histograms" in data

    @pytest.mark.asyncio
    async def test_increment_metric(self, client: httpx.AsyncClient) -> None:
        """POST /api/monitor/metrics/increment increments a counter."""
        resp = await client.post(
            "/api/monitor/metrics/increment",
            json={"name": "test_counter", "value": 1.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_set_gauge(self, client: httpx.AsyncClient) -> None:
        """POST /api/monitor/metrics/gauge sets a gauge."""
        resp = await client.post(
            "/api/monitor/metrics/gauge",
            json={"name": "test_gauge", "value": 42.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_increment_metric_missing_name(self, client: httpx.AsyncClient) -> None:
        """POST /api/monitor/metrics/increment with empty name returns error."""
        resp = await client.post(
            "/api/monitor/metrics/increment",
            json={"name": ""},
        )
        assert resp.status_code == 422
        assert "detail" in resp.json()


class TestTracing:
    """Test tracing endpoints."""

    @pytest.mark.asyncio
    async def test_get_traces(self, client: httpx.AsyncClient) -> None:
        """GET /api/monitor/traces returns traces."""
        resp = await client.get("/api/monitor/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "spans" in data

    @pytest.mark.asyncio
    async def test_create_trace(self, client: httpx.AsyncClient) -> None:
        """POST /api/monitor/trace creates a trace span."""
        resp = await client.post(
            "/api/monitor/trace",
            json={"name": "test_trace", "attributes": {"key": "value"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "span" in data
        assert data["span"]["name"] == "test_trace"
        assert "duration_ms" in data["span"]
