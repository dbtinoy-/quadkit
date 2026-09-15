from __future__ import annotations

"""Infrastructure pytest fixtures for integration tests.

These fixtures provide connected clients for all supported external services.
Each fixture probes the service first and skips the test if unavailable.

Usage in conftest.py::

    pytest_plugins = ["quadkit.testing.integration.fixtures"]

Available fixtures:
    - integration_config   — IntegrationTestConfig (session scope)
    - postgres_pool        — asyncpg Pool (session scope)
    - postgres_conn        — asyncpg Connection (function scope)
    - redis_client         — redis.asyncio.Redis (session scope)
    - kafka_producer       — AIOKafkaProducer (session scope)
    - elasticsearch_client — AsyncElasticsearch (session scope)
    - elasticsearch_index  — unique index name (function scope)
    - mongodb_client       — AsyncIOMotorClient (session scope)
    - mongodb_database     — AsyncIOMotorDatabase (function scope)
    - minio_client         — placeholder for MinIO client (session scope)
    - minio_bucket         — unique bucket name (function scope)
    - qdrant_client        — AsyncQdrantClient (session scope)
    - neo4j_driver         — AsyncGraphDatabase driver (session scope)
    - neo4j_session        — AsyncSession (function scope)
"""

from collections.abc import AsyncGenerator
from importlib import import_module
from typing import Any, cast
import uuid

import pytest
import pytest_asyncio

from quadkit.testing.integration.config import IntegrationTestConfig
from quadkit.testing.integration.probes import ServiceProbe

__all__ = [
    "elasticsearch_client",
    "elasticsearch_index",
    "integration_config",
    "kafka_producer",
    "minio_bucket",
    "minio_client",
    "mongodb_client",
    "mongodb_database",
    "neo4j_driver",
    "neo4j_session",
    "postgres_conn",
    "postgres_pool",
    "qdrant_client",
    "redis_client",
]


# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def integration_config() -> IntegrationTestConfig:
    """Return the integration test configuration populated from the environment.

    Returns:
        IntegrationTestConfig with Docker Compose defaults.
    """
    return IntegrationTestConfig.from_env()


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def postgres_pool(
    integration_config: IntegrationTestConfig,
) -> AsyncGenerator[object, None]:
    """Yield a session-scoped asyncpg connection pool.

    Skips if PostgreSQL is not reachable.

    Args:
        integration_config: Service configuration.

    Yields:
        asyncpg.Pool connected to the test database.
    """
    if not await ServiceProbe.check_postgres(integration_config.postgres_dsn_raw):
        pytest.skip("PostgreSQL not available")

    try:
        asyncpg = cast("Any", import_module("asyncpg"))
    except ImportError:
        pytest.skip("asyncpg not installed")

    pool = await asyncpg.create_pool(
        integration_config.postgres_dsn_raw, min_size=1, max_size=5
    )
    try:
        yield pool
    finally:
        await pool.close()


