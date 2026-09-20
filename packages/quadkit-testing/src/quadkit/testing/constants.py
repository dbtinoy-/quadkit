"""Constants for quadkit-testing."""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__ = importlib.metadata.version("quadkit-testing")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

# -- Environment Variable Prefixes -------------------------------------------

ENV_PREFIX: str = "QK_TESTING__"
ENV_NESTED_DELIMITER: str = "__"

# -- Default Timeouts --------------------------------------------------------

DEFAULT_PROBE_TIMEOUT: float = 30.0
DEFAULT_PROBE_INTERVAL: float = 0.5
DEFAULT_HTTP_TIMEOUT: float = 10.0

# -- Service Default Ports ----------------------------------------------------

DEFAULT_REDIS_PORT: int = 6379
DEFAULT_POSTGRES_PORT: int = 5432
DEFAULT_RABBITMQ_PORT: int = 5672
DEFAULT_SMTP_PORT: int = 25
DEFAULT_ELASTICSEARCH_PORT: int = 9200
DEFAULT_MEILISEARCH_PORT: int = 7700

# -- Integration Marker Names ------------------------------------------------

MARKER_REDIS: str = "redis"
MARKER_POSTGRES: str = "postgres"
MARKER_RABBITMQ: str = "rabbitmq"
MARKER_SMTP: str = "smtp"
MARKER_ELASTICSEARCH: str = "elasticsearch"
MARKER_MEILISEARCH: str = "meilisearch"

__all__ = [
    "DEFAULT_ELASTICSEARCH_PORT",
    "DEFAULT_HTTP_TIMEOUT",
    "DEFAULT_MEILISEARCH_PORT",
    "DEFAULT_POSTGRES_PORT",
    "DEFAULT_PROBE_INTERVAL",
    "DEFAULT_PROBE_TIMEOUT",
    "DEFAULT_RABBITMQ_PORT",
    "DEFAULT_REDIS_PORT",
    "DEFAULT_SMTP_PORT",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "MARKER_ELASTICSEARCH",
    "MARKER_MEILISEARCH",
    "MARKER_POSTGRES",
    "MARKER_RABBITMQ",
    "MARKER_REDIS",
    "MARKER_SMTP",
]
