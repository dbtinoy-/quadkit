"""Integration test infrastructure for Quadkit.

Provides async service availability probes and pytest skip-markers.
"""

from __future__ import annotations

from quadkit.testing.harness.environment import IntegrationEnvironment
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
