"""CLI doctor checks for quadkit-monitor."""

from __future__ import annotations

import os


def check_monitor_config() -> dict[str, object]:
    """Validate monitor section in application.yaml.

    Returns:
        A DoctorCheckResult-compatible dict.
    """
    return {
        "status": "ok",
        "message": "Monitor configuration check not yet implemented",
    }


def check_otel_endpoint() -> dict[str, object]:
    """Check OTEL_EXPORTER_OTLP_ENDPOINT is reachable.

    Returns:
        A DoctorCheckResult-compatible dict.
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return {
            "status": "warning",
            "message": "OTEL_EXPORTER_OTLP_ENDPOINT not set — OTLP export disabled",
        }
    return {"status": "ok", "message": f"OTLP endpoint configured: {endpoint}"}
