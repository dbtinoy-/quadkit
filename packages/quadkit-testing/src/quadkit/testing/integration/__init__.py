"""Integration test infrastructure for Quadkit.

Provides async service availability probes and pytest skip-markers.
"""

from __future__ import annotations

from typing import Any, Final

from quadkit.testing._lazy_exports import resolve_export
from quadkit.testing.integration.config import IntegrationTestConfig
from quadkit.testing.integration.markers import (
    requires_elasticsearch,
    requires_kafka,
    requires_meilisearch,
    requires_minio,
    requires_mongodb,
    requires_neo4j,
    requires_postgres,
    requires_qdrant,
    requires_rabbitmq,
    requires_redis,
    requires_smtp,
)
from quadkit.testing.integration.probes import ServiceProbe

_LAZY_IMPORTS: Final[dict[str, tuple[str, str]]] = {
    "IntegrationEnvironment": (
        "quadkit.testing.harness.environment",
        "IntegrationEnvironment",
    ),
}

# The environment adapter targets private service packages and is omitted from
# the public projection; markers and probes remain public utilities.
_OPTIONAL_MODULES: Final[frozenset[str]] = frozenset(
    {"quadkit.testing.harness.environment"}
)


def __getattr__(name: str) -> Any:
    """Import and return a public attribute on first access."""
    return resolve_export(
        name,
        _LAZY_IMPORTS,
        package=__name__,
        optional=_OPTIONAL_MODULES,
    )


def __dir__() -> list[str]:
    """Return the importable public names."""
    return sorted(__all__)


__all__ = [
    "IntegrationEnvironment",
    "IntegrationTestConfig",
    "ServiceProbe",
    "requires_elasticsearch",
    "requires_kafka",
    "requires_meilisearch",
    "requires_minio",
    "requires_mongodb",
    "requires_neo4j",
    "requires_postgres",
    "requires_qdrant",
    "requires_rabbitmq",
    "requires_redis",
    "requires_smtp",
]
