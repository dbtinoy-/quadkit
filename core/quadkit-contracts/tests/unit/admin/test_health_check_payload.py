"""Tests for the HealthCheckPayload value type."""

from __future__ import annotations

import pytest

from quadkit.contracts.admin.health_payload import HealthCheckPayload
from quadkit.contracts.core.health import HealthStatus


def test_health_check_payload_defaults() -> None:
    payload = HealthCheckPayload(status=HealthStatus.HEALTHY, component="LLM Provider")
    assert payload.status == HealthStatus.HEALTHY
    assert payload.component == "LLM Provider"
    assert payload.detail == ""
    assert payload.latency_ms is None


def test_health_check_payload_is_frozen() -> None:
    payload = HealthCheckPayload(status=HealthStatus.DEGRADED, component="x")
    with pytest.raises(Exception):  # noqa: B017, PT011 — dataclass FrozenInstanceError
        payload.detail = "changed"
