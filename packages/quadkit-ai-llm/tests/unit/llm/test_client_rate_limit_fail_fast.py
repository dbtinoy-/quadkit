"""Rate-limited requests must fail fast inside clients.

With a multi-model cascade, the correct reaction to HTTP 429 is to
advance to the next cascade entry immediately — not to retry the
throttled model in place.  Other transient errors keep retrying.
"""

from __future__ import annotations

import pytest

from quadkit.ai.llm.clients.base import AbstractLLMClient
from quadkit.ai.llm.clients.openrouter import OpenRouterClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.exceptions import LLMError, LLMRateLimitError, LLMTimeoutError
from quadkit.contracts.web.http_models import HttpResponse
from quadkit.result import Err, Result


class _CountingClient(AbstractLLMClient):
    """AbstractLLMClient subclass returning a fixed error, counting attempts."""

    def __init__(self, error: LLMError) -> None:
        super().__init__(ClientConfig(provider="openai", model="test", api_key="x"))
        self._error = error
        self.attempts = 0

    async def _do_complete(self, messages, **kwargs) -> Result:
        self.attempts += 1
        return Err(self._error)

    async def _do_chat(self, messages, **kwargs) -> Result:
        return Err(self._error)

    async def _do_stream_chat(self, messages, **kwargs):
        raise NotImplementedError

    async def health_check(self, timeout: float = 5.0):
        raise NotImplementedError

    async def _backoff(self, attempt: int) -> None:
        return  # no sleeping in tests


async def test_rate_limit_error_is_not_retried_and_is_sanitized():
    secret = "RATE_LIMIT_SECRET_SENTINEL"
    client = _CountingClient(LLMRateLimitError(secret))
    result = await client.complete(messages=[])
    assert result.is_err()
    error = result.unwrap_err()
    assert isinstance(error, LLMRateLimitError)
    assert secret not in str(error)
    assert error.details == {"error_type": "LLMRateLimitError"}
    assert client.attempts == 1


async def test_transient_error_still_retries_and_is_sanitized():
    secret = "connection reset by peer"
    client = _CountingClient(LLMError(secret))
    result = await client.complete(messages=[])
    assert result.is_err()
    assert secret not in str(result.unwrap_err())
    assert client.attempts == client.max_retries + 1


async def test_raised_provider_exception_is_sanitized(capsys):
    secret = "RAISED_PROVIDER_SECRET_SENTINEL"

    class _RaisingClient(_CountingClient):
        def __init__(self) -> None:
            super().__init__(LLMError("unused"))
            self.max_retries = 0

        async def _do_complete(self, messages, **kwargs) -> Result:
            self.attempts += 1
            raise RuntimeError(secret)

    client = _RaisingClient()
    with pytest.raises(LLMError) as exc_info:
        await client.complete(messages=[])

    error = exc_info.value
    assert secret not in str(error)
    assert error.details == {"error_type": "RuntimeError"}
    assert error.__cause__ is None

    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert "RuntimeError" in captured.out + captured.err


class _Http429Client:
    """Fake ResilientHTTPClient whose POST always returns HTTP 429."""

    def __init__(self) -> None:
        self.post_calls = 0

    async def post(self, path: str, json: dict | None = None) -> HttpResponse:
        self.post_calls += 1
        response = HttpResponse(
            status=429,
            url="https://openrouter.ai/api/v1/chat/completions",
            method="POST",
        )
        response.raise_for_status()
        return response


async def test_openrouter_http_429_maps_to_rate_limit_error_and_fails_fast():
    client = OpenRouterClient(
        ClientConfig(provider="openrouter", model="test-model", api_key="x")
    )
    http = _Http429Client()
    client._client = http  # type: ignore[assignment]  # bypass real HTTP client

    async def _no_backoff(attempt: int) -> None:
        return

    client._backoff = _no_backoff  # type: ignore[method-assign]

    result = await client.complete(messages=[])

    assert result.is_err()
    assert isinstance(result.unwrap_err(), LLMRateLimitError)
    assert http.post_calls == 1


class _HttpTimeoutClient:
    """Fake ResilientHTTPClient whose POST always times out."""

    def __init__(self) -> None:
        self.post_calls = 0

    async def post(self, path: str, json: dict | None = None) -> HttpResponse:
        self.post_calls += 1
        raise TimeoutError


async def test_openrouter_timeout_maps_to_timeout_error_and_fails_fast():
    """A request timeout must advance the cascade, not retry 4x in place.

    Each in-place retry costs a full client timeout (120s in prod); the
    router's cascade should move to the next entry instead.
    """
    client = OpenRouterClient(
        ClientConfig(provider="openrouter", model="test-model", api_key="x")
    )
    http = _HttpTimeoutClient()
    client._client = http  # type: ignore[assignment]  # bypass real HTTP client

    async def _no_backoff(attempt: int) -> None:
        return

    client._backoff = _no_backoff  # type: ignore[method-assign]

    result = await client.complete(messages=[])

    assert result.is_err()
    assert isinstance(result.unwrap_err(), LLMTimeoutError)
    assert http.post_calls == 1


async def test_timeout_error_is_not_retried_by_base_client():
    # Message deliberately contains "timeout", which the legacy string
    # heuristic treats as retryable — the typed check must win.
    client = _CountingClient(LLMTimeoutError("request timeout after 120s"))
    result = await client.complete(messages=[])
    assert result.is_err()
    assert client.attempts == 1