@pytest_asyncio.fixture
async def postgres_conn(postgres_pool: object) -> AsyncGenerator[object, None]:
    """Yield a function-scoped asyncpg connection from the pool.

    Args:
        postgres_pool: Session-scoped asyncpg pool.

    Yields:
        asyncpg.Connection for the duration of a single test.
    """
    async with postgres_pool.acquire() as conn:  # type: ignore[attr-defined]
        yield conn


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def redis_client(
    integration_config: IntegrationTestConfig,
) -> AsyncGenerator[object, None]:
    """Yield a session-scoped async Redis client.

    Skips if Redis is not reachable.

    Args:
        integration_config: Service configuration.

    Yields:
        redis.asyncio.Redis connected to the test database.
    """
    if not await ServiceProbe.check_redis(integration_config.redis_url):
        pytest.skip("Redis not available")

    try:
        import redis.asyncio as redis
    except ImportError:
        pytest.skip("redis not installed")

    client = redis.from_url(integration_config.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Kafka
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def kafka_producer(
    integration_config: IntegrationTestConfig,
) -> AsyncGenerator[object, None]:
    """Yield a session-scoped AIOKafkaProducer.

    Skips if Kafka is not reachable.

    Args:
        integration_config: Service configuration.

    Yields:
        aiokafka.AIOKafkaProducer connected to the test broker.
    """
    if not await ServiceProbe.check_kafka(integration_config.kafka_bootstrap):
        pytest.skip("Kafka not available")

    try:
        aiokafka = cast("Any", import_module("aiokafka"))
    except ImportError:
        pytest.skip("aiokafka not installed")

    producer = aiokafka.AIOKafkaProducer(
        bootstrap_servers=integration_config.kafka_bootstrap
    )
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()


# ---------------------------------------------------------------------------
# Elasticsearch
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def elasticsearch_client(
    integration_config: IntegrationTestConfig,
) -> AsyncGenerator[object, None]:
    """Yield a session-scoped AsyncElasticsearch client.

    Skips if Elasticsearch is not reachable.

    Args:
        integration_config: Service configuration.

    Yields:
        elasticsearch.AsyncElasticsearch connected to the test cluster.
    """
    if not await ServiceProbe.check_elasticsearch(integration_config.elasticsearch_url):
        pytest.skip("Elasticsearch not available")

    try:
        from elasticsearch import AsyncElasticsearch  # type: ignore[import-not-found]
    except ImportError:
        pytest.skip("elasticsearch[async] not installed")

    client = AsyncElasticsearch(hosts=[integration_config.elasticsearch_url])
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def elasticsearch_index() -> str:
    """Return a unique Elasticsearch index name for test isolation.

    Returns:
        A unique index name string.
    """
    return f"quadkit_test_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def mongodb_client(
    integration_config: IntegrationTestConfig,
) -> AsyncGenerator[object, None]:
    """Yield a session-scoped AsyncIOMotorClient.

    Skips if MongoDB is not reachable.

    Args:
        integration_config: Service configuration.

    Yields:
        motor.AsyncIOMotorClient connected to the test server.
    """
    if not await ServiceProbe.check_mongodb(integration_config.mongodb_dsn):
        pytest.skip("MongoDB not available")

    try:
        from motor.motor_asyncio import (
            AsyncIOMotorClient,
        )
    except ImportError:
        pytest.skip("motor not installed")

    client: Any = AsyncIOMotorClient(integration_config.mongodb_dsn)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def mongodb_database(mongodb_client: object) -> object:
    """Return a function-scoped MongoDB database with a unique name.

    Args:
        mongodb_client: Session-scoped motor client.

    Returns:
        AsyncIOMotorDatabase for the duration of a single test.
    """
    db_name = f"quadkit_test_{uuid.uuid4().hex[:12]}"
    return mongodb_client[db_name]  # type: ignore[index]


# ---------------------------------------------------------------------------
# MinIO
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def minio_client(
    integration_config: IntegrationTestConfig,
) -> AsyncGenerator[object, None]:
    """Yield a session-scoped MinIO client placeholder.

    Skips if MinIO is not reachable.

    Args:
        integration_config: Service configuration.

    Yields:
        MinIO client object (implementation-specific).
    """
    if not await ServiceProbe.check_minio(integration_config.minio_endpoint):
        pytest.skip("MinIO not available")

    # MinIO client instantiation depends on the chosen library (miniopy-async, boto3, etc.)
    # Concrete packages should provide their own fixture that wraps this one.
    yield None


@pytest.fixture
def minio_bucket() -> str:
    """Return a unique MinIO bucket name for test isolation.

    Returns:
        A unique bucket name string.
    """
    return f"quadkit-test-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def qdrant_client(
    integration_config: IntegrationTestConfig,
) -> AsyncGenerator[object, None]:
    """Yield a session-scoped AsyncQdrantClient.

    Skips if Qdrant is not reachable.

    Args:
        integration_config: Service configuration.

    Yields:
        qdrant_client.AsyncQdrantClient connected to the test server.
    """
    if not await ServiceProbe.check_qdrant(integration_config.qdrant_url):
        pytest.skip("Qdrant not available")

    try:
        qdrant_client = cast("Any", import_module("qdrant_client"))
    except ImportError:
        pytest.skip("qdrant-client not installed")

    client = qdrant_client.AsyncQdrantClient(url=integration_config.qdrant_url)
    try:
        yield client
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Neo4j
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def neo4j_driver(
    integration_config: IntegrationTestConfig,
) -> AsyncGenerator[object, None]:
    """Yield a session-scoped async Neo4j driver.

    Skips if Neo4j is not reachable.

    Args:
        integration_config: Service configuration.

    Yields:
        neo4j.AsyncDriver connected to the test database.
    """
    if not await ServiceProbe.check_neo4j(integration_config.neo4j_url):
        pytest.skip("Neo4j not available")

    try:
        import neo4j  # type: ignore[import-not-found]
    except ImportError:
        pytest.skip("neo4j not installed")

    user, password = integration_config.neo4j_auth.split("/", 1)
    driver = neo4j.AsyncGraphDatabase.driver(
        integration_config.neo4j_url,
        auth=(user, password),
    )
    try:
        yield driver
    finally:
        await driver.close()


@pytest_asyncio.fixture
async def neo4j_session(neo4j_driver: object) -> AsyncGenerator[object, None]:
    """Yield a function-scoped async Neo4j session.

    Args:
        neo4j_driver: Session-scoped Neo4j driver.

    Yields:
        neo4j.AsyncSession for the duration of a single test.
    """
    async with neo4j_driver.session() as session:  # type: ignore[attr-defined]
        yield session
