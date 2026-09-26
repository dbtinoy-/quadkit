"""Constants for quadkit-monitor."""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__: str = importlib.metadata.version("quadkit-monitor")
except ImportError:
    __version__ = "0.0.0"

# -- Environment Variable Prefixes -------------------------------------------

ENV_PREFIX: str = "QK_MONITOR__"
ENV_NESTED_DELIMITER: str = "__"

# -- Default Configuration Values --------------------------------------------

DEFAULT_SERVICE_NAME: str = "quadkit-service"
DEFAULT_PROMETHEUS_PORT: int = 8000
DEFAULT_OTEL_ENDPOINT: str | None = None
DEFAULT_MAX_SPANS: int = 1000
DEFAULT_HEALTH_CHECK_INTERVAL: int = 30

# -- MetricProtocol Name Prefixes ----------------------------------------------------

METRIC_PREFIX: str = "quadkit_"
REQUEST_TOTAL_METRIC: str = "quadkit_requests_total"
ACTIVE_CONNECTIONS_METRIC: str = "quadkit_active_connections"
REQUEST_DURATION_METRIC: str = "quadkit_request_duration_seconds"

# -- Default Histogram Buckets -----------------------------------------------

DEFAULT_DURATION_BUCKETS: tuple[float, ...] = (0.1, 0.5, 1.0, 2.0, 5.0, 10.0)

__all__ = [
    "ACTIVE_CONNECTIONS_METRIC",
    "DEFAULT_DURATION_BUCKETS",
    "DEFAULT_HEALTH_CHECK_INTERVAL",
    "DEFAULT_MAX_SPANS",
    "DEFAULT_OTEL_ENDPOINT",
    "DEFAULT_PROMETHEUS_PORT",
    "DEFAULT_SERVICE_NAME",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "METRIC_PREFIX",
    "REQUEST_DURATION_METRIC",
    "REQUEST_TOTAL_METRIC",
]
