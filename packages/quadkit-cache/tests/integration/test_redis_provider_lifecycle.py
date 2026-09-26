from __future__ import annotations

"""Redis cache provider lifecycle tests."""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_redis]


class TestRedisProviderLifecycle:
    """Verify Redis cache provider boots with real Redis."""

    async def test_provider_can_connect(self, redis_client: object) -> None:
        """Redis client fixture connection is functional."""
        result = await redis_client.ping()  # type: ignore[union-attr]
        assert result is True

    async def test_set_and_get_round_trip(self, redis_client: object) -> None:
        """Basic set/get round-trip confirms real Redis connectivity."""
        await redis_client.set("lifecycle_test_key", "alive")  # type: ignore[union-attr]
        value = await redis_client.get("lifecycle_test_key")
        assert value == "alive"
