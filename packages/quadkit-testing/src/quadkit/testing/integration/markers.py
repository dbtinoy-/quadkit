"""Pytest skip-markers for external service availability.

Import these markers and apply them to tests (or test classes) that
require a specific service to be running.  When the Quadkit pytest
plugin is active (via ``pytest_plugins`` or the installed entry-point),
tests are automatically skipped if the service is not available.

Usage::

    from quadkit.testing import requires_redis, requires_postgres

    @requires_redis
    @pytest.mark.asyncio
    async def test_redis_cache():
        ...

    @requires_postgres
    class TestPostgresRepository:
        ...
"""

from __future__ import annotations

import pytest

__all__ = [
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

# Named marks — the Quadkit pytest plugin (plugin.py) handles
# the actual skip logic based on service availability at collection time.
requires_redis = pytest.mark.requires_redis
requires_postgres = pytest.mark.requires_postgres
requires_elasticsearch = pytest.mark.requires_elasticsearch
requires_rabbitmq = pytest.mark.requires_rabbitmq
requires_meilisearch = pytest.mark.requires_meilisearch
requires_smtp = pytest.mark.requires_smtp
requires_kafka = pytest.mark.requires_kafka
requires_minio = pytest.mark.requires_minio
requires_mongodb = pytest.mark.requires_mongodb
requires_qdrant = pytest.mark.requires_qdrant
requires_neo4j = pytest.mark.requires_neo4j
