"""Pytest plugin for Quadkit testing (auto-loaded via the pytest11 entry point).

Registers Quadkit markers and wires automatic test-skipping: a test marked
``requires_<service>`` is skipped at collection time when the service does
not accept a TCP connection on its default port (localhost), so suites stay
green in environments without the external dependency.

External fixture modules are exported via ``pytest_plugins`` so their
fixtures are available to every test run while quadkit-testing is
installed.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

# Fixture modules whose fixtures become globally available.
pytest_plugins = [
    "quadkit.testing.fixtures.core",
    "quadkit.testing.fixtures.ai",
    "quadkit.testing.fixtures.db",
    "quadkit.testing.fixtures.web",
    "quadkit.testing.fixtures.tasks",
    "quadkit.testing.integration.fixtures",
]

# Marker declarations registered via config.addinivalue_line("markers", ...).
_MARKERS: list[str] = [
    "requires_redis: mark test as requiring Redis service",
    "requires_postgres: mark test as requiring PostgreSQL service",
    "requires_elasticsearch: mark test as requiring Elasticsearch service",
    "requires_rabbitmq: mark test as requiring RabbitMQ service",
    "requires_meilisearch: mark test as requiring Meilisearch service",
    "requires_smtp: mark test as requiring SMTP service",
    "requires_kafka: mark test as requiring Kafka service",
    "requires_minio: mark test as requiring MinIO service",
    "requires_mongodb: mark test as requiring MongoDB service",
    "requires_qdrant: mark test as requiring Qdrant service",
    "requires_neo4j: mark test as requiring Neo4j service",
    "integration: mark test as an integration test",
    "slow: mark test as a slow running test",
    "performance: mark test as a performance test",
]

# service -> (host, port) for the TCP availability check.
_SERVICE_ENDPOINTS: dict[str, tuple[str, int]] = {
    "redis": ("localhost", 6379),
    "postgres": ("localhost", 5432),
    "elasticsearch": ("localhost", 9200),
    "rabbitmq": ("localhost", 5672),
    "meilisearch": ("localhost", 7700),
    "smtp": ("localhost", 25),
    "kafka": ("localhost", 9092),
    "minio": ("localhost", 9000),
    "mongodb": ("localhost", 27017),
    "qdrant": ("localhost", 6333),
    "neo4j": ("localhost", 7687),
}

# Seconds to wait for a service connection before declaring it unavailable.
_CHECK_TIMEOUT: float = 0.5


def _check_service(service: str) -> bool:
    """Return ``True`` if *service* accepts a TCP connection.

    Uses the service's default localhost port from :data:`_SERVICE_ENDPOINTS`.
    Unknown services are not gated (returns ``True``).  Any connection error
    means the service is unavailable.
    """
    endpoint = _SERVICE_ENDPOINTS.get(service)
    if endpoint is None:
        return True
    host, port = endpoint
    try:
        with socket.create_connection((host, port), timeout=_CHECK_TIMEOUT):
            return True
    except OSError:
        return False


def pytest_configure(config: pytest.Config) -> None:
    """Register the Quadkit markers."""
    for marker in _MARKERS:
        config.addinivalue_line("markers", marker)


def pytest_collection_modifyitems(config: pytest.Config, items: list[Any]) -> None:
    """Auto-skip tests whose required services are unavailable.

    Service availability is cached per service for the duration of the
    collection hook so each endpoint is probed at most once.
    """
    availability: dict[str, bool] = {}
    for item in items:
        for marker in item.iter_markers():
            if not marker.name.startswith("requires_"):
                continue
            service = marker.name.removeprefix("requires_")
            if service not in availability:
                availability[service] = _check_service(service)
            if not availability[service]:
                item.add_marker(pytest.mark.skip(reason=f"{service} not available"))


__all__ = [
    "_CHECK_TIMEOUT",
    "_MARKERS",
    "_SERVICE_ENDPOINTS",
    "_check_service",
    "pytest_collection_modifyitems",
    "pytest_configure",
    "pytest_plugins",
]
