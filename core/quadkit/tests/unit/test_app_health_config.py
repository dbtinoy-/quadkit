"""Tests for health-probe wiring of AppConfig/HealthConfig fields."""

from __future__ import annotations

from quadkit.app.base import Application
from quadkit.contracts.core.health import (
    AggregateHealthResult,
    HealthCheckResult,
    HealthStatus,
)


def _unhealthy_result() -> AggregateHealthResult:
    return AggregateHealthResult(
        components=[
            HealthCheckResult(
                component="db",
                status=HealthStatus.UNHEALTHY,
                message="boom",
                details={"error": 1},
            )
        ]
    )


class TestEffectiveHealthTimeout:
    """Per-provider timeout: explicit arg > AppConfig > HealthConfig."""

    def test_explicit_argument_wins(self) -> None:
        app = Application()
        assert app._effective_timeout(2.5) == 2.5

    def test_defaults_to_app_config(self) -> None:
        app = Application()
        app._config.health.check_timeout = 12.0

        assert app._effective_timeout(None) == 5.0

    def test_falls_back_to_health_config_when_app_value_is_none(self) -> None:
        app = Application()
        app._config.app.health_check_timeout = None
        app._config.health.check_timeout = 12.0

        assert app._effective_timeout(None) == 12.0

    def test_app_section_overrides_health_section(self) -> None:
        app = Application()
        app._config.app = {"health_check_timeout": 9.5}
        assert app._effective_timeout(None) == 9.5


class TestIncludeDetailsPolicy:
    """HealthConfig.include_details=False scrubs detailed error info."""

    def test_scrubs_when_disabled(self) -> None:
        app = Application()
        app._config.health.include_details = False

        scrubbed = app._apply_details_policy(_unhealthy_result())
        assert scrubbed.status == HealthStatus.UNHEALTHY  # status preserved
        assert scrubbed.components[0].message is None
        assert scrubbed.components[0].error is None
        assert scrubbed.components[0].details is None

    def test_keeps_details_when_enabled(self) -> None:
        app = Application()
        app._config.health.include_details = True

        kept = app._apply_details_policy(_unhealthy_result())
        assert kept.components[0].message == "boom"
        assert kept.components[0].details == {"error": 1}
