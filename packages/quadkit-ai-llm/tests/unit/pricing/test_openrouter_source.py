"""Tests for OpenRouterPricingSource."""

from __future__ import annotations

from unittest.mock import MagicMock

import aiohttp
import pytest

from quadkit.ai.llm.pricing.sources import OpenRouterPricingSource
from quadkit.contracts.web.http_models import HttpStatusError


class FakeResponse:
    """Minimal HTTP response double."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    @property
    def json(self) -> dict:
        return self._payload


class FakeClient:
    """ResilientHTTPClient double returning a fixed payload."""

    def __init__(self, payload: dict, exc: Exception | None = None) -> None:
        self._payload = payload
        self._exc = exc

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str) -> FakeResponse:
        if self._exc is not None:
            raise self._exc
        return FakeResponse(self._payload)


class TestOpenRouterPricingSource:
    """Tests for OpenRouterPricingSource."""

    def test_to_float_converts_per_token_strings(self) -> None:
        source = OpenRouterPricingSource()
        assert source._to_float("0.0000025") == pytest.approx(2.5e-6)
        assert source._to_float("10") == pytest.approx(10.0)
        assert source._to_float("abc") is None
        assert source._to_float(None) is None

    @pytest.mark.asyncio
    async def test_fetch_maps_per_token_to_per_1m(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "data": [
                {
                    "id": "openai/gpt-4o",
                    "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
                },
                {
                    "id": "openai/gpt-4o-mini",
                    "pricing": {"prompt": "0.00000015", "completion": "0.0000006"},
                },
            ]
        }
        monkeypatch.setattr(
            "quadkit.ai.llm.pricing.sources.ResilientHTTPClient",
            lambda *a, **k: FakeClient(payload),
        )

        source = OpenRouterPricingSource()
        pricing = await source._fetch_pricing()

        gpt4o = pricing["openai/gpt-4o"]
        assert gpt4o.prompt_per_1m == pytest.approx(2.5)
        assert gpt4o.completion_per_1m == pytest.approx(10.0)
        assert gpt4o.provider == "openai"
        assert gpt4o.source == "api:openrouter"

    @pytest.mark.asyncio
    async def test_bare_name_alias_indexed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "data": [
                {
                    "id": "openai/gpt-4o",
                    "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
                }
            ]
        }
        monkeypatch.setattr(
            "quadkit.ai.llm.pricing.sources.ResilientHTTPClient",
            lambda *a, **k: FakeClient(payload),
        )

        source = OpenRouterPricingSource()
        pricing = await source._fetch_pricing()

        # Bare alias points to the full slug entry.
        assert "gpt-4o" in pricing
        assert pricing["gpt-4o"].model == "openai/gpt-4o"

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "quadkit.ai.llm.pricing.sources.ResilientHTTPClient",
            lambda *a, **k: FakeClient({}, exc=OSError("network down")),
        )

        source = OpenRouterPricingSource()
        pricing = await source.get_pricing("gpt-4o")

        assert pricing is None
        assert source._cache is None

    @pytest.mark.asyncio
    async def test_get_all_pricing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "data": [
                {
                    "id": "openai/gpt-4o",
                    "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
                }
            ]
        }
        monkeypatch.setattr(
            "quadkit.ai.llm.pricing.sources.ResilientHTTPClient",
            lambda *a, **k: FakeClient(payload),
        )

        source = OpenRouterPricingSource()
        all_pricing = await source.get_all_pricing()

        assert "openai/gpt-4o" in all_pricing
        assert "gpt-4o" in all_pricing


class TestHttpFailureContainment:
    """HTTP status errors and aiohttp failures must degrade, not crash."""

    @pytest.mark.asyncio
    async def test_http_status_error_contained(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "quadkit.ai.llm.pricing.sources.ResilientHTTPClient",
            lambda *a, **k: FakeClient(
                {}, exc=HttpStatusError("boom", status=503, response=MagicMock())
            ),
        )

        source = OpenRouterPricingSource()
        pricing = await source._fetch_pricing()

        assert pricing == {}

    @pytest.mark.asyncio
    async def test_aiohttp_client_error_contained(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "quadkit.ai.llm.pricing.sources.ResilientHTTPClient",
            lambda *a, **k: FakeClient({}, exc=aiohttp.ServerDisconnectedError()),
        )

        source = OpenRouterPricingSource()
        pricing = await source._fetch_pricing()

        assert pricing == {}
