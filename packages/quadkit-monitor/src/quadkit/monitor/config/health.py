"""Health check configuration."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.config import BaseConfig
from quadkit.monitor import constants as monitor_const
from quadkit.validation import Field


@dataclass(init=False)
class HealthCheckConfig(BaseConfig):
    """Configuration for health checks.

    Attributes:
        enabled: Whether health checks are enabled.
        path: HTTP path for health endpoint.
        include_details: Include detailed component health in response.
        timeout: Timeout for health check operations (seconds).
        checks: List of health check names to include.
    """

    enabled: bool = Field(True, description="Enable health checks")
    path: str = Field("/health", description="Health endpoint path")
    include_details: bool = Field(
        True,
        description="Include detailed health info in response",
    )
    timeout: float = Field(5.0, ge=0.1, description="Health check timeout in seconds")
    checks: list[str] = Field(
        default_factory=list,
        description="List of health check names to run",
    )
    interval: int = Field(
        monitor_const.DEFAULT_HEALTH_CHECK_INTERVAL,
        ge=1,
        description="Health check interval in seconds",
    )


__all__ = [
    "HealthCheckConfig",
]
