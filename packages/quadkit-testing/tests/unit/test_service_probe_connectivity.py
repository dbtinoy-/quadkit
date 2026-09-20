"""Test ServiceProbe connectivity checks for external services.

ServiceProbe provides async static methods to check availability of common
external services (Redis, Postgres, Elasticsearch, RabbitMQ, Meilisearch, SMTP).
Each method returns True if reachable, False otherwise, suppressing all exceptions.

This test suite validates:
1. Availability detection (returns bool)
2. Exception suppression (no exceptions raised)
3. Custom connection parameters
4. Timeout and connection handling
"""

from __future__ import annotations

import pytest

from quadkit.testing.integration.probes import ServiceProbe


class TestServiceProbeRedis:
    """Test ServiceProbe.check_redis() for Redis availability detection."""

    @pytest.mark.asyncio
    async def test_check_redis_with_default_url_returns_bool(self) -> None:
        """Verify check_redis() returns bool when called with default URL."""
        result = await ServiceProbe.check_redis()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_redis_with_custom_url_returns_bool(self) -> None:
        """Verify check_redis() returns bool with custom URL."""
        result = await ServiceProbe.check_redis("redis://127.0.0.1:6379")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_redis_with_invalid_url_returns_false(self) -> None:
        """Verify check_redis() returns False for unreachable URL."""
        result = await ServiceProbe.check_redis("redis://invalid-host:9999")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_redis_suppresses_all_exceptions(self) -> None:
        """Verify check_redis() does not raise exceptions on connection failure."""
        # Use obviously invalid URL that will fail
        try:
            result = await ServiceProbe.check_redis("redis://invalid-url:99999")
            assert isinstance(result, bool)
            # If we get here without exception, suppression works
            assert True
        except Exception as e:
            pytest.fail(f"check_redis() raised {type(e).__name__}: {e}")


