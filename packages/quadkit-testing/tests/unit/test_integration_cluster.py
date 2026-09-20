"""Tests for quadkit.testing.integration (config, markers, cleanup, probes, fixtures)."""

from __future__ import annotations

from typing import Any

from quadkit.testing.integration import markers
from quadkit.testing.integration.config import IntegrationTestConfig
from quadkit.testing.integration.fixtures import (
    integration_config,
)

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
