"""Cache service configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quadkit.cache import constants as const
from quadkit.domain import DomainModel
from quadkit.validation import Field


@dataclass(init=False)
class CacheServiceConfig(DomainModel):
    """Configuration for the cache service layer.

    Controls service-level behavior and features like stampede
    protection, metrics, and circuit breaker.

    Attributes:
        enable_protection: Enable cache stampede protection.
        enable_metrics: Enable service-level metrics.
        enable_health_checks: Enable health checks.
        protection_lock_ttl: Lock TTL for stampede protection.
        protection_max_wait: Max wait time for locks.
        protection_retry_interval: Retry interval for locks.
        default_backend: Name of the default backend.
        circuit_breaker_enabled: Enable circuit breaker pattern.
        circuit_breaker_threshold: Failure threshold for circuit breaker.
        default_serializer: Default serializer type.
    """

    enable_protection: bool = Field(
        const.DEFAULT_SERVICE_PROTECTION_ENABLED,
        description="Enable stampede protection",
    )
    enable_metrics: bool = Field(
        const.DEFAULT_SERVICE_METRICS_ENABLED,
        description="Enable metrics",
    )
    enable_health_checks: bool = Field(
        const.DEFAULT_SERVICE_HEALTH_CHECKS_ENABLED,
        description="Enable health checks",
    )
    protection_lock_ttl: int = Field(
        const.DEFAULT_PROTECTION_LOCK_TTL,
        description="Protection lock TTL",
    )
    protection_max_wait: float = Field(
        const.DEFAULT_PROTECTION_MAX_WAIT,
        description="Max wait for locks",
    )
    protection_retry_interval: float = Field(
        const.DEFAULT_PROTECTION_RETRY_INTERVAL,
        description="Lock retry interval",
    )
    default_backend: str | None = Field(None, description="Default backend name")
    circuit_breaker_enabled: bool = Field(
        const.DEFAULT_SERVICE_CIRCUIT_BREAKER_ENABLED,
        description="Enable circuit breaker",
    )
    circuit_breaker_threshold: int = Field(
        const.DEFAULT_SERVICE_CIRCUIT_BREAKER_THRESHOLD,
        description="Circuit breaker threshold",
    )
    default_serializer: str = Field(
        const.DEFAULT_SERVICE_SERIALIZER,
        description="Default serializer",
    )


def make_cache_service_config(**kwargs: Any) -> CacheServiceConfig:
    """Helper to create service config from kwargs.

    Args:
        **kwargs: Service configuration keyword arguments.

    Returns:
        Created :class:`CacheServiceConfig` instance.
    """
    return CacheServiceConfig(**kwargs)


__all__ = [
    "CacheServiceConfig",
    "make_cache_service_config",
]