class TestServiceProbePostgres:
    """Test ServiceProbe.check_postgres() for PostgreSQL availability."""

    @pytest.mark.asyncio
    async def test_check_postgres_with_default_dsn_returns_bool(self) -> None:
        """Verify check_postgres() returns bool with default DSN."""
        result = await ServiceProbe.check_postgres()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_postgres_with_custom_dsn_returns_bool(self) -> None:
        """Verify check_postgres() returns bool with custom DSN."""
        result = await ServiceProbe.check_postgres(
            "postgresql://user:password@127.0.0.1:5432/testdb"
        )
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_postgres_with_invalid_dsn_returns_false(self) -> None:
        """Verify check_postgres() returns False for unreachable DSN."""
        result = await ServiceProbe.check_postgres(
            "postgresql://invalid-host:99999/testdb"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_check_postgres_suppresses_all_exceptions(self) -> None:
        """Verify check_postgres() does not raise exceptions."""
        try:
            result = await ServiceProbe.check_postgres(
                "postgresql://invalid:99999/testdb"
            )
            assert isinstance(result, bool)
            assert True
        except Exception as e:
            pytest.fail(f"check_postgres() raised {type(e).__name__}: {e}")


class TestServiceProbeElasticsearch:
    """Test ServiceProbe.check_elasticsearch() for Elasticsearch availability."""

    @pytest.mark.asyncio
    async def test_check_elasticsearch_with_default_url_returns_bool(
        self,
    ) -> None:
        """Verify check_elasticsearch() returns bool with default URL."""
        result = await ServiceProbe.check_elasticsearch()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_elasticsearch_with_custom_url_returns_bool(
        self,
    ) -> None:
        """Verify check_elasticsearch() returns bool with custom URL."""
        result = await ServiceProbe.check_elasticsearch("http://127.0.0.1:9200")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_elasticsearch_with_invalid_url_returns_false(
        self,
    ) -> None:
        """Verify check_elasticsearch() returns False for unreachable URL."""
        result = await ServiceProbe.check_elasticsearch("http://invalid-host:9999")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_elasticsearch_suppresses_all_exceptions(self) -> None:
        """Verify check_elasticsearch() does not raise exceptions."""
        try:
            result = await ServiceProbe.check_elasticsearch("http://invalid-host:9999")
            assert isinstance(result, bool)
            assert True
        except Exception as e:
            pytest.fail(f"check_elasticsearch() raised {type(e).__name__}: {e}")


class TestServiceProbeRabbitMQ:
    """Test ServiceProbe.check_rabbitmq() for RabbitMQ availability."""

    @pytest.mark.asyncio
    async def test_check_rabbitmq_with_default_url_returns_bool(self) -> None:
        """Verify check_rabbitmq() returns bool with default URL."""
        result = await ServiceProbe.check_rabbitmq()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_rabbitmq_with_custom_url_returns_bool(self) -> None:
        """Verify check_rabbitmq() returns bool with custom URL."""
        result = await ServiceProbe.check_rabbitmq("amqp://guest:guest@127.0.0.1/")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_rabbitmq_with_invalid_url_returns_false(self) -> None:
        """Verify check_rabbitmq() returns False for unreachable URL."""
        result = await ServiceProbe.check_rabbitmq("amqp://invalid-host:9999/")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_rabbitmq_suppresses_all_exceptions(self) -> None:
        """Verify check_rabbitmq() does not raise exceptions."""
        try:
            result = await ServiceProbe.check_rabbitmq("amqp://invalid-host:9999/")
            assert isinstance(result, bool)
            assert True
        except Exception as e:
            pytest.fail(f"check_rabbitmq() raised {type(e).__name__}: {e}")


class TestServiceProbeMeilisearch:
    """Test ServiceProbe.check_meilisearch() for Meilisearch availability."""

    @pytest.mark.asyncio
    async def test_check_meilisearch_with_default_url_returns_bool(self) -> None:
        """Verify check_meilisearch() returns bool with default URL."""
        result = await ServiceProbe.check_meilisearch()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_meilisearch_with_custom_url_returns_bool(self) -> None:
        """Verify check_meilisearch() returns bool with custom URL."""
        result = await ServiceProbe.check_meilisearch("http://127.0.0.1:7700")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_meilisearch_with_invalid_url_returns_false(self) -> None:
        """Verify check_meilisearch() returns False for unreachable URL."""
        result = await ServiceProbe.check_meilisearch("http://invalid-host:9999")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_meilisearch_suppresses_all_exceptions(self) -> None:
        """Verify check_meilisearch() does not raise exceptions."""
        try:
            result = await ServiceProbe.check_meilisearch("http://invalid-host:9999")
            assert isinstance(result, bool)
            assert True
        except Exception as e:
            pytest.fail(f"check_meilisearch() raised {type(e).__name__}: {e}")


class TestServiceProbeSMTP:
    """Test ServiceProbe.check_smtp() for SMTP server availability."""

    @pytest.mark.asyncio
    async def test_check_smtp_with_default_parameters_returns_bool(self) -> None:
        """Verify check_smtp() returns bool with default host/port."""
        result = await ServiceProbe.check_smtp()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_smtp_with_custom_host_returns_bool(self) -> None:
        """Verify check_smtp() returns bool with custom host."""
        result = await ServiceProbe.check_smtp(host="127.0.0.1", port=25)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_smtp_with_custom_port_returns_bool(self) -> None:
        """Verify check_smtp() returns bool with custom port."""
        result = await ServiceProbe.check_smtp(host="localhost", port=587)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_smtp_with_invalid_host_returns_false(self) -> None:
        """Verify check_smtp() returns False for unreachable host."""
        result = await ServiceProbe.check_smtp(
            host="invalid-host.example.com", port=9999
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_check_smtp_suppresses_all_exceptions(self) -> None:
        """Verify check_smtp() does not raise exceptions."""
        try:
            result = await ServiceProbe.check_smtp(
                host="invalid-host.example.com", port=9999
            )
            assert isinstance(result, bool)
            assert True
        except Exception as e:
            pytest.fail(f"check_smtp() raised {type(e).__name__}: {e}")


class TestServiceProbeIntegration:
    """Integration tests for ServiceProbe across multiple checks."""

    @pytest.mark.asyncio
    async def test_concurrent_probe_checks_return_bool(self) -> None:
        """Verify multiple concurrent probe calls all return bool."""
        import asyncio

        results = await asyncio.gather(
            ServiceProbe.check_redis("redis://invalid:9999"),
            ServiceProbe.check_postgres("postgresql://invalid:9999/db"),
            ServiceProbe.check_elasticsearch("http://invalid:9999"),
            ServiceProbe.check_rabbitmq("amqp://invalid:9999/"),
            ServiceProbe.check_meilisearch("http://invalid:9999"),
            ServiceProbe.check_smtp(host="invalid", port=9999),
        )
        assert all(isinstance(r, bool) for r in results)
        # All invalid hosts should return False
        assert all(r is False for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_checks_handle_timeouts(self) -> None:
        """Verify concurrent checks with short timeouts don't raise."""
        import asyncio

        # Use intentionally slow/unreachable services
        try:
            results = await asyncio.gather(
                ServiceProbe.check_redis("redis://192.0.2.1:6379"),  # TEST-NET-1
                ServiceProbe.check_postgres("postgresql://192.0.2.1:5432/db"),
                ServiceProbe.check_elasticsearch("http://192.0.2.1:9200"),
                return_exceptions=True,
            )
            # All should return bool, not exceptions
            for result in results:
                if isinstance(result, Exception):
                    pytest.fail(f"Probe raised exception: {result}")
                assert isinstance(result, bool)
        except Exception as e:
            pytest.fail(f"Concurrent probes raised {type(e).__name__}: {e}")
