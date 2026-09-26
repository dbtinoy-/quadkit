"""Tests for LoggingAlertDispatcher (alerts)."""

from __future__ import annotations

import pytest

from quadkit.monitor.alerts import LoggingAlertDispatcher
from quadkit.monitor.alerts.alerting import _HIGH_SEVERITY_LEVELS


class _RecordingLogger:
    """Stand-in for the module structlog logger: records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def _log(self, level: str, msg: str, **extra) -> None:
        self.calls.append((level, msg, extra))

    def debug(self, msg, **kw) -> None:
        self._log("debug", msg, **kw)

    def info(self, msg, **kw) -> None:
        self._log("info", msg, **kw)

    def warning(self, msg, **kw) -> None:
        self._log("warning", msg, **kw)

    def error(self, msg, **kw) -> None:
        self._log("error", msg, **kw)

    def critical(self, msg, **kw) -> None:
        self._log("critical", msg, **kw)


@pytest.fixture
def rec(monkeypatch) -> _RecordingLogger:
    """Patch the alerting module logger with a recorder."""
    import quadkit.monitor.alerts.alerting as mod

    logger = _RecordingLogger()
    monkeypatch.setattr(mod, "logger", logger)
    return logger


class TestSendAlert:
    def test_high_severity_levels_constant(self) -> None:
        assert frozenset({"high", "critical"}) == _HIGH_SEVERITY_LEVELS

    @pytest.mark.asyncio
    async def test_low_severity_logs_warning(self, rec) -> None:
        await LoggingAlertDispatcher().send_alert("t", "m", "low", context={"k": "v"})
        assert rec.calls == [
            (
                "warning",
                "alert_dispatched",
                {
                    "alert_title": "t",
                    "alert_severity": "low",
                    "alert_message": "m",
                    "alert_context": {"k": "v"},
                },
            )
        ]

    @pytest.mark.asyncio
    async def test_high_severity_logs_error(self, rec) -> None:
        await LoggingAlertDispatcher().send_alert("t2", "m2", "high")
        assert rec.calls == [
            (
                "error",
                "alert_dispatched",
                {
                    "alert_title": "t2",
                    "alert_severity": "high",
                    "alert_message": "m2",
                },
            )
        ]

    @pytest.mark.asyncio
    async def test_critical_severity_logs_error_case_insensitive(self, rec) -> None:
        await LoggingAlertDispatcher().send_alert("t3", "m3", "CRITICAL")
        assert rec.calls[0][0] == "error"
        assert rec.calls[0][2]["alert_severity"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_medium_severity_logs_warning(self, rec) -> None:
        await LoggingAlertDispatcher().send_alert("t4", "m4", "medium")
        assert rec.calls[0][0] == "warning"

    @pytest.mark.asyncio
    async def test_unknown_severity_logs_warning(self, rec) -> None:
        await LoggingAlertDispatcher().send_alert("t5", "m5", "weird")
        assert rec.calls[0][0] == "warning"

    @pytest.mark.asyncio
    async def test_no_context_omits_key(self, rec) -> None:
        await LoggingAlertDispatcher().send_alert("t6", "m6", "low")
        assert "alert_context" not in rec.calls[0][2]


class TestSendMetricAlert:
    @pytest.mark.asyncio
    async def test_mild_breach_warns(self, rec) -> None:
        await LoggingAlertDispatcher().send_metric_alert("cpu", 110.0, 100.0)
        assert rec.calls == [
            (
                "warning",
                "metric_alert_dispatched",
                {
                    "metric_name": "cpu",
                    "current_value": 110.0,
                    "threshold": 100.0,
                },
            )
        ]

    @pytest.mark.asyncio
    async def test_severe_breach_errors(self, rec) -> None:
        await LoggingAlertDispatcher().send_metric_alert("mem", 300.0, 100.0)
        assert rec.calls[0][0] == "error"
        assert rec.calls[0][1] == "metric_alert_dispatched"
        assert rec.calls[0][2]["current_value"] == 300.0

    @pytest.mark.asyncio
    async def test_exactly_double_threshold_errors(self, rec) -> None:
        await LoggingAlertDispatcher().send_metric_alert("d", 200.0, 100.0)
        assert rec.calls[0][0] == "error"

    @pytest.mark.asyncio
    async def test_zero_threshold_never_errors(self, rec) -> None:
        await LoggingAlertDispatcher().send_metric_alert("z", 1000.0, 0.0)
        assert rec.calls[0][0] == "warning"

    @pytest.mark.asyncio
    async def test_context_forwarded(self, rec) -> None:
        await LoggingAlertDispatcher().send_metric_alert(
            "c", 5.0, 1.0, context={"host": "h1"}
        )
        assert rec.calls[0][2]["alert_context"] == {"host": "h1"}

    @pytest.mark.asyncio
    async def test_none_context_omits_key(self, rec) -> None:
        await LoggingAlertDispatcher().send_metric_alert("n", 1.0, 2.0, context=None)
        assert "alert_context" not in rec.calls[0][2]
