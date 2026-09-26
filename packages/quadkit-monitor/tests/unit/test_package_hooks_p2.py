"""P2 hook surface import verification for quadkit-monitor."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_monitor_hooks_root_module_exists() -> None:
    import quadkit.monitor
    from quadkit.monitor.hooks import (
        AlertFiredHook,
        HealthCheckRunHook,
        MetricRecordedHook,
    )

    assert MetricRecordedHook.__name__ == "MetricRecordedHook"
    assert AlertFiredHook.__name__ == "AlertFiredHook"
    assert HealthCheckRunHook.__name__ == "HealthCheckRunHook"
    assert quadkit.monitor.MetricRecordedHook is MetricRecordedHook
    assert quadkit.monitor.AlertFiredHook is AlertFiredHook
    assert quadkit.monitor.HealthCheckRunHook is HealthCheckRunHook


def test_monitor_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.monitor.hooks import AlertFiredHook, MetricRecordedHook

    metric = MetricRecordedHook(metric_name="request_count", value=42.0)
    alert = AlertFiredHook(alert_name="high_error_rate", severity="critical")

    assert is_dataclass(metric)
    assert is_dataclass(alert)

    with pytest.raises(TypeError):
        MetricRecordedHook("request_count", 42.0)  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        metric.value = 0.0  # type: ignore[misc]
