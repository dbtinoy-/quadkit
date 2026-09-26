"""Pytest fixtures for quadkit-cache integration tests.

``redis_client`` is overridden here so cache integration tests run without a
pre-started Docker Compose stack: a live Redis is used when reachable, and an
in-process :class:`~quadkit.testing.fakes.redis.FakeRedisClient` takes over
otherwise.  The default ``-m "not integration"`` run never touches any of
this — these fixtures are only loaded for integration tests.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio

from quadkit.testing.fakes.redis import FakeRedisClient
from quadkit.testing.integration.config import IntegrationTestConfig
from quadkit.testing.integration.probes import ServiceProbe


@pytest_asyncio.fixture(scope="session")
async def redis_client(
    integration_config: IntegrationTestConfig,
) -> AsyncGenerator[object, None]:
    """Yield a live Redis client, or an in-process fake when Redis is down.

    Args:
        integration_config: Service connection settings from the environment.

    Yields:
        A real ``redis.asyncio.Redis`` client when the service is reachable;
        otherwise an in-process ``FakeRedisClient``.
    """
    if await ServiceProbe.check_redis(integration_config.redis_url):
        try:
            import redis.asyncio as redis

            client = redis.from_url(integration_config.redis_url, decode_responses=True)
        except ImportError:
            yield FakeRedisClient()
            return
        try:
            yield client
        finally:
            await client.close()
        return
    yield FakeRedisClient()