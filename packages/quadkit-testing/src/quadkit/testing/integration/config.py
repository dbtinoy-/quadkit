from __future__ import annotations

"""Integration test service configuration.

All values are read from environment variables with Docker Compose defaults.
"""

from dataclasses import dataclass, field
import os

__all__ = ["IntegrationTestConfig"]


@dataclass(frozen=True)
class IntegrationTestConfig:
    """Configuration for integration tests.

    All values read from environment variables with Docker Compose defaults.

    Attributes:
        postgres_dsn: SQLAlchemy-style async DSN for PostgreSQL.
        postgres_dsn_raw: Plain asyncpg DSN (no +asyncpg driver prefix).
        redis_url: Redis connection URL.
        kafka_bootstrap: Kafka bootstrap servers.
        minio_endpoint: MinIO endpoint (host:port).
        minio_access_key: MinIO access key.
        minio_secret_key: MinIO secret key.
        elasticsearch_url: Elasticsearch base URL.
        mongodb_dsn: MongoDB connection string.
        qdrant_url: Qdrant HTTP URL.
        neo4j_url: Neo4j bolt URL.
        neo4j_auth: Neo4j auth string (user/password).
    """

    postgres_dsn: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_POSTGRES_DSN",
            "postgresql+asyncpg://quadkit:quadkit@localhost:15432/quadkit_test",
        )
    )
    postgres_dsn_raw: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_POSTGRES_DSN_RAW",
            "postgresql://quadkit:quadkit@localhost:15432/quadkit_test",
        )
    )
    redis_url: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_REDIS_URL",
            "redis://localhost:16379/15",
        )
    )
    kafka_bootstrap: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_KAFKA_BOOTSTRAP",
            "localhost:19092",
        )
    )
    minio_endpoint: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_MINIO_ENDPOINT",
            "localhost:19000",
        )
    )
    minio_access_key: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_MINIO_ACCESS_KEY",
            "minioadmin",
        )
    )
    minio_secret_key: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_MINIO_SECRET_KEY",
            "minioadmin",
        )
    )
    elasticsearch_url: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_ELASTICSEARCH_URL",
            "http://localhost:19200",
        )
    )
    mongodb_dsn: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_MONGODB_DSN",
            "mongodb://localhost:17017",
        )
    )
    qdrant_url: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_QDRANT_URL",
            "http://localhost:16333",
        )
    )
    neo4j_url: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_NEO4J_URL",
            "bolt://localhost:17687",
        )
    )
    neo4j_auth: str = field(
        default_factory=lambda: os.environ.get(
            "QK_TEST_NEO4J_AUTH",
            "neo4j/testpassword",
        )
    )

    @classmethod
    def from_env(cls) -> IntegrationTestConfig:
        """Create config from current environment variables.

        Returns:
            IntegrationTestConfig populated from environment with Docker Compose defaults.
        """
        return cls()
