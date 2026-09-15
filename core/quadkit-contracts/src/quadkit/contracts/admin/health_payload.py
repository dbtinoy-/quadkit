"""Structured health-check result for the admin dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.core.health import HealthStatus


@dataclass(frozen=True)
class HealthCheckPayload:
    """Structured result of an admin-contributed health check.

    Replaces the prose ``str`` previously returned by
    ``BaseAdminContributor.render_health_check`` — the host (``WidgetController``)
    owns turning this into HTML, so every contributor's health check renders
    with the same badge/status presentation.
    """

    status: HealthStatus
    component: str
    detail: str = ""
    latency_ms: float | None = None


__all__ = ["HealthCheckPayload"]
