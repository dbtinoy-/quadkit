"""Integration fixtures: skip paths, library-missing paths, connected paths."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from _pytest.outcomes import Skipped
from quadkit.testing.integration.config import IntegrationTestConfig
from quadkit.testing.integration.fixtures import (
    elasticsearch_client,
    elasticsearch_index,
    kafka_producer,
    minio_bucket,
    minio_client,
    mongodb_client,
    mongodb_database,
    neo4j_driver,
    neo4j_session,
    postgres_conn,
    postgres_pool,
    qdrant_client,
    redis_client,
)
from quadkit.testing.integration.probes import ServiceProbe


def _cfg() -> IntegrationTestConfig:
    return IntegrationTestConfig()


async def _drive(gen: Any) -> Any:
    """Drive an async-generator fixture: yield value, then clean teardown."""
    value = await gen.__anext__()
    await gen.aclose()
    return value


from _integration_helpers import _AC, _AsyncCM, _HTTP200

# ---------------------------------------------------------------------------
# integration fixtures — skip paths (service unavailable)
# ---------------------------------------------------------------------------


async def _expect_skip(gen_factory: Any) -> None:
    with pytest.raises(Skipped):
        await gen_factory().__anext__()


async def test_fixtures_skip_when_unavailable(monkeypatch: Any) -> None:
    for probe_name in (
        "check_postgres",
        "check_redis",
        "check_kafka",
        "check_elasticsearch",
        "check_mongodb",
        "check_minio",
        "check_qdrant",
        "check_neo4j",
    ):
        monkeypatch.setattr(ServiceProbe, probe_name, AsyncMock(return_value=False))

    cfg = _cfg()
    await _expect_skip(lambda: postgres_pool.__wrapped__(cfg))
    await _expect_skip(lambda: redis_client.__wrapped__(cfg))
    await _expect_skip(lambda: kafka_producer.__wrapped__(cfg))
    await _expect_skip(lambda: elasticsearch_client.__wrapped__(cfg))
    await _expect_skip(lambda: mongodb_client.__wrapped__(cfg))
    await _expect_skip(lambda: minio_client.__wrapped__(cfg))
    await _expect_skip(lambda: qdrant_client.__wrapped__(cfg))
    await _expect_skip(lambda: neo4j_driver.__wrapped__(cfg))


# ---------------------------------------------------------------------------
# integration fixtures — library-missing skip paths
# ---------------------------------------------------------------------------


async def test_fixtures_skip_when_library_missing(monkeypatch: Any) -> None:
    cfg = _cfg()

    for probe_name in (
        "check_postgres",
        "check_redis",
        "check_kafka",
        "check_elasticsearch",
        "check_mongodb",
        "check_qdrant",
        "check_neo4j",
    ):
        monkeypatch.setattr(ServiceProbe, probe_name, AsyncMock(return_value=True))

    # Force ImportError for ALL probed drivers, not just the installed ones:
    # in a shared-process suite other packages' conftests may have injected
    # driver stubs into sys.modules (e.g. nosql stubs motor/pymongo,
    # vector stubs qdrant_client), so "not installed" is not a safe
    # process-global assumption.
    monkeypatch.setitem(sys.modules, "asyncpg", None)
    monkeypatch.setitem(sys.modules, "redis.asyncio", None)
    monkeypatch.setitem(sys.modules, "motor.motor_asyncio", None)
    monkeypatch.setitem(sys.modules, "aiokafka", None)
    monkeypatch.setitem(sys.modules, "elasticsearch", None)
    monkeypatch.setitem(sys.modules, "qdrant_client", None)
    monkeypatch.setitem(sys.modules, "neo4j", None)
    await _expect_skip(lambda: postgres_pool.__wrapped__(cfg))
    await _expect_skip(lambda: redis_client.__wrapped__(cfg))
    await _expect_skip(lambda: kafka_producer.__wrapped__(cfg))
    await _expect_skip(lambda: elasticsearch_client.__wrapped__(cfg))
    await _expect_skip(lambda: mongodb_client.__wrapped__(cfg))
    await _expect_skip(lambda: qdrant_client.__wrapped__(cfg))
    await _expect_skip(lambda: neo4j_driver.__wrapped__(cfg))


# ---------------------------------------------------------------------------
# integration fixtures — connected paths
# ---------------------------------------------------------------------------


async def test_postgres_pool_and_conn(monkeypatch: Any) -> None:
    pytest.importorskip("asyncpg", reason="asyncpg driver not installed")
    import asyncpg

    pool = MagicMock()
    pool.close = AsyncMock()
    conn = MagicMock()
    monkeypatch.setattr(asyncpg, "create_pool", lambda _dsn, **_kwargs: _AC(pool))
    monkeypatch.setattr(ServiceProbe, "check_postgres", AsyncMock(return_value=True))

    value = await _drive(postgres_pool.__wrapped__(_cfg()))
    assert value is pool
    pool.close.assert_awaited_once()

    fake_pool = MagicMock()
    fake_pool.acquire = MagicMock(return_value=_AsyncCM(conn))
    value = await _drive(postgres_conn.__wrapped__(fake_pool))
    assert value is conn


async def test_redis_client_fixture(monkeypatch: Any) -> None:
    pytest.importorskip("redis.asyncio", reason="redis.asyncio driver not installed")
    import redis.asyncio as real_redis

    client = MagicMock()
    client.close = AsyncMock()
    monkeypatch.setattr(real_redis, "from_url", lambda _url, **_kwargs: client)
    monkeypatch.setattr(ServiceProbe, "check_redis", AsyncMock(return_value=True))

    value = await _drive(redis_client.__wrapped__(_cfg()))
    assert value is client
    client.close.assert_awaited_once()


async def test_kafka_producer_fixture(monkeypatch: Any) -> None:
    producer = MagicMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    mod = types.ModuleType("aiokafka")

    def _producer(**kwargs: Any) -> Any:
        assert kwargs == {"bootstrap_servers": "localhost:19092"}
        return producer

    mod.AIOKafkaProducer = _producer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiokafka", mod)
    monkeypatch.setattr(ServiceProbe, "check_kafka", AsyncMock(return_value=True))

    value = await _drive(kafka_producer.__wrapped__(_cfg()))
    assert value is producer
    producer.start.assert_awaited_once()
    producer.stop.assert_awaited_once()


async def test_elasticsearch_client_fixture(
    monkeypatch: Any,
) -> None:
    http = _HTTP200()
    await http.start()
    try:
        client = MagicMock()
        client.close = AsyncMock()
        mod = types.ModuleType("elasticsearch")
        mod.AsyncElasticsearch = (  # type: ignore[attr-defined]
            lambda hosts=None: client  # noqa: ARG005
        )
        monkeypatch.setitem(sys.modules, "elasticsearch", mod)
        monkeypatch.setattr(
            ServiceProbe, "check_elasticsearch", AsyncMock(return_value=True)
        )

        value = await _drive(elasticsearch_client.__wrapped__(_cfg()))
        assert value is client
        client.close.assert_awaited_once()
    finally:
        await http.stop()


def test_elasticsearch_index_and_minio_bucket() -> None:
    name = elasticsearch_index.__wrapped__()
    assert name.startswith("quadkit_test_")
    assert len(name) == len("quadkit_test_") + 12

    bucket = minio_bucket.__wrapped__()
    assert bucket.startswith("quadkit-test-")
    assert elasticsearch_index.__wrapped__() != name


async def test_mongodb_client_and_database(monkeypatch: Any) -> None:
    pytest.importorskip(
        "motor.motor_asyncio", reason="motor.motor_asyncio driver not installed"
    )
    import inspect

    from motor.motor_asyncio import AsyncIOMotorClient

    # In a shared-process suite another package's conftest may have injected
    # a motor *stub* (MagicMock) into sys.modules — importorskip cannot tell
    # the difference. Only run against the real driver.
    if not inspect.isclass(AsyncIOMotorClient):
        pytest.skip("motor driver is a test stub in this process, not the real driver")

    monkeypatch.setattr(ServiceProbe, "check_mongodb", AsyncMock(return_value=True))
    client = AsyncIOMotorClient(_cfg().mongodb_dsn)
    try:
        # Fixture builds its own client; verify behaviour with the real motor
        # client (lazy connect) by checking the fixture yields a motor client.
        value = await _drive(mongodb_client.__wrapped__(_cfg()))
        assert isinstance(value, AsyncIOMotorClient)

        class _DB:
            def __init__(self, name: str) -> None:
                self.name = name

        class _FakeMongoClient:
            def __init__(self) -> None:
                self.names: list[str] = []

            def __getitem__(self, name: str) -> _DB:
                self.names.append(name)
                return _DB(name)

        fake_client = _FakeMongoClient()
        db = mongodb_database.__wrapped__(fake_client)
        assert isinstance(db, _DB)
        assert len(fake_client.names) == 1
        assert fake_client.names[0].startswith("quadkit_test_")
    finally:
        client.close()


async def test_minio_client_fixture(monkeypatch: Any) -> None:
    monkeypatch.setattr(ServiceProbe, "check_minio", AsyncMock(return_value=True))
    value = await _drive(minio_client.__wrapped__(_cfg()))
    assert value is None  # placeholder — concrete packages provide their own


async def test_qdrant_client_fixture(monkeypatch: Any) -> None:
    client = MagicMock()
    client.close = AsyncMock()
    mod = types.ModuleType("qdrant_client")
    mod.AsyncQdrantClient = (  # type: ignore[attr-defined]
        lambda url=None: client  # noqa: ARG005
    )
    monkeypatch.setitem(sys.modules, "qdrant_client", mod)
    monkeypatch.setattr(ServiceProbe, "check_qdrant", AsyncMock(return_value=True))

    value = await _drive(qdrant_client.__wrapped__(_cfg()))
    assert value is client
    client.close.assert_awaited_once()


async def test_neo4j_driver_and_session(monkeypatch: Any) -> None:
    driver = MagicMock()
    driver.close = AsyncMock()
    captured: dict[str, Any] = {}

    def _fake_driver(url: str, auth: tuple[str, str] | None = None) -> Any:
        captured["url"] = url
        captured["auth"] = auth
        return driver

    mod = types.ModuleType("neo4j")
    mod.AsyncGraphDatabase = SimpleNamespace(  # type: ignore[attr-defined]
        driver=_fake_driver
    )
    monkeypatch.setitem(sys.modules, "neo4j", mod)
    monkeypatch.setattr(ServiceProbe, "check_neo4j", AsyncMock(return_value=True))

    value = await _drive(neo4j_driver.__wrapped__(_cfg()))
    assert value is driver
    assert captured["url"] == "bolt://localhost:17687"
    assert captured["auth"] == ("neo4j", "testpassword")
    driver.close.assert_awaited_once()

    session = object()

    class _FakeDriver:
        def session(self) -> Any:
            return _AsyncCM(session)

    value = await _drive(neo4j_session.__wrapped__(_FakeDriver()))
    assert value is session


# ---------------------------------------------------------------------------
# small async CM helpers
# ---------------------------------------------------------------------------
