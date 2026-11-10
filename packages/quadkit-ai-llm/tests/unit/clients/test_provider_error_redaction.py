"""Provider error mappers never expose provider text or request URLs."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import aiohttp
import pytest
from yarl import URL

from quadkit.ai.llm.clients.anthropic import AnthropicClient
from quadkit.ai.llm.clients._bedrock_errors import error_to_result
from quadkit.ai.llm.clients.cloudflare_workers import CloudflareWorkersClient
from quadkit.ai.llm.clients.cohere import CohereClient
from quadkit.ai.llm.clients.gemini import GeminiClient
from quadkit.ai.llm.clients.groq import GroqClient
from quadkit.ai.llm.clients.mistral import MistralClient
from quadkit.ai.llm.clients.openai import OpenAIClient
from quadkit.ai.llm.clients.openrouter import OpenRouterClient
from quadkit.ai.llm.clients.vertex_ai import VertexAIClient
from quadkit.ai.llm.exceptions import LLMAuthenticationError, LLMRateLimitError
from quadkit.contracts.web.http_models import HttpResponse, HttpStatusError

_PRIVATE_DETAIL = (
    "api_key=sk-provider-private /srv/private/prompts/tenant-42.txt"
)
_PRIVATE_URL = "https://private.example/v1?api_key=sk-provider-private"


def _http_status_error(status: int) -> HttpStatusError:
    response = HttpResponse(
        status=status,
        url=_PRIVATE_URL,
        method="POST",
        text=_PRIVATE_DETAIL,
        json={"error": _PRIVATE_DETAIL},
    )
    return HttpStatusError(
        f"HTTP {status} for {_PRIVATE_URL}: {_PRIVATE_DETAIL}",
        status=status,
        response=response,
    )


def _aiohttp_status_error(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(
        request_info=SimpleNamespace(real_url=URL(_PRIVATE_URL)),  # type: ignore[arg-type]
        history=(),
        status=status,
        message=_PRIVATE_DETAIL,
    )


def _assert_safe_rate_limit(result: Any) -> None:
    assert result.is_err()
    error = result.unwrap_err()
    assert isinstance(error, LLMRateLimitError)
    assert _PRIVATE_DETAIL not in str(error)
    assert _PRIVATE_URL not in str(error)
    assert "sk-provider-private" not in str(error)
    assert error.__cause__ is None


@pytest.mark.parametrize(
    ("client_type", "error"),
    [
        (OpenAIClient, RuntimeError(f"rate limit: {_PRIVATE_DETAIL}")),
        (AnthropicClient, RuntimeError(f"rate limit: {_PRIVATE_DETAIL}")),
        (CloudflareWorkersClient, _http_status_error(429)),
        (GeminiClient, _http_status_error(429)),
        (GroqClient, _aiohttp_status_error(429)),
        (MistralClient, _aiohttp_status_error(429)),
        (CohereClient, _aiohttp_status_error(429)),
        (OpenRouterClient, _http_status_error(429)),
        (VertexAIClient, _http_status_error(429)),
    ],
)
def test_provider_rate_limit_mapping_hides_provider_details(
    client_type: type[Any], error: Exception
) -> None:
    """Common provider mappers preserve error types without echoing bodies."""
    client = object.__new__(client_type)

    result = client._handle_error_as_result(error)

    _assert_safe_rate_limit(result)


def test_bedrock_rate_limit_mapping_hides_provider_details() -> None:
    """Bedrock's response envelope is classified without exposing messages."""

    class _BedrockError(Exception):
        response = {"Error": {"Code": "ThrottlingException", "Message": _PRIVATE_DETAIL}}

    result = error_to_result(_BedrockError(_PRIVATE_DETAIL))

    _assert_safe_rate_limit(result)


def test_authentication_mapping_does_not_chain_provider_error() -> None:
    """Authentication errors omit raw provider details and exception causes."""
    client = object.__new__(OpenAIClient)

    with pytest.raises(LLMAuthenticationError) as exc_info:
        client._handle_error_as_result(RuntimeError(f"invalid api key: {_PRIVATE_DETAIL}"))

    assert "sk-provider-private" not in str(exc_info.value)
    assert _PRIVATE_URL not in str(exc_info.value)
    assert _PRIVATE_DETAIL not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
