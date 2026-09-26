"""Unified Health Check System."""

from __future__ import annotations

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.health import HealthCheckCategory
from quadkit.monitor.health.base import HealthCheck
from quadkit.monitor.health.cached import CachedHealthChecker
from quadkit.monitor.health.checker import HealthChecker, health_checker
from quadkit.monitor.health.checker_registry import HealthCheckerRegistry
from quadkit.monitor.health.functions import FunctionHealthCheck
from quadkit.monitor.health.registry import HealthCheckRegistry

__all__ = [
    "CachedHealthChecker",
    "FunctionHealthCheck",
    "HealthCheck",
    "HealthCheckCategory",
    "HealthCheckRegistry",
    "HealthCheckResult",
    "HealthChecker",
    "HealthCheckerRegistry",
    "HealthStatus",
    "health_checker",
]
