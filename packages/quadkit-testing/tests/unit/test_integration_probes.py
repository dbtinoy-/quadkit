"""Integration service probes."""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from quadkit.testing.integration.probes import ServiceProbe

from _integration_helpers import _AC, _HTTP200, _TCP

# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------


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
