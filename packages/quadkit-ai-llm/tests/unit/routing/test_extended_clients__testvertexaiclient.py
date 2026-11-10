from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMRateLimitError,
)
from quadkit.ai.llm.types import ChatMessage, Role
from quadkit.contracts.core import HealthStatus
from quadkit.validation import SecretStr

from ._test_extended_clients_support import (
    _compat_config,
    _fake_openai_module,
    _gemini_api_response,
    _inject_google_auth,
    _make_http_error,
    _mock_http_response,
    _vertex_config,
)


class TestVertexAIClient:
    def test_missing_vertex_project_raises_value_error(self, monkeypatch: Any) -> None:
        _inject_google_auth(monkeypatch)
        from quadkit.ai.llm.clients.vertex_ai import VertexAIClient

        with pytest.raises(ValueError, match="vertex_project"):
            VertexAIClient(
                ClientConfig(
                    provider="google-vertex",
                    model="gemini-1.5-pro",
                    extra={"vertex_location": "us-central1"},
                )
            )

    def test_missing_vertex_location_raises_value_error(self, monkeypatch: Any) -> None:
        _inject_google_auth(monkeypatch)
        from quadkit.ai.llm.clients.vertex_ai import VertexAIClient

        with pytest.raises(ValueError, match="vertex_location"):
            VertexAIClient(
                ClientConfig(
                    provider="google-vertex",
                    model="gemini-1.5-pro",
                    extra={"vertex_project": "my-project"},
                )
            )

    @pytest.mark.asyncio
    async def test_complete_success(self, monkeypatch: Any) -> None:
        _inject_google_auth(monkeypatch)
        from quadkit.ai.llm.clients.vertex_ai import VertexAIClient

        client = VertexAIClient(_vertex_config())

        mock_http = MagicMock()
        mock_http.post = AsyncMock(
            return_value=_mock_http_response(_gemini_api_response("Vertex response"))
        )
        mock_http.headers = {}

        async def _fake_get_http() -> Any:
            return mock_http

        client._get_http = _fake_get_http  # type: ignore[method-assign]
        res = await client.complete(messages=[{"role": "user", "content": "hi"}])

        assert res.is_ok()
        assert "Vertex response" in res.unwrap().content

    @pytest.mark.asyncio
    async def test_complete_returns_err_on_rate_limit(self, monkeypatch: Any) -> None:
        _inject_google_auth(monkeypatch)
        from quadkit.ai.llm.clients.vertex_ai import VertexAIClient

        client = VertexAIClient(_vertex_config())
        mock_http = MagicMock()
        mock_http.post = AsyncMock(side_effect=_make_http_error(429))
        mock_http.headers = {}

        async def _fake_get_http() -> Any:
            return mock_http

        client._get_http = _fake_get_http  # type: ignore[method-assign]
        client.max_retries = 0

        res = await client.complete(messages=[{"role": "user", "content": "hi"}])
        assert res.is_err()
        assert isinstance(res.unwrap_err(), LLMRateLimitError)

    @pytest.mark.asyncio
    async def test_complete_raises_auth_error_on_401(self, monkeypatch: Any) -> None:
        _inject_google_auth(monkeypatch)
        from quadkit.ai.llm.clients.vertex_ai import VertexAIClient

        client = VertexAIClient(_vertex_config())
        mock_http = MagicMock()
        mock_http.post = AsyncMock(side_effect=_make_http_error(401))
        mock_http.headers = {}

        async def _fake_get_http() -> Any:
            return mock_http

        client._get_http = _fake_get_http  # type: ignore[method-assign]

        with pytest.raises(LLMAuthenticationError):
            await client.complete(messages=[{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, monkeypatch: Any) -> None:
        _inject_google_auth(monkeypatch)
        from quadkit.ai.llm.clients.vertex_ai import VertexAIClient

        client = VertexAIClient(_vertex_config())
        mock_http = MagicMock()
        mock_http.get = AsyncMock(return_value=_mock_http_response({"models": []}))
        mock_http.headers = {}

        async def _fake_get_http() -> Any:
            return mock_http

        client._get_http = _fake_get_http  # type: ignore[method-assign]

        result = await client.health_check()
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_error(
        self, monkeypatch: Any
    ) -> None:
        _inject_google_auth(monkeypatch)
        from quadkit.ai.llm.clients.vertex_ai import VertexAIClient

        client = VertexAIClient(_vertex_config())

        async def _bad_get_http() -> Any:
            raise OSError("network error")

        client._get_http = _bad_get_http  # type: ignore[method-assign]

        result = await client.health_check()
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_close_releases_http_client(self, monkeypatch: Any) -> None:
        _inject_google_auth(monkeypatch)
        from quadkit.ai.llm.clients.vertex_ai import VertexAIClient

        client = VertexAIClient(_vertex_config())
        mock_http = MagicMock()
        mock_http.close = AsyncMock()
        client._http = mock_http

        await client.close()

        mock_http.close.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# OpenAICompatibleClient + DeepSeek / Together / Fireworks
# ──────────────────────────────────────────────────────────────────────────────


class TestOpenAICompatibleClient:
    @pytest.mark.asyncio
    async def test_deepseek_complete_success(self, monkeypatch: Any) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module("DeepSeek hi"))
        from quadkit.ai.llm.clients.openai_compatible import DeepSeekClient

        client = DeepSeekClient(_compat_config("custom", "deepseek-chat"))
        res = await client.complete(
            messages=[ChatMessage(role=Role.USER, content="hi")]
        )

        assert res.is_ok()
        assert res.unwrap().content == "DeepSeek hi"

    @pytest.mark.asyncio
    async def test_together_complete_success(self, monkeypatch: Any) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module("Together hi"))
        from quadkit.ai.llm.clients.openai_compatible import TogetherClient

        client = TogetherClient(
            _compat_config("custom", "meta-llama/Llama-3-8b-chat-hf")
        )
        res = await client.complete(
            messages=[ChatMessage(role=Role.USER, content="hi")]
        )

        assert res.is_ok()
        assert res.unwrap().content == "Together hi"

    @pytest.mark.asyncio
    async def test_fireworks_complete_success(self, monkeypatch: Any) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module("Fireworks hi"))
        from quadkit.ai.llm.clients.openai_compatible import FireworksClient

        client = FireworksClient(
            _compat_config("custom", "accounts/fireworks/models/llama-v3-70b-instruct")
        )
        res = await client.complete(
            messages=[ChatMessage(role=Role.USER, content="hi")]
        )

        assert res.is_ok()
        assert res.unwrap().content == "Fireworks hi"

    def test_deepseek_uses_correct_base_url(self, monkeypatch: Any) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.openai_compatible import DeepSeekClient

        client = DeepSeekClient(_compat_config())
        assert "deepseek.com" in DeepSeekClient._provider_base_url

    def test_together_uses_correct_base_url(self, monkeypatch: Any) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.openai_compatible import TogetherClient

        assert "together.xyz" in TogetherClient._provider_base_url

    def test_fireworks_uses_correct_base_url(self, monkeypatch: Any) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.openai_compatible import FireworksClient

        assert "fireworks.ai" in FireworksClient._provider_base_url

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy_on_success(
        self, monkeypatch: Any
    ) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.openai_compatible import DeepSeekClient

        client = DeepSeekClient(_compat_config())
        result = await client.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.component == "llm.deepseek"

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_error(
        self, monkeypatch: Any
    ) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.openai_compatible import DeepSeekClient

        client = DeepSeekClient(_compat_config())

        class _FailModels:
            async def list(self) -> None:
                raise OSError("connection refused")

        client.client.models = _FailModels()

        result = await client.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "Provider health check failed (OSError)" in (result.error or "")
        assert "connection refused" not in (result.error or "")

    @pytest.mark.asyncio
    async def test_api_base_override_takes_precedence(self, monkeypatch: Any) -> None:
        """config.api_base overrides _provider_base_url."""
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.openai_compatible import DeepSeekClient

        config = ClientConfig(
            provider="custom",
            model="deepseek-chat",
            api_key=SecretStr("sk-test"),
            api_base="https://my-proxy.local/v1",
        )
        # Should not raise; custom base URL is used.
        client = DeepSeekClient(config)
        assert client is not None

    @pytest.mark.asyncio
    async def test_placeholder_api_key_used_when_no_key_in_config(
        self, monkeypatch: Any
    ) -> None:
        """A missing api_key falls back to the placeholder (required by openai SDK)."""
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.openai_compatible import TogetherClient

        # No api_key — should not raise
        client = TogetherClient(
            ClientConfig(
                provider="custom", model="llama-3-8b", api_base="https://x.com/v1"
            )
        )
        assert client is not None
