"""Configuration models for the middleware subsystem.

Contains :class:`MiddlewareConfig`, which controls retry behaviour,
correlation headers, and other middleware defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.middleware.constants import (
    DEFAULT_CORRELATION_HEADER,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY,
)
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class MiddlewareConfig(BaseConfig):
    """Middleware chain, pipeline, and registry configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="ignore",
    )

    default_retry_count: int = Field(
        default=DEFAULT_RETRY_COUNT,
        ge=0,
        description="Default number of retries for RetryMiddleware.",
    )
    default_retry_delay: float = Field(
        default=DEFAULT_RETRY_DELAY,
        ge=0.0,
        description="Default delay in seconds between retries.",
    )
    correlation_header: str = Field(
        default=DEFAULT_CORRELATION_HEADER,
        description=(
            "Conventional HTTP header name carrying the correlation ID "
            "(X-Correlation-Id). Edge/transport layers map it to/from the "
            "'correlation_id' context attribute set by "
            "CorrelationIdMiddleware; core middleware reads no HTTP headers."
        ),
    )
    default_timeout: float = Field(
        default=30.0,
        ge=0.1,
        description="Default timeout in seconds for TimeoutMiddleware",
    )
    circuit_failure_threshold: int = Field(
        default=5,
        ge=1,
        description="Consecutive failures before CircuitBreakerMiddleware opens",
    )
    circuit_recovery_timeout: float = Field(
        default=30.0,
        ge=1.0,
        description="Seconds before open circuit transitions to half-open",
    )
    rate_limit_max_requests: int = Field(
        default=100,
        ge=1,
        description="Max requests per window for RateLimiterMiddleware",
    )
    rate_limit_window: float = Field(
        default=60.0,
        ge=1.0,
        description="Rate limit window in seconds",
    )


__all__ = ["MiddlewareConfig"]
