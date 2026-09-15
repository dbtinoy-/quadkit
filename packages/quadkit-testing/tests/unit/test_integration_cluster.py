"""Tests for quadkit.testing.integration (config, markers, cleanup, probes, fixtures)."""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from _pytest.outcomes import Skipped
import pytest

from quadkit.testing.integration import cleanup, markers
from quadkit.testing.integration.config import IntegrationTestConfig
from quadkit.testing.integration.fixtures import (
    elasticsearch_client,
    elasticsearch_index,
    integration_config,
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

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _drive(gen: Any) -> Any:
    """Drive an async-generator fixture: yield value, then clean teardown."""
    value = await gen.__anext__()
    await gen.aclose()
    return value


def _cfg() -> IntegrationTestConfig:
    return IntegrationTestConfig()


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    cfg = IntegrationTestConfig()
    assert cfg.postgres_dsn.startswith("postgresql+asyncpg://")
    assert cfg.postgres_dsn_raw.startswith("postgresql://")
    assert cfg.redis_url == "redis://localhost:16379/15"
    assert cfg.kafka_bootstrap == "localhost:19092"
    assert cfg.minio_endpoint == "localhost:19000"
    assert cfg.minio_access_key == "minioadmin"
    assert cfg.minio_secret_key == "minioadmin"
    assert cfg.elasticsearch_url == "http://localhost:19200"
    assert cfg.mongodb_dsn == "mongodb://localhost:17017"
    assert cfg.qdrant_url == "http://localhost:16333"
    assert cfg.neo4j_url == "bolt://localhost:17687"
    assert cfg.neo4j_auth == "neo4j/testpassword"


def test_config_from_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("QK_TEST_REDIS_URL", "redis://host:6379/1")
    monkeypatch.setenv("QK_TEST_NEO4J_AUTH", "u/p")
    cfg = IntegrationTestConfig.from_env()
    assert cfg.redis_url == "redis://host:6379/1"
    assert cfg.neo4j_auth == "u/p"


def test_integration_config_fixture(monkeypatch: Any) -> None:
    monkeypatch.setenv("QK_TEST_KAFKA_BOOTSTRAP", "bk:9092")
    cfg = integration_config.__wrapped__()
    assert cfg.kafka_bootstrap == "bk:9092"
    assert isinstance(cfg, IntegrationTestConfig)


# ---------------------------------------------------------------------------
# markers
# ---------------------------------------------------------------------------


def test_markers_exist_and_apply() -> None:
    expected = {
        "requires_elasticsearch",
        "requires_kafka",
        "requires_meilisearch",
        "requires_minio",
        "requires_mongodb",
        "requires_neo4j",
        "requires_postgres",
        "requires_qdrant",
        "requires_rabbitmq",
        "requires_redis",
        "requires_smtp",
    }
    assert expected == set(markers.__all__)

    for name in markers.__all__:
        mark = getattr(markers, name)
        assert mark.name == name

        @mark
        def _fn() -> None:  # pragma: no cover - never executed
            pass

        assert any(m.name == name for m in _fn.pytestmark)

    class _Cls:
        pass

    markers.requires_postgres(_Cls)
    assert any(m.name == "requires_postgres" for m in _Cls.pytestmark)


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


# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------


class _TCP:
    def __init__(self) -> None:
        self.server: asyncio.AbstractServer | None = None
        self.port = 0

    async def start(self) -> int:
        async def _handler(reader: Any, writer: Any) -> None:
            writer.close()
            await writer.wait_closed()

        self.server = await asyncio.start_server(_handler, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


class _HTTP200:
    def __init__(self) -> None:
        self.server: asyncio.AbstractServer | None = None
        self.port = 0

    async def start(self) -> int:
        async def _handler(reader: Any, writer: Any) -> None:
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 2\r\n\r\n{}"
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        self.server = await asyncio.start_server(_handler, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


async def test_probes_tcp_services() -> None:
    tcp = _TCP()
    port = await tcp.start()
    try:
        assert await ServiceProbe.check_kafka(f"127.0.0.1:{port}") is True
        assert await ServiceProbe.check_minio(f"127.0.0.1:{port}") is True
        assert await ServiceProbe.check_smtp("127.0.0.1", port) is True
        assert await ServiceProbe.check_mongodb(f"mongodb://127.0.0.1:{port}") is True
        assert await ServiceProbe.check_qdrant(f"http://127.0.0.1:{port}") is True
        assert await ServiceProbe.check_neo4j(f"bolt://127.0.0.1:{port}") is True
    finally:
        await tcp.stop()


async def test_probes_tcp_services_unreachable() -> None:
    tcp = _TCP()
    await tcp.start()
    closed_port = tcp.port
    await tcp.stop()
    assert await ServiceProbe.check_kafka(f"127.0.0.1:{closed_port}") is False
    assert await ServiceProbe.check_minio(f"127.0.0.1:{closed_port}") is False
    assert await ServiceProbe.check_smtp("127.0.0.1", closed_port) is False
    assert (
        await ServiceProbe.check_mongodb(f"mongodb://127.0.0.1:{closed_port}") is False
    )
    assert await ServiceProbe.check_qdrant(f"http://127.0.0.1:{closed_port}") is False
    assert await ServiceProbe.check_neo4j(f"bolt://127.0.0.1:{closed_port}") is False


async def test_probes_http_services() -> None:
    http = _HTTP200()
    port = await http.start()
    try:
        base = f"http://127.0.0.1:{port}"
        assert await ServiceProbe.check_elasticsearch(base) is True
        assert await ServiceProbe.check_meilisearch(base) is True
    finally:
        await http.stop()


async def test_probes_http_services_unreachable() -> None:
    http = _HTTP200()
    await http.start()
    closed_port = http.port
    await http.stop()
    assert (
        await ServiceProbe.check_elasticsearch(f"http://127.0.0.1:{closed_port}")
        is False
    )
    assert (
        await ServiceProbe.check_meilisearch(f"http://127.0.0.1:{closed_port}") is False
    )


async def test_probe_redis(monkeypatch: Any) -> None:
    pytest.importorskip("redis.asyncio", reason="redis.asyncio driver not installed")
    import redis.asyncio as real_redis

    # Unreachable real server → False (must precede the from_url patch).
    tcp = _TCP()
    await tcp.start()
    closed_port = tcp.port
    await tcp.stop()
    assert await ServiceProbe.check_redis(f"redis://127.0.0.1:{closed_port}") is False

    mock_client = MagicMock()
    mock_client.ping = AsyncMock()
    mock_client.close = AsyncMock()
    monkeypatch.setattr(real_redis, "from_url", lambda _url, **_kwargs: mock_client)
    assert await ServiceProbe.check_redis("redis://fake:6379") is True
    mock_client.ping.assert_awaited_once()
    mock_client.close.assert_awaited_once()


async def test_probe_postgres(monkeypatch: Any) -> None:
    pytest.importorskip("asyncpg", reason="asyncpg driver not installed")
    import asyncpg

    # Unreachable real server → False (must precede the connect patch).
    tcp = _TCP()
    await tcp.start()
    closed_port = tcp.port
    await tcp.stop()
    assert (
        await ServiceProbe.check_postgres(f"postgresql://127.0.0.1:{closed_port}/db")
        is False
    )

    conn = MagicMock()
    conn.close = AsyncMock()
    monkeypatch.setattr(asyncpg, "connect", lambda _dsn, **_kwargs: _AC(conn))
    assert await ServiceProbe.check_postgres("postgresql://fake/db") is True
    conn.close.assert_awaited_once()


async def test_probe_rabbitmq() -> None:
    conn = MagicMock()
    conn.close = AsyncMock()
    mod = types.ModuleType("aio_pika")

    async def connect_robust(url: str, timeout: float = 0) -> Any:
        return conn

    mod.connect_robust = connect_robust  # type: ignore[attr-defined]
    sys.modules["aio_pika"] = mod
    try:
        assert await ServiceProbe.check_rabbitmq("amqp://127.0.0.1:5672/") is True
        conn.close.assert_awaited_once()
    finally:
        sys.modules.pop("aio_pika", None)


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
    pytest.importorskip("motor.motor_asyncio", reason="motor.motor_asyncio driver not installed")
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


class _AsyncCM:
    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _AC:
    """One-shot awaitable returning *value*."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def __await__(self) -> Any:
        async def _get() -> Any:
            return self._value

        return _get().__await__()
