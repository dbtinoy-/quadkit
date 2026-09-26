"""Tests for the HealthCheckProvider ASGI middleware endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.monitor.middleware.health import HealthCheckProvider
from quadkit.serialization import loads


def _scope(
    path: str = "/health",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict:
    scope: dict = {"type": "http", "method": "GET", "path": path}
    if headers is not None:
        scope["headers"] = headers
    return scope


async def _run(provider: HealthCheckProvider, scope: dict) -> list:
    sent: list = []

    async def send(message: dict) -> None:
        sent.append(message)

    await provider(scope, AsyncMock(), send)
    return sent


@pytest.mark.asyncio
async def test_health_check_provider_open_by_default() -> None:
    sent = await _run(HealthCheckProvider(), _scope())
    assert sent[0]["status"] == 200
    assert loads(sent[1]["body"].decode("utf-8"))["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_provider_rejects_missing_token() -> None:
    sent = await _run(HealthCheckProvider(auth_token="s3cret"), _scope())
    assert sent[0]["status"] == 401
    headers = dict(sent[0]["headers"])
    assert headers[b"www-authenticate"] == b"Bearer"
    assert sent[1]["body"] == b"Unauthorized"


@pytest.mark.asyncio
async def test_health_check_provider_rejects_wrong_token() -> None:
    provider = HealthCheckProvider(auth_token="s3cret")
    sent = await _run(provider, _scope(headers=[(b"authorization", b"Bearer wrong")]))
    assert sent[0]["status"] == 401


@pytest.mark.asyncio
async def test_health_check_provider_accepts_matching_token() -> None:
    provider = HealthCheckProvider(auth_token="s3cret")
    sent = await _run(provider, _scope(headers=[(b"authorization", b"Bearer s3cret")]))
    assert sent[0]["status"] == 200
    assert loads(sent[1]["body"].decode("utf-8"))["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_provider_other_paths_unaffected_by_token() -> None:
    sent = await _run(HealthCheckProvider(auth_token="s3cret"), _scope(path="/other"))
    assert sent[0]["status"] == 404
