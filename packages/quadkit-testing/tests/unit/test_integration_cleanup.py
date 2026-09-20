"""Integration cleanup helpers per service."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from quadkit.testing.integration import cleanup

from _integration_helpers import _AsyncCM

# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


async def test_cleanup_postgres_and_redis() -> None:
    conn = MagicMock()
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCM(conn))
    await cleanup.drop_postgres_schema(pool, "myschema")
    conn.execute.assert_awaited_once_with('DROP SCHEMA IF EXISTS "myschema" CASCADE')

    redis = MagicMock()
    redis.flushdb = AsyncMock()
    await cleanup.flush_redis_db(redis)
    redis.flushdb.assert_awaited_once()


async def test_cleanup_kafka_topic() -> None:
    class _Admin:
        instances: list[_Admin] = []

        def __init__(self, bootstrap_servers: str) -> None:
            self.bootstrap = bootstrap_servers
            self.started = False
            self.deleted: list[str] | None = None
            self.closed = False
            _Admin.instances.append(self)

        async def start(self) -> None:
            self.started = True

        async def delete_topics(self, topics: list[str]) -> None:
            self.deleted = topics

        async def close(self) -> None:
            self.closed = True

    mod = types.ModuleType("aiokafka.admin")
    mod.AIOKafkaAdminClient = _Admin  # type: ignore[attr-defined]
    sys.modules["aiokafka.admin"] = mod
    try:
        await cleanup.delete_kafka_topic("bk:9092", "topic-1")
    finally:
        del sys.modules["aiokafka.admin"]

    admin = _Admin.instances[-1]
    assert admin.bootstrap == "bk:9092"
    assert admin.started
    assert admin.closed
    assert admin.deleted == ["topic-1"]


async def test_cleanup_kafka_topic_missing_lib() -> None:
    sys.modules["aiokafka.admin"] = None
    try:
        await cleanup.delete_kafka_topic("bk:9092", "topic-1")  # silent no-op
    finally:
        del sys.modules["aiokafka.admin"]


def _async_minio_client() -> MagicMock:
    client = MagicMock()
    obj = SimpleNamespace(object_name="a.txt")
    client.list_objects = AsyncMock(return_value=[obj])
    client.remove_object = AsyncMock()
    client.remove_bucket = AsyncMock()
    return client


def _boto_minio_client() -> MagicMock:
    client = MagicMock()
    client.list_objects = MagicMock(return_value={"Contents": [{"Key": "b.txt"}]})
    client.remove_object = MagicMock()
    client.remove_bucket = MagicMock()
    return client


async def test_cleanup_minio_bucket_async_client() -> None:
    client = _async_minio_client()
    await cleanup.delete_minio_bucket(client, "bkt")
    client.list_objects.assert_awaited_once_with("bkt", recursive=True)
    client.remove_object.assert_awaited_once_with("bkt", "a.txt")
    client.remove_bucket.assert_awaited_once_with("bkt")


async def test_cleanup_minio_bucket_boto_style() -> None:
    client = _boto_minio_client()
    await cleanup.delete_minio_bucket(client, "bkt")
    client.list_objects.assert_called_once_with("bkt", recursive=True)
    client.remove_object.assert_called_once_with("bkt", "b.txt")
    client.remove_bucket.assert_called_once_with("bkt")


async def test_cleanup_minio_bucket_recursive_fallback_and_no_objects() -> None:
    class _NoRecursiveList:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def __call__(self, bucket: str) -> list:
            self.calls.append(bucket)
            return []

    list_fn = _NoRecursiveList()
    client = MagicMock()
    client.list_objects = list_fn
    client.remove_object = AsyncMock()
    client.remove_bucket = AsyncMock()
    await cleanup.delete_minio_bucket(client, "bkt")
    assert list_fn.calls == ["bkt"]  # TypeError on recursive= → retried plain
    client.remove_object.assert_not_awaited()
    client.remove_bucket.assert_awaited_once_with("bkt")

    # Client without object APIs → direct bucket removal.
    class _BareClient:
        def __init__(self) -> None:
            self.removed: str | None = None

        async def remove_bucket(self, name: str) -> None:
            self.removed = name

    bare = _BareClient()
    await cleanup.delete_minio_bucket(bare, "bkt")
    assert bare.removed == "bkt"


async def test_cleanup_mongodb_qdrant_neo4j() -> None:
    mongo = MagicMock()
    mongo.drop_database = AsyncMock()
    await cleanup.drop_mongodb_database(mongo, "db1")
    mongo.drop_database.assert_awaited_once_with("db1")

    qdrant = MagicMock()
    qdrant.delete_collection = AsyncMock()
    await cleanup.delete_qdrant_collection(qdrant, "col1")
    qdrant.delete_collection.assert_awaited_once_with("col1")

    neo4j = MagicMock()
    neo4j.run = AsyncMock()
    await cleanup.clear_neo4j_graph(neo4j)
    neo4j.run.assert_awaited_once_with("MATCH (n) DETACH DELETE n")
