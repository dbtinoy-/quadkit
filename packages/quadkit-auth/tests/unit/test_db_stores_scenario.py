"""Scenario tests for database-backed user + OAuth identity stores.

Covers ``RedisUserStore`` (read-through cache semantics, credential
isolation, TTL) and ``MongoDBOAuthIdentityStore`` (link CRUD, user
resolution, sync-path refusal) against hermetic fakes — no live
Redis/MongoDB.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from quadkit.auth.models.user import User, UserCredentials
from quadkit.auth.storage.db_stores import RedisUserStore
from quadkit.auth.storage.oauth_identity_store._mongodb import (
    MongoDBOAuthIdentityStore,
)


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class _FakeRedis:
    """Minimal Redis-like async client (hashes only, what the store uses).

    Stores values as **bytes** (str-encoded) like a real redis client
    returns from ``HGETALL`` — this keeps the decode path exercised.
    """

    def __init__(self) -> None:
        self.hashes: dict[str, dict[bytes, bytes]] = {}
        self.ttls: dict[str, int] = {}
        self.calls: list[str] = []

    @staticmethod
    def _b(val: Any) -> bytes:
        if isinstance(val, bytes):
            return val
        if isinstance(val, str):
            return val.encode()
        return str(val).encode()

    async def hset(self, key: str, mapping: dict[str, Any]) -> Any:
        self.calls.append("hset")
        existing = self.hashes.setdefault(key, {})
        existing.update({self._b(k): self._b(v) for k, v in mapping.items()})
        return len(mapping)

    async def hgetall(self, key: str) -> dict[bytes, bytes]:
        self.calls.append("hgetall")
        return dict(self.hashes.get(key, {}))

    async def expire(self, key: str, ttl: int) -> Any:
        self.calls.append("expire")
        self.ttls[key] = ttl
        return True

    async def delete(self, key: str) -> Any:
        self.calls.append("delete")
        self.hashes.pop(key, None)
        self.ttls.pop(key, None)
        return 1 if key in self.hashes else 0


class _FakeDbProvider:
    def __init__(self, redis: _FakeRedis | None = None) -> None:
        self.redis = redis or _FakeRedis()


class _FakeDeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class _FakeCursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def __aiter__(self) -> "_FakeCursor":
        self._it = iter(self._docs)
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None


class _FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
        self.indexes: list[tuple[tuple[tuple[str, int], ...], dict[str, Any]]] = []

    async def create_index(
        self, keys: list[tuple[str, int]], **kwargs: Any
    ) -> Any:
        self.indexes.append((tuple(keys), kwargs))
        return "idx"

    async def insert_one(self, doc: dict[str, Any]) -> Any:
        self.docs.append(doc)
        return None

    async def find_one(
        self,
        query: dict[str, Any],
        projection: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                if projection:
                    return {k: doc[k] for k in projection if k in doc}
                return dict(doc)
        return None

    def find(self, query: dict[str, Any]) -> _FakeCursor:
        docs = [
            dict(d) for d in self.docs if all(d.get(k) == v for k, v in query.items())
        ]
        return _FakeCursor(docs)

    async def delete_one(self, query: dict[str, Any]) -> _FakeDeleteResult:
        for i, doc in enumerate(self.docs):
            if all(doc.get(k) == v for k, v in query.items()):
                del self.docs[i]
                return _FakeDeleteResult(1)
        return _FakeDeleteResult(0)

    async def delete_many(self, query: dict[str, Any]) -> _FakeDeleteResult:
        before = len(self.docs)
        self.docs = [
            d for d in self.docs if not all(d.get(k) == v for k, v in query.items())
        ]
        return _FakeDeleteResult(before - len(self.docs))


class _FakeMongoDb:
    def __init__(self) -> None:
        self.collections: dict[str, _FakeCollection] = {}

    def __getitem__(self, name: str) -> _FakeCollection:
        return self.collections.setdefault(name, _FakeCollection())


class _FakeMongoProvider:
    def __init__(self) -> None:
        self.db = _FakeMongoDb()


def _store(ttl: int | None = None, prefix: str = "user:") -> tuple[RedisUserStore, _FakeRedis]:
    redis = _FakeRedis()
    return RedisUserStore(_FakeDbProvider(redis), prefix=prefix, ttl=ttl), redis


def _mongo_store(
    collection: str = "oauth_identities",
) -> tuple[MongoDBOAuthIdentityStore, _FakeMongoProvider]:
    provider = _FakeMongoProvider()
    return (
        MongoDBOAuthIdentityStore(provider, collection_name=collection),
        provider,
    )


# --------------------------------------------------------------------------
# RedisUserStore
# --------------------------------------------------------------------------


async def test_redis_store_create_get_roundtrip() -> None:
    store, redis = _store()
    user = await store.create_user(
        "Alice", "alice@x.com", "hashed-1", roles=["admin"], permissions=["a:read"]
    )
    assert user.email == "alice@x.com"
    assert user.roles == ["admin"]
    assert user.permissions == ["a:read"]

    key = f"user:{user.user_id}"
    assert key in redis.hashes
    # credential fields live in the same hash but never surface via get_user_by_id
    assert redis.hashes[key].get(b"hashed_password") == b"hashed-1"

    got = await store.get_user_by_id(user.user_id)
    assert got is not None
    assert got.user_id == user.user_id
    assert got.name == "Alice"
    assert got.roles == ["admin"]
    # no credential attribute leaks into the user projection
    assert not hasattr(got, "hashed_password") or not getattr(got, "hashed_password", None)

    assert await store.get_user_by_id("missing") is None


async def test_redis_store_prefix_custom() -> None:
    store, redis = _store(prefix="cache:u-")
    user = await store.create_user("B", "b@x.com", None)
    assert f"cache:u-{user.user_id}" in redis.hashes


async def test_redis_store_ttl_applied() -> None:
    store, redis = _store(ttl=60)
    user = await store.create_user("C", "c@x.com", None)
    key = f"user:{user.user_id}"
    assert redis.ttls.get(key) == 60

    user.name = "C2"
    await store.update_user(user)
    assert redis.ttls.get(key) == 60


async def test_redis_store_full_scan_ops_raise() -> None:
    store, _ = _store()
    with pytest.raises(NotImplementedError, match="email lookups"):
        await store.get_user_by_email("a@x.com")
    with pytest.raises(NotImplementedError, match="list_users"):
        await store.list_users()
    with pytest.raises(NotImplementedError, match="count_users"):
        await store.count_users()


async def test_redis_store_credentials_roundtrip() -> None:
    store, redis = _store()
    user = await store.create_user("D", "d@x.com", "h1", previous_passwords_note=None)

    creds = await store.get_credentials(user.user_id)
    assert creds is not None
    assert creds.hashed_password == "h1"
    assert creds.previous_hashes == []

    assert await store.get_credentials("nope") is None

    updated = UserCredentials(user_id=user.user_id, hashed_password="h2", previous_hashes=["h1"])
    await store.update_credentials(updated)
    got = await store.get_credentials(user.user_id)
    assert got is not None
    assert got.hashed_password == "h2"
    assert got.previous_hashes == ["h1"]


async def test_redis_store_credentials_none_password_omitted() -> None:
    store, redis = _store()
    user = await store.create_user("E", "e@x.com", "h1")
    # updating with hashed_password=None must NOT wipe the stored hash
    await store.update_credentials(UserCredentials(user_id=user.user_id))
    got = await store.get_credentials(user.user_id)
    assert got is not None
    assert got.hashed_password == "h1"


async def test_redis_store_delete_user() -> None:
    store, redis = _store()
    user = await store.create_user("F", "f@x.com", None)
    key = f"user:{user.user_id}"
    assert key in redis.hashes
    await store.delete_user(user.user_id)
    assert key not in redis.hashes
    assert "delete" in redis.calls


async def test_redis_store_datetime_parsing() -> None:
    store, _ = _store()
    user = await store.create_user("G", "g@x.com", None)
    user.created_at = datetime.now(UTC)
    user.last_login_at = datetime.fromtimestamp(1700000000)
    await store.update_user(user)

    got = await store.get_user_by_id(user.user_id)
    assert got is not None
    assert got.created_at is not None and abs(
        got.created_at.utcoffset().total_seconds() - 0
    ) == 0
    # naive timestamp (fromisoformat of a naive iso string) preserved
    assert got.last_login_at == datetime.fromtimestamp(1700000000)
    assert got.login_count == 0


async def test_redis_store_name_falls_back_to_username() -> None:
    store, redis = _store()
    user = await store.create_user("H", "h@x.com", None)
    key = f"user:{user.user_id}"
    # simulate an entry written with `username` and no `name` field
    del redis.hashes[key][b"name"]
    redis.hashes[key][b"username"] = b"h_user"
    got = await store.get_user_by_id(user.user_id)
    assert got is not None
    # _user_from_data: name field absent -> falls back to username
    assert got.name == "h_user"


# --------------------------------------------------------------------------
# MongoDBOAuthIdentityStore
# --------------------------------------------------------------------------


async def test_mongo_identity_create_and_get() -> None:
    store, provider = _mongo_store()
    identity = await store.create_oauth_identity("u1", "google", "g-123")
    assert identity.user_id == "u1"
    assert identity.provider == "google"
    assert identity.provider_user_id == "g-123"
    assert identity.created_at is not None

    coll = provider.db["oauth_identities"]
    assert len(coll.docs) == 1
    # indexes were created exactly once
    assert len(coll.indexes) == 2
    assert coll.indexes[1][1].get("unique") is True

    got = await store.get_oauth_identity("google", "g-123")
    assert got is not None
    assert got.user_id == "u1"

    assert await store.get_oauth_identity("google", "nope") is None


async def test_mongo_identity_indexes_created_once() -> None:
    store, provider = _mongo_store()
    await store.create_oauth_identity("u1", "google", "g-1")
    await store.get_oauth_identity("google", "g-1")
    await store.get_oauth_identities_for_user("u1")
    coll = provider.db["oauth_identities"]
    assert len(coll.indexes) == 2  # not re-created per call


async def test_mongo_identity_list_for_user() -> None:
    store, _ = _mongo_store()
    await store.create_oauth_identity("u1", "google", "g-1")
    await store.create_oauth_identity("u1", "github", "gh-1")
    await store.create_oauth_identity("u2", "google", "g-2")

    ids = await store.get_oauth_identities_for_user("u1")
    assert {i.provider for i in ids} == {"google", "github"}

    assert await store.get_oauth_identities_for_user("nobody") == []


async def test_mongo_identity_delete_one() -> None:
    store, _ = _mongo_store()
    await store.create_oauth_identity("u1", "google", "g-1")
    assert await store.delete_oauth_identity("google", "g-1") is True
    assert await store.delete_oauth_identity("google", "g-1") is False
    # other identities untouched
    await store.create_oauth_identity("u1", "github", "gh-1")
    assert await store.get_oauth_identity("github", "gh-1") is not None


async def test_mongo_identity_delete_for_user() -> None:
    store, _ = _mongo_store()
    await store.create_oauth_identity("u1", "google", "g-1")
    await store.create_oauth_identity("u1", "github", "gh-1")
    await store.create_oauth_identity("u2", "google", "g-2")

    assert await store.delete_oauth_identities_for_user("u1") == 2
    assert await store.get_oauth_identities_for_user("u1") == []
    remaining = await store.get_oauth_identities_for_user("u2")
    assert len(remaining) == 1

    assert await store.delete_oauth_identities_for_user("nobody") == 0


async def test_mongo_identity_user_lookup_projection() -> None:
    store, _ = _mongo_store()
    await store.create_oauth_identity("u9", "google", "g-9")
    assert await store.get_user_by_oauth_identity("google", "g-9") == "u9"
    assert await store.get_user_by_oauth_identity("google", "missing") is None


async def test_mongo_identity_resolve_user_id_paths() -> None:
    store, provider = _mongo_store()
    # OAuth external id path (non-UUID)
    await store.create_oauth_identity("local-1", "google", "ext-abc")
    assert await store.resolve_user_id("ext-abc", provider="google") == "local-1"
    assert await store.resolve_user_id("ext-abc", provider="github") is None

    # UUID path: checks the users collection
    uuid_id = "123e4567-e89b-12d3-a456-426614174000"
    provider.db["users"].docs.append({"_id": uuid_id, "email": "x@x.com"})
    assert await store.resolve_user_id(uuid_id) == uuid_id
    assert await store.resolve_user_id("99999999-9999-9999-9999-999999999999") is None

    # uppercase UUIDs are accepted (IGNORECASE)
    upper = uuid_id.upper()
    provider.db["users"].docs.append({"_id": upper})
    assert await store.resolve_user_id(upper) == upper


async def test_mongo_identity_sync_refused() -> None:
    store, _ = _mongo_store()
    assert store.resolve_user_id_sync("whatever", provider="google") is None


async def test_mongo_identity_custom_collection_name() -> None:
    store, provider = _mongo_store(collection="links")
    await store.create_oauth_identity("u1", "google", "g-1")
    assert "links" in provider.db.collections
    assert "oauth_identities" not in provider.db.collections
