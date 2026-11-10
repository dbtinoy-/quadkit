"""SSRF behavior tests for WebFetchConnector (D4)."""

from __future__ import annotations

import ipaddress
from types import TracebackType
from typing import Any, Self

import pytest

from quadkit.ai.mcp.connectors.web_fetch import WebFetchConnector
from quadkit.ai.mcp.types import MCPToolResult


class _FakeResponse:
    def __init__(
        self,
        status: int,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._text = text
        self.headers = headers or {}

    async def read(self) -> bytes:
        return self._text.encode()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


class _FakeSession:
    def __init__(self, responses: dict[str, _FakeResponse]) -> None:
        self._responses = responses

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:  # noqa: ARG002
        return self._responses[url]


@pytest.fixture(autouse=True)
def _fake_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve every hostname to a public IP so no live DNS runs."""
    from quadkit.contracts.security import url_safety as contracts_url_safety

    monkeypatch.setattr(
        contracts_url_safety,
        "resolve_hostname",
        lambda _: [ipaddress.ip_address("93.184.216.34")],
    )


def _monkeypatch_aiohttp(
    monkeypatch: pytest.MonkeyPatch, responses: dict[str, _FakeResponse]
) -> None:
    import sys

    monkeypatch.setitem(
        sys.modules,
        "aiohttp",
        type(
            "aiohttp",
            (),
            {
                "ClientSession": lambda **_kw: _FakeSession(responses),
                "ClientTimeout": lambda **_kw: None,
                "ClientError": ConnectionError,
            },
        ),
    )


@pytest.mark.asyncio
async def test_web_fetch_blocks_private_literal() -> None:
    result = await WebFetchConnector().call_tool(
        "web_fetch", {"url": "http://169.254.169.254/latest/meta-data/"}
    )
    assert result.is_error is True


@pytest.mark.asyncio
async def test_web_fetch_allows_public_and_returns_text(monkeypatch) -> None:
    _monkeypatch_aiohttp(
        monkeypatch,
        {
            "https://example.com/": _FakeResponse(status=200, text="Hello public"),
        },
    )
    result: MCPToolResult = await WebFetchConnector().call_tool(
        "web_fetch", {"url": "https://example.com/"}
    )
    assert result.is_error is False
    assert "Hello public" in result.content[0]["text"]


@pytest.mark.asyncio
async def test_web_fetch_blocks_redirect_to_private(monkeypatch) -> None:
    _monkeypatch_aiohttp(
        monkeypatch,
        {
            "https://public.example/": _FakeResponse(
                status=302,
                headers={"Location": "http://127.0.0.1/secret"},
            ),
        },
    )
    result = await WebFetchConnector().call_tool(
        "web_fetch", {"url": "https://public.example/"}
    )
    assert result.is_error is True
