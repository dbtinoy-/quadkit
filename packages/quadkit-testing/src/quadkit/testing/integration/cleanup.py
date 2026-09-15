from __future__ import annotations

from importlib import import_module
from inspect import isawaitable
from typing import Any, cast

"""Cleanup utilities for integration test teardown."""

__all__ = [
    "clear_neo4j_graph",
    "delete_kafka_topic",
    "delete_minio_bucket",
    "delete_qdrant_collection",
    "drop_mongodb_database",
    "drop_postgres_schema",
    "flush_redis_db",
]


async def drop_postgres_schema(pool: Any, schema_name: str) -> None:
    """Drop a PostgreSQL schema and all its objects.

    Args:
        pool: An asyncpg connection pool.
        schema_name: Schema name to drop.
    """
    async with pool.acquire() as conn:
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')


async def flush_redis_db(client: Any) -> None:
    """Flush all keys from the current Redis database.

    Args:
        client: An async Redis client (redis.asyncio.Redis).
    """
    await client.flushdb()


async def delete_kafka_topic(bootstrap: str, topic: str) -> None:
    """Delete a Kafka topic.

    Args:
        bootstrap: Kafka bootstrap server.
        topic: Topic name to delete.
    """
    try:
        aiokafka_admin = cast("Any", import_module("aiokafka.admin"))
        admin = aiokafka_admin.AIOKafkaAdminClient(bootstrap_servers=bootstrap)
        await admin.start()
        try:
            await admin.delete_topics([topic])
        finally:
            await admin.close()
    except ImportError:
        pass


async def delete_minio_bucket(client: Any, bucket_name: str) -> None:
    """Delete a MinIO bucket and all its objects.

    Objects are drained first (best effort) so the bucket removal is not
    blocked by leftover contents.  Supports ``miniopy_async.Minio``
    (async) and boto3-style (sync) S3 clients.

    Args:
        client: A miniopy_async or boto3 client.
        bucket_name: Bucket name to purge and delete.
    """
    list_fn = getattr(client, "list_objects", None)
    remove_obj_fn = getattr(client, "remove_object", None)
    if list_fn is not None and remove_obj_fn is not None:
        try:
            listing = list_fn(bucket_name, recursive=True)
        except TypeError:
            listing = list_fn(bucket_name)
        if isawaitable(listing):
            listing = await listing
        if isinstance(listing, dict):  # boto3-style response payload
            objects: list[Any] = listing.get("Contents", [])
        else:
            objects = list(listing)
        for obj in objects:
            name = (
                getattr(obj, "object_name", None)
                or getattr(obj, "key", None)
                or (obj.get("Key") if isinstance(obj, dict) else None)
                or obj
            )
            removed = remove_obj_fn(bucket_name, name)
            if isawaitable(removed):
                await removed

    removed_bucket = client.remove_bucket(bucket_name)
    if isawaitable(removed_bucket):
        await removed_bucket


async def drop_mongodb_database(client: Any, db_name: str) -> None:
    """Drop a MongoDB database.

    Args:
        client: A motor AsyncIOMotorClient.
        db_name: Database name to drop.
    """
    await client.drop_database(db_name)


async def delete_qdrant_collection(client: Any, collection_name: str) -> None:
    """Delete a Qdrant collection.

    Args:
        client: A qdrant_client.AsyncQdrantClient.
        collection_name: Collection to delete.
    """
    await client.delete_collection(collection_name)


async def clear_neo4j_graph(session: Any) -> None:
    """Delete all nodes and relationships in a Neo4j database.

    Args:
        session: A neo4j.AsyncSession.
    """
    await session.run("MATCH (n) DETACH DELETE n")
