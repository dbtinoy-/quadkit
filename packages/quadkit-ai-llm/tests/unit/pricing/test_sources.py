"""Tests for APIPricingSource error containment."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.ai.llm.pricing.sources import APIPricingSource
from quadkit.contracts.web.http_models import HttpStatusError


class _FakeResponse:
    def raise_for_status(self) -> None:
        raise HttpStatusError("down", status=500, response=MagicMock())


class _RaisingClient:
    async def __aenter__(self) -> "_RaisingClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str) -> _FakeResponse:
        return _FakeResponse()


class TestAPIPricingSourceContainment:
    """API pricing source must degrade on HTTP errors."""

    @pytest.mark.asyncio
    async def test_http_status_error_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "quadkit.ai.llm.pricing.sources.ResilientHTTPClient",
            lambda *a, **k: _RaisingClient(),
        )

        source = APIPricingSource("https://example.com/prices.json")
        pricing = await source.get_all_pricing()

        assert pricing == {}
        assert source._cache is None
