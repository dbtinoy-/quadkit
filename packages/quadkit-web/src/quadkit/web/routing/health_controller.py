"""Kubernetes-style health and metrics controller built on Tier-0 contracts."""

from __future__ import annotations

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.observability.metrics import (
    HealthCheckRegistryProtocol,
    MetricsExpositionProtocol,
)
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.decorators import get
from quadkit.web.transport.responses import JSONResponse, Response


def _to_http_status(status: HealthStatus | int | str) -> int:
    if isinstance(status, int):
        return status
    raw = status.value if isinstance(status, HealthStatus) else str(status).lower()
    if raw in {HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value}:
        return 200
    return 503


def _serialize_status(status: HealthStatus | int | str) -> str | int:
    if isinstance(status, HealthStatus):
        return status.value
    return status


class HealthController(Controller):
    """HTTP probe controller exposing ``/health``, ``/ready``, ``/live``, ``/startup``, and ``/metrics``."""

    prefix = "/health"

    def __init__(
        self,
        registry: HealthCheckRegistryProtocol,
        metrics_exporter: MetricsExpositionProtocol | None = None,
    ) -> None:
        super().__init__()
        self.registry = registry
        self.metrics_exporter = metrics_exporter

    @get("")
    async def health_check(self) -> JSONResponse:
        """Basic liveness summary probe."""
        status, details = await self.registry.run_liveness()
        return JSONResponse(
            {"status": _serialize_status(status), "details": details},
            status_code=_to_http_status(status),
        )

    @get("/ready")
    async def readiness(self) -> JSONResponse:
        """Readiness probe."""
        status, details = await self.registry.run_readiness()
        return JSONResponse(
            {"status": _serialize_status(status), "components": details},
            status_code=_to_http_status(status),
        )

    @get("/live")
    async def liveness(self) -> JSONResponse:
        """Liveness probe."""
        status, details = await self.registry.run_liveness()
        return JSONResponse(
            {"status": _serialize_status(status), "components": details},
            status_code=_to_http_status(status),
        )

    @get("/startup")
    async def startup(self) -> JSONResponse:
        """Startup probe."""
        status, details = await self.registry.run_startup()
        return JSONResponse(
            {"status": _serialize_status(status), "components": details},
            status_code=_to_http_status(status),
        )

    @get("/metrics")
    async def metrics(self) -> Response:
        """Export Prometheus-formatted metrics when a collector/exporter is wired."""
        if self.metrics_exporter is None:
            return Response(
                content="# Metrics unavailable (no metrics exporter configured)\n",
                media_type="text/plain; charset=utf-8",
            )
        try:
            payload = self.metrics_exporter.export()
            return Response(
                content=payload,
                media_type=self.metrics_exporter.content_type,
            )
        except Exception as exc:  # noqa: BLE001 — surface scrape failure as 500 JSON
            return JSONResponse(
                {"error": "Failed to export metrics", "detail": str(exc)},
                status_code=500,
            )


__all__ = ["HealthController"]
