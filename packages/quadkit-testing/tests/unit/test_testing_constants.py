"""Unit tests for quadkit-testing constants."""

import pytest

from quadkit.testing.constants import (
    DEFAULT_ELASTICSEARCH_PORT,
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_MEILISEARCH_PORT,
    DEFAULT_POSTGRES_PORT,
    DEFAULT_PROBE_INTERVAL,
    DEFAULT_PROBE_TIMEOUT,
    DEFAULT_RABBITMQ_PORT,
    DEFAULT_REDIS_PORT,
    DEFAULT_SMTP_PORT,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
    MARKER_ELASTICSEARCH,
    MARKER_MEILISEARCH,
    MARKER_POSTGRES,
    MARKER_RABBITMQ,
    MARKER_REDIS,
    MARKER_SMTP,
)


class TestTestingConstants:
    """Tests for testing constants."""

    def test_env_prefix(self) -> None:
        """Test environment variable prefix."""
        assert ENV_PREFIX == "QK_TESTING__"
        assert isinstance(ENV_PREFIX, str)

    def test_env_nested_delimiter(self) -> None:
        """Test environment variable nested delimiter."""
        assert ENV_NESTED_DELIMITER == "__"
        assert isinstance(ENV_NESTED_DELIMITER, str)

    def test_default_probe_timeout(self) -> None:
        """Test default probe timeout."""
        assert DEFAULT_PROBE_TIMEOUT == 30.0
        assert isinstance(DEFAULT_PROBE_TIMEOUT, float)
        assert DEFAULT_PROBE_TIMEOUT > 0

    def test_default_probe_interval(self) -> None:
        """Test default probe interval."""
        assert DEFAULT_PROBE_INTERVAL == 0.5
        assert isinstance(DEFAULT_PROBE_INTERVAL, float)
        assert DEFAULT_PROBE_INTERVAL > 0

    def test_default_http_timeout(self) -> None:
        """Test default HTTP timeout."""
        assert DEFAULT_HTTP_TIMEOUT == 10.0
        assert isinstance(DEFAULT_HTTP_TIMEOUT, float)
        assert DEFAULT_HTTP_TIMEOUT > 0

    def test_default_redis_port(self) -> None:
        """Test default Redis port."""
        assert DEFAULT_REDIS_PORT == 6379
        assert isinstance(DEFAULT_REDIS_PORT, int)
        assert DEFAULT_REDIS_PORT > 0

    def test_default_postgres_port(self) -> None:
        """Test default PostgreSQL port."""
        assert DEFAULT_POSTGRES_PORT == 5432
        assert isinstance(DEFAULT_POSTGRES_PORT, int)
        assert DEFAULT_POSTGRES_PORT > 0

    def test_default_rabbitmq_port(self) -> None:
        """Test default RabbitMQ port."""
        assert DEFAULT_RABBITMQ_PORT == 5672
        assert isinstance(DEFAULT_RABBITMQ_PORT, int)
        assert DEFAULT_RABBITMQ_PORT > 0

    def test_default_smtp_port(self) -> None:
        """Test default SMTP port."""
        assert DEFAULT_SMTP_PORT == 25
        assert isinstance(DEFAULT_SMTP_PORT, int)
        assert DEFAULT_SMTP_PORT > 0

    def test_default_elasticsearch_port(self) -> None:
        """Test default Elasticsearch port."""
        assert DEFAULT_ELASTICSEARCH_PORT == 9200
        assert isinstance(DEFAULT_ELASTICSEARCH_PORT, int)
        assert DEFAULT_ELASTICSEARCH_PORT > 0

    def test_default_meilisearch_port(self) -> None:
        """Test default Meilisearch port."""
        assert DEFAULT_MEILISEARCH_PORT == 7700
        assert isinstance(DEFAULT_MEILISEARCH_PORT, int)
        assert DEFAULT_MEILISEARCH_PORT > 0

    def test_marker_redis(self) -> None:
        """Test Redis marker."""
        assert MARKER_REDIS == "redis"
        assert isinstance(MARKER_REDIS, str)

    def test_marker_postgres(self) -> None:
        """Test PostgreSQL marker."""
        assert MARKER_POSTGRES == "postgres"
        assert isinstance(MARKER_POSTGRES, str)

    def test_marker_rabbitmq(self) -> None:
        """Test RabbitMQ marker."""
        assert MARKER_RABBITMQ == "rabbitmq"
        assert isinstance(MARKER_RABBITMQ, str)

    def test_marker_smtp(self) -> None:
        """Test SMTP marker."""
        assert MARKER_SMTP == "smtp"
        assert isinstance(MARKER_SMTP, str)

    def test_marker_elasticsearch(self) -> None:
        """Test Elasticsearch marker."""
        assert MARKER_ELASTICSEARCH == "elasticsearch"
        assert isinstance(MARKER_ELASTICSEARCH, str)

    def test_marker_meilisearch(self) -> None:
        """Test Meilisearch marker."""
        assert MARKER_MEILISEARCH == "meilisearch"
        assert isinstance(MARKER_MEILISEARCH, str)

    def test_all_exports(self) -> None:
        """Test that all constants are properly exported."""
        from quadkit.testing import constants

        expected = [
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
        for name in expected:
            assert hasattr(constants, name)
