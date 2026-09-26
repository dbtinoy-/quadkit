from __future__ import annotations

from quadkit.contracts.exceptions import ConfigurationError as _ConfigurationError
from quadkit.contracts.exceptions import QuadkitError


class MonitorError(QuadkitError):
    """Base exception for monitoring errors."""

    _code: str = "QK_ERR_MONITOR_001"


class BackendNotAvailableError(MonitorError):
    """Raised when a required monitoring backend is not available."""

    _code: str = "QK_ERR_MONITOR_002"


class MetricNotFoundError(MonitorError):
    """Raised when a requested metric is not found."""

    _code: str = "QK_ERR_MONITOR_003"


class InvalidMetricError(MonitorError):
    """Raised when metric parameters are invalid."""

    _code: str = "QK_ERR_MONITOR_004"


class SpanError(MonitorError):
    """Base exception for span-related errors."""

    _code: str = "QK_ERR_MONITOR_005"


class SpanNotFoundError(SpanError):
    """Raised when a requested span is not found."""

    _code: str = "QK_ERR_MONITOR_006"


class MonitorConfigurationError(MonitorError, _ConfigurationError):
    """Raised when monitoring configuration is invalid."""

    _code: str = "QK_ERR_MONITOR_007"


__all__ = [
    "BackendNotAvailableError",
    "InvalidMetricError",
    "MetricNotFoundError",
    "MonitorConfigurationError",
    "MonitorError",
    "SpanError",
    "SpanNotFoundError",
]
