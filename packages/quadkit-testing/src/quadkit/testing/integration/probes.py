"""Async service availability probes for integration tests.

``ServiceProbe`` checks whether external services are reachable before
tests that depend on them are executed.  Use it in conftest fixtures or
test-setup code to skip tests gracefully.

All methods are ``staticmethod`` — no instantiation needed::

    available = await ServiceProbe.check_redis()
    if not available:
        pytest.skip("Redis not available")
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, cast

from quadkit.logging import get_logger

__all__ = ["ServiceProbe"]

logger = get_logger(__name__)


class ServiceProbe:
    """Async probes for common external services.

    Each method attempts a real network connection and returns ``True``
    if the service is reachable, ``False`` otherwise.  All probes
    suppress *all* exceptions — they are purely availability indicators,
    not functional tests.

    Example::

        @pytest.fixture
        async def redis_client():
            if not await ServiceProbe.check_redis():
                pytest.skip("Redis not available")
            # ... connect and return client
    """

    @staticmethod
    async def check_redis(url: str = "redis://localhost:6379") -> bool:
        """Return ``True`` if a Redis server is reachable at *url*."""
        try:
            import redis.asyncio as redis

            client = cast("Any", redis.from_url(url, socket_connect_timeout=1))
            await client.ping()
            await client.close()
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug("probe_failed", dependency="redis", url=url, error=str(e))
            return False

    @staticmethod
    async def check_postgres(
        dsn: str = "postgresql://localhost/test",
    ) -> bool:
        """Return ``True`` if a PostgreSQL server is reachable at *dsn*."""
        try:
            asyncpg = cast("Any", import_module("asyncpg"))

            conn = await asyncpg.connect(dsn, timeout=2)
            await conn.close()
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug("probe_failed", dependency="postgres", dsn=dsn, error=str(e))
            return False

    @staticmethod
    async def check_elasticsearch(url: str = "http://localhost:9200") -> bool:
        """Return ``True`` if an Elasticsearch HTTP endpoint is reachable."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception as e:  # noqa: BLE001
            logger.debug(
                "probe_failed", dependency="elasticsearch", url=url, error=str(e)
            )
            return False

    @staticmethod
    async def check_rabbitmq(
        url: str = "amqp://guest:guest@localhost:5672/",
    ) -> bool:
        """Return ``True`` if a RabbitMQ AMQP broker is reachable."""
        try:
            aio_pika = cast("Any", import_module("aio_pika"))

            connection = await aio_pika.connect_robust(url, timeout=2)
            await connection.close()
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug("probe_failed", dependency="rabbitmq", url=url, error=str(e))
            return False

    @staticmethod
    async def check_meilisearch(url: str = "http://localhost:7700") -> bool:
        """Return ``True`` if a Meilisearch HTTP endpoint is reachable."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{url}/health")
                return response.status_code == 200
        except Exception as e:  # noqa: BLE001
            logger.debug(
                "probe_failed", dependency="meilisearch", url=url, error=str(e)
            )
            return False

    @staticmethod
    async def check_smtp(host: str = "localhost", port: int = 25) -> bool:
        """Return ``True`` if an SMTP server is accepting connections."""
        import asyncio

        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=2.0,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug(
                "probe_failed", dependency="smtp", host=host, port=port, error=str(e)
            )
            return False

    @staticmethod
    async def check_kafka(bootstrap: str = "localhost:19092") -> bool:
        """Return True if a Kafka broker is reachable.

        Args:
            bootstrap: Kafka bootstrap server address.

        Returns:
            True if a broker connection succeeds.
        """
        import asyncio

        try:
            host, port_str = bootstrap.split(":", 1)
            port = int(port_str)
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug(
                "probe_failed", dependency="kafka", bootstrap=bootstrap, error=str(e)
            )
            return False

    @staticmethod
    async def check_minio(endpoint: str = "localhost:19000") -> bool:
        """Return True if a MinIO endpoint is reachable.

        Args:
            endpoint: MinIO endpoint in host:port format.

        Returns:
            True if the HTTP endpoint responds.
        """
        import asyncio

        try:
            host, port_str = endpoint.split(":", 1)
            port = int(port_str)
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug(
                "probe_failed", dependency="minio", endpoint=endpoint, error=str(e)
            )
            return False

    @staticmethod
    async def check_mongodb(dsn: str = "mongodb://localhost:17017") -> bool:
        """Return True if a MongoDB server is reachable.

        Args:
            dsn: MongoDB connection string.

        Returns:
            True if the server responds to a ping.
        """
        import asyncio
        from urllib.parse import urlparse

        try:
            parsed = urlparse(dsn)
            host = parsed.hostname or "localhost"
            port = parsed.port or 27017
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug("probe_failed", dependency="mongodb", dsn=dsn, error=str(e))
            return False

    @staticmethod
    async def check_qdrant(url: str = "http://localhost:16333") -> bool:
        """Return True if a Qdrant vector store is reachable.

        Args:
            url: Qdrant HTTP URL.

        Returns:
            True if the healthz endpoint responds with 200.
        """
        import asyncio
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6333
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug("probe_failed", dependency="qdrant", url=url, error=str(e))
            return False

    @staticmethod
    async def check_neo4j(url: str = "bolt://localhost:17687") -> bool:
        """Return True if a Neo4j graph database is reachable.

        Args:
            url: Neo4j bolt URL.

        Returns:
            True if a TCP connection to the bolt port succeeds.
        """
        import asyncio
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 7687
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug("probe_failed", dependency="neo4j", url=url, error=str(e))
            return False
