"""Tests for the /health route — verifies 200/207/503 status codes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from quadkit.contracts.core import (
    AggregateHealthResult,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.contracts.core.health import HealthCheckCategory
from quadkit.web.routing.health_checks import ComponentHealth, HealthCheckResponse


def _make_health_response(status: HealthStatus) -> HealthCheckResponse:
    """Build a minimal HealthCheckResponse for mocking."""
    component = ComponentHealth(
        status=status,
        latency_ms=1.0,
        checked_at=datetime.now(UTC),
    )
    return HealthCheckResponse(
        status=status,
        version="test",
        components={"database": component, "redis": component},
        checked_at=datetime.now(UTC),
    )


def _make_probe_result(
    *,
    component: str,
    status: HealthStatus,
    category: HealthCheckCategory,
) -> AggregateHealthResult:
    """Build a minimal AggregateHealthResult for probe route tests."""
    return AggregateHealthResult(
        components=[
            HealthCheckResult(
                component=component,
                status=status,
                category=category,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_health_returns_200_when_healthy(test_bed) -> None:
    """200 is returned when all components are HEALTHY."""
    from quadkit.web.di.provider import WebProvider

    web = await test_bed.resolve(WebProvider)
    client = TestClient(web.starlette, raise_server_exceptions=False)

    mock_response = _make_health_response(HealthStatus.HEALTHY)
    with patch(
        "quadkit.web.routing.health.WebHealthChecker.check_health",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        resp = client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == HealthStatus.HEALTHY.value


@pytest.mark.asyncio
async def test_health_returns_207_when_degraded(test_bed) -> None:
    """207 is returned when at least one component is DEGRADED."""
    from quadkit.web.di.provider import WebProvider

    web = await test_bed.resolve(WebProvider)
    client = TestClient(web.starlette, raise_server_exceptions=False)

    mock_response = _make_health_response(HealthStatus.DEGRADED)
    with patch(
        "quadkit.web.routing.health.WebHealthChecker.check_health",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        resp = client.get("/health")

    assert resp.status_code == 207
    data = resp.json()
    assert data["status"] == HealthStatus.DEGRADED.value


@pytest.mark.asyncio
async def test_health_returns_503_when_unhealthy(test_bed) -> None:
    """503 is returned when any component is UNHEALTHY."""
    from quadkit.web.di.provider import WebProvider

    web = await test_bed.resolve(WebProvider)
    client = TestClient(web.starlette, raise_server_exceptions=False)

    mock_response = _make_health_response(HealthStatus.UNHEALTHY)
    with patch(
        "quadkit.web.routing.health.WebHealthChecker.check_health",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        resp = client.get("/health")

    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == HealthStatus.UNHEALTHY.value


@pytest.mark.asyncio
async def test_health_response_contains_components(test_bed) -> None:
    """The JSON response includes component-level health details."""
    from quadkit.web.di.provider import WebProvider

    web = await test_bed.resolve(WebProvider)
    client = TestClient(web.starlette, raise_server_exceptions=False)

    mock_response = _make_health_response(HealthStatus.HEALTHY)
    with patch(
        "quadkit.web.routing.health.WebHealthChecker.check_health",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        resp = client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert "components" in data
    assert "database" in data["components"]
    assert "redis" in data["components"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "method_name", "component", "status", "category", "expected_code"),
    [
        (
            "/health/live",
            "liveness",
            "live",
            HealthStatus.HEALTHY,
            HealthCheckCategory.LIVENESS,
            200,
        ),
        (
            "/health/ready",
            "readiness",
            "ready",
            HealthStatus.DEGRADED,
            HealthCheckCategory.READINESS,
            207,
        ),
        (
            "/health/startup",
            "startup_check",
            "startup",
            HealthStatus.UNHEALTHY,
            HealthCheckCategory.STARTUP,
            503,
        ),
    ],
)
async def test_probe_routes_use_application_health(
    test_bed,
    path: str,
    method_name: str,
    component: str,
    status: HealthStatus,
    category: HealthCheckCategory,
    expected_code: int,
) -> None:
    """Probe routes should proxy to the application health methods."""
    from quadkit.web.di.provider import WebProvider

    web = await test_bed.resolve(WebProvider)
    client = TestClient(web.starlette, raise_server_exceptions=False)

    mock_result = _make_probe_result(
        component=component,
        status=status,
        category=category,
    )

    with patch(
        f"quadkit.app.base.Application.{method_name}",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = client.get(path)

    assert resp.status_code == expected_code
    data = resp.json()
    assert data["status"] == status.value
    assert data["components"][0]["component"] == component
    assert data["components"][0]["category"] == category.value
