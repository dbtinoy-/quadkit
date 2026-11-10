"""Unit tests for GeminiClient and CloudflareWorkersClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.gemini import GeminiClient, _messages_to_gemini
from quadkit.ai.llm.clients.cloudflare_workers import CloudflareWorkersClient
from quadkit.ai.llm.exceptions import LLMAuthenticationError, LLMRateLimitError, LLMError
from quadkit.ai.llm.types import AIError
from quadkit.contracts.web.http_models import HttpStatusError


def _make_http_error(status: int) -> HttpStatusError:
    """Construct an HttpStatusError from a mocked response."""
    mock_response = MagicMock()
    mock_response.url = "https://example.com/fake"
    mock_response.method = "POST"
    return HttpStatusError(f"HTTP {status}", status=status, response=mock_response)


# ── GeminiClient ──────────────────────────────────────────────────────────────


def _gemini_config(**kwargs) -> ClientConfig:
    return ClientConfig(
        provider="gemini",
        model="gemini-2.5-flash",
        api_key="AIza-fake",
        **kwargs,
    )


def _mock_http_response(data: dict) -> MagicMock:
    """Create a mock HttpResponse with .json as a property (not a method)."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    type(resp).json = property(lambda self: data)
    return resp


@pytest.mark.asyncio
async def test_gemini_complete_success():
    client = GeminiClient(_gemini_config())
    api_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello from Gemini!"}],
                    "role": "model",
                }
            }
        ],
        "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 10},
    }
    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=_mock_http_response(api_response))
    client._http = mock_http

    res = await client.complete(
        messages=[{"role": "user", "content": "Hi"}],
        model="gemini-2.5-flash",
    )

    assert res.is_ok()
    completion = res.unwrap()
    assert completion.content == "Hello from Gemini!"
    assert completion.usage.prompt_tokens == 5
    assert completion.usage.completion_tokens == 10


@pytest.mark.asyncio
async def test_gemini_authenticate_error_raises_auth_error():
    client = GeminiClient(_gemini_config())
    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=_make_http_error(401))
    client._http = mock_http

    with pytest.raises(LLMAuthenticationError):
        await client.complete(messages=[{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
async def test_gemini_rate_limit_raises_rate_limit_error():
    client = GeminiClient(_gemini_config())
    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=_make_http_error(429))
    client._http = mock_http

    client.max_retries = 0
    res = await client.complete(messages=[{"role": "user", "content": "Hi"}])
    assert res.is_err()
    err = res.unwrap_err()
    assert isinstance(err, LLMRateLimitError)


@pytest.mark.asyncio
async def test_gemini_raises_ai_error_for_unknown_http_status():
    client = GeminiClient(_gemini_config())
    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=_make_http_error(503))
    client._http = mock_http

    client.max_retries = 0
    with pytest.raises(AIError):
        await client.complete(messages=[{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
async def test_gemini_raises_auth_error_when_api_key_missing():
    client = GeminiClient(ClientConfig(provider="gemini", model="m"))
    with pytest.raises(LLMAuthenticationError):
        await client.complete(messages=[])


def test_gemini_messages_conversion_simple():
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    contents = _messages_to_gemini(messages)
    # System prepended to first user turn
    assert len(contents) == 1
    assert contents[0]["role"] == "user"
    texts = [p["text"] for p in contents[0]["parts"] if "text" in p]
    assert "You are helpful." in texts
    assert "Hello" in texts


def test_gemini_messages_conversion_assistant_role():
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    contents = _messages_to_gemini(messages)
    assert len(contents) == 2
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"


@pytest.mark.asyncio
async def test_gemini_close_cleans_up():
    client = GeminiClient(_gemini_config())
    mock_http = MagicMock()
    mock_http.close = AsyncMock()
    client._http = mock_http

    await client.close()

    mock_http.close.assert_called_once()
    assert client._http is None


@pytest.mark.asyncio
async def test_gemini_context_manager():
    client = GeminiClient(_gemini_config())
    mock_http = MagicMock()
    mock_http.close = AsyncMock()
    client._http = mock_http

    async with client as c:
        assert c is client

    mock_http.close.assert_called_once()


# ── CloudflareWorkersClient ───────────────────────────────────────────────────


def _cf_config(**kwargs) -> ClientConfig:
    return ClientConfig(
        provider="cloudflare",
        model="@cf/meta/llama-3.1-8b-instruct",
        extra={
            "cf_account_id": "fake-account-id",
            "cf_api_token": "fake-token",
        },
        **kwargs,
    )


def _cf_response(text: str = "Hello from Cloudflare") -> dict:
    return {"success": True, "result": {"response": text}}


@pytest.mark.asyncio
async def test_cloudflare_complete_success():
    client = CloudflareWorkersClient(_cf_config())
    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=_mock_http_response(_cf_response("CF hello")))
    client._http = mock_http

    res = await client.complete(
        messages=[{"role": "user", "content": "Hi"}],
    )

    assert res.is_ok()
    completion = res.unwrap()
    assert completion.content == "CF hello"


@pytest.mark.asyncio
async def test_cloudflare_rate_limit_raises_rate_limit_error():
    client = CloudflareWorkersClient(_cf_config())
    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=_make_http_error(429))
    client._http = mock_http

    client.max_retries = 0
    res = await client.complete(messages=[{"role": "user", "content": "Hi"}])
    assert res.is_err()
    err = res.unwrap_err()
    assert isinstance(err, LLMRateLimitError)


def test_cloudflare_raises_auth_error_when_credentials_missing():
    config = ClientConfig(
        provider="cloudflare",
        model="@cf/meta/llama-3.1-8b-instruct",
        extra={},
    )
    with pytest.raises(LLMAuthenticationError):
        CloudflareWorkersClient(config)


@pytest.mark.asyncio
async def test_cloudflare_close_cleans_up():
    client = CloudflareWorkersClient(_cf_config())
    mock_http = MagicMock()
    mock_http.close = AsyncMock()
    client._http = mock_http

    await client.close()

    mock_http.close.assert_called_once()
    assert client._http is None
