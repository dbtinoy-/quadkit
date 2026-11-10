"""Unit tests for ResilientHTTPClient in quadkit.ai.llm.http.client."""

from unittest.mock import AsyncMock

import pytest

from quadkit.ai.llm.http.client import ResilientHTTPClient


def test_resolve_url_and_merge_headers() -> None:
    client = ResilientHTTPClient(base_url="https://api.test")

    assert client._build_url("") == "https://api.test"
    assert client._build_url("/v1") == "https://api.test/v1"
    assert client._build_url("v1") == "https://api.test/v1"
    assert client._build_url("https://other/ok") == "https://other/ok"

    client.headers = {"A": "1"}
    merged = client._merge_headers({"B": "2"})
    assert merged == {"A": "1", "B": "2"}


def test_base_url_trailing_slash_stripped() -> None:
    client = ResilientHTTPClient(base_url="https://api.test/v1/")
    assert client.base_url == "https://api.test/v1"
    assert client._build_url("/chat") == "https://api.test/v1/chat"


@pytest.mark.asyncio
async def test_close_is_idempotent() -> None:
    """close() on an uninitialised client is a no-op."""
    client = ResilientHTTPClient(base_url="https://api.test")
    await client.close()  # should not raise
    await client.close()  # second call also safe


@pytest.mark.asyncio
async def test_context_manager_closes_on_exit() -> None:
    """Using ResilientHTTPClient as async context manager calls close()."""
    client = ResilientHTTPClient(base_url="https://api.test")
    close_mock = AsyncMock()
    client.close = close_mock  # type: ignore[method-assign]

    async with client:
        pass

    close_mock.assert_awaited_once()

