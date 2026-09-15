"""Configuration models for the app subsystem.

Contains :class:`AppConfig`, which controls application identity,
environment, and lifecycle timeouts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quadkit.app.constants import (
    DEFAULT_APP_NAME,
    DEFAULT_HEALTH_CHECK_TIMEOUT,
    DEFAULT_SHUTDOWN_TIMEOUT,
)


@dataclass
class AppConfig:
    """Application lifecycle and runner utilities configuration."""

    app_name: str = DEFAULT_APP_NAME
    # ``name`` is the canonical YAML key under ``app:``; ``app_name`` remains
    # supported for compatibility with the original flat configuration.
    name: str | None = None
    # consumed by: OTEL resource attribute, logger context, AppProvider
    debug: bool | str = False
    # consumed by: Application — verbose startup/teardown logging
    env: str = "production"
    # consumed by: Application — environment name surfaced in health checks
    shutdown_timeout: float = DEFAULT_SHUTDOWN_TIMEOUT
    # consumed by: Application.stop() maximum wait time
    health_check_timeout: float = DEFAULT_HEALTH_CHECK_TIMEOUT
    # consumed by: CoreProvider.health_check() per-provider timeout

    def __post_init__(self) -> None:
        """Normalize aliases and scalar values loaded from environment variables."""
        if self.name is not None:
            self.app_name = self.name
        else:
            self.name = self.app_name

        if isinstance(self.debug, str):
            value = self.debug.strip().lower()
            if value in {"1", "true", "yes", "on"}:
                self.debug = True
            elif value in {"0", "false", "no", "off", ""}:
                self.debug = False
            else:
                raise ValueError(f"Invalid boolean value for app.debug: {self.debug!r}")
        if self.shutdown_timeout is not None:
            self.shutdown_timeout = float(self.shutdown_timeout)
        if self.health_check_timeout is not None:
            self.health_check_timeout = float(self.health_check_timeout)


@dataclass
class StartupProbeConfig:
    """Startup probe configuration."""

    timeout: float = 60.0
    # consumed by: Application.startup_check() — max wait time for initialization


@dataclass
class HealthConfig:
    """Health probe configuration.

    Controls Kubernetes-style liveness, readiness, and startup probes.
    """

    check_timeout: float = DEFAULT_HEALTH_CHECK_TIMEOUT
    # Per-provider timeout for individual health checks (seconds).
    include_details: bool = True
    # Include detailed error messages in health responses.
    startup: StartupProbeConfig = field(default_factory=StartupProbeConfig)
    # Startup probe configuration.


__all__ = ["AppConfig", "HealthConfig", "StartupProbeConfig"]
