"""Unit tests for the in-process ``FakeRedisClient`` used by docker-free tests."""

from __future__ import annotations

from quadkit.testing.fakes.redis import FakeRedisClient


class TestFakeRedisClientPing:
    """The in-process client answers ping without any live Redis."""

    async def test_ping_returns_true(self, redis_fake: FakeRedisClient) -> None:
        """ping() confirms the fake client is reachable."""
        assert await redis_fake.ping() is True


class TestFakeRedisSetGet:
    """set/get round-trip semantics match ``redis.asyncio``."""

    async def test_set_get_round_trip(self, redis_fake: FakeRedisClient) -> None:
        """set() stores a value that get() returns unchanged."""
        assert await redis_fake.set("name", "alice") is True
        assert await redis_fake.get("name") == "alice"

    async def test_get_missing_returns_none(self, redis_fake: FakeRedisClient) -> None:
        """get() on an absent key returns None."""
        assert await redis_fake.get("missing") is None

    async def test_set_overwrites_existing_value(
        self, redis_fake: FakeRedisClient
    ) -> None:
        """set() replaces an existing value for the same key."""
        await redis_fake.set("count", "1")
        await redis_fake.set("count", "2")
        assert await redis_fake.get("count") == "2"

    async def test_nx_does_not_overwrite(self, redis_fake: FakeRedisClient) -> None:
        """nx=True only sets when the key is absent."""
        await redis_fake.set("key", "first")
        assert await redis_fake.set("key", "second", nx=True) is None
        assert await redis_fake.get("key") == "first"

    async def test_nx_sets_when_absent(self, redis_fake: FakeRedisClient) -> None:
        """nx=True writes when the key does not exist."""
        assert await redis_fake.set("fresh", "value", nx=True) is True
        assert await redis_fake.get("fresh") == "value"

    async def test_xx_only_sets_existing(self, redis_fake: FakeRedisClient) -> None:
        """xx=True only updates keys that already exist."""
        assert await redis_fake.set("key", "v1", xx=True) is None
        await redis_fake.set("key", "v1")
        assert await redis_fake.set("key", "v2", xx=True) is True
        assert await redis_fake.get("key") == "v2"


class TestFakeRedisKeys:
    """Key-level operations behave like redis.asyncio."""

    async def test_delete_returns_removed_count(
        self, redis_fake: FakeRedisClient
    ) -> None:
        """delete() reports the number of removed keys."""
        await redis_fake.set("a", "1")
        await redis_fake.set("b", "2")
        assert await redis_fake.delete("a", "b", "missing") == 2

    async def test_exists_counts_present_keys(
        self, redis_fake: FakeRedisClient
    ) -> None:
        """exists() returns how many keys hold live values."""
        await redis_fake.set("a", "1")
        assert await redis_fake.exists("a", "b") == 1

    async def test_flushdb_clears_store(self, redis_fake: FakeRedisClient) -> None:
        """flushdb() empties the fake store."""
        await redis_fake.set("a", "1")
        assert await redis_fake.flushdb() is True
        assert await redis_fake.exists("a") == 0


class TestFakeRedisExpiry:
    """TTL handling is deterministic via monotonic timestamps."""

    async def test_expire_removes_value(self, redis_fake: FakeRedisClient) -> None:
        """A key expired with expire(key, 0) is no longer readable."""
        await redis_fake.set("temp", "value")
        assert await redis_fake.expire("temp", 0) is True
        assert await redis_fake.get("temp") is None

    async def test_ttl_live_key(self, redis_fake: FakeRedisClient) -> None:
        """ttl() reports remaining seconds for a live key."""
        await redis_fake.set("temp", "value", ex=60)
        ttl = await redis_fake.ttl("temp")
        assert ttl > 0

    async def test_ttl_missing_key(self, redis_fake: FakeRedisClient) -> None:
        """ttl() returns -2 for keys that never existed."""
        assert await redis_fake.ttl("gone") == -2

    async def test_value_created_with_ms_ttl_expires(
        self, redis_fake: FakeRedisClient
    ) -> None:
        """px (millisecond TTL) is honoured at read time."""
        await redis_fake.set("fast", "value", px=1)
        ttl = await redis_fake.ttl("fast")
        assert 0 <= ttl <= 1


class TestFakeRedisIsolation:
    """Each fake instance owns an independent store."""

    async def test_instances_do_not_share_state(self) -> None:
        """Two FakeRedisClient instances never see each other's data."""
        first = FakeRedisClient()
        second = FakeRedisClient()
        await first.set("shared", "value")
        assert await second.get("shared") is None

    async def test_fixture_provides_fresh_instance(
        self, redis_fake: FakeRedisClient
    ) -> None:
        """The redis_fake fixture yields an empty client per test."""
        assert await redis_fake.exists("anything") == 0