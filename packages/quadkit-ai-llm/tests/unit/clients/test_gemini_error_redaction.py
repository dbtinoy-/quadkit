"""Gemini provider errors do not expose response bodies or API-key URLs."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.ai.llm.clients.gemini import GeminiClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
)
from quadkit.ai.llm.types import AIError
from quadkit.contracts.web.http_models import HttpResponse, HttpStatusError

_PRIVATE_URL = "https://private.example/v1?key=AIza-private-api-key"
_PRIVATE_BODY = "/srv/provider/private/prompt.txt prompt=private-prompt"


def _client() -> GeminiClient:
    return GeminiClient(
        ClientConfig(
            provider="gemini",
            model="gemini-2.5-flash",
            api_key="AIza-private-api-key",
        )
    )


def _http_error(status: int, *, body: str = _PRIVATE_BODY) -> HttpStatusError:
    response = HttpResponse(
        status=status,
        url=_PRIVATE_URL,
        method="POST",
        text=body,
        json={"error": {"message": body}},
    )
    return HttpStatusError(
        f"HTTP {status} for POST {_PRIVATE_URL}: {body}",
        status=status,
        response=response,
    )


@pytest.mark.parametrize(
    ("status", "expected", "message"),
    [
        (400, LLMError, "gemini: invalid request"),
        (429, LLMRateLimitError, "gemini: rate limit exceeded"),
        (404, LLMModelNotFoundError, "gemini: model not found"),
    ],
)
def test_recoverable_http_error_text_is_generic(
    status: int, expected: type[LLMError], message: str
) -> None:
    """Recoverable error classification is retained without body text."""
    result = _client()._handle_error_as_result(_http_error(status))

    assert result.is_err()
    error = result.unwrap_err()
    assert isinstance(error, expected)
    assert message in str(error)
    assert _PRIVATE_BODY not in str(error)
    assert _PRIVATE_URL not in str(error)
    assert "AIza-private-api-key" not in str(error)


def test_model_not_found_400_uses_private_body_only_for_classification() -> None:
    """A known 400 model error keeps its type but not its provider text."""
    private_detail = f"Model 'private-model' does not exist: {_PRIVATE_BODY}"
    result = _client()._handle_error_as_result(
        _http_error(400, body=private_detail)
    )

    assert result.is_err()
    error = result.unwrap_err()
    assert isinstance(error, LLMModelNotFoundError)
    assert "gemini: model not found" in str(error)
    assert private_detail not in str(error)
    assert "private-model" not in str(error)
    assert _PRIVATE_URL not in str(error)


def test_bad_request_error_is_generic() -> None:
    """Invalid-request details are not included in the returned error."""
    result = _client()._handle_error_as_result(
        _http_error(400, body="private input is invalid")
    )

    assert result.is_err()
    error = result.unwrap_err()
    assert type(error) is LLMError
    assert "gemini: invalid request" in str(error)
    assert "private input" not in str(error)


def test_authentication_error_does_not_chain_http_details() -> None:
    """The raised auth error has neither secret URL text nor raw cause."""
    with pytest.raises(LLMAuthenticationError) as exc_info:
        _client()._handle_error_as_result(_http_error(403))

    assert "AIza-private-api-key" not in str(exc_info.value)
    assert _PRIVATE_URL not in str(exc_info.value)
    assert _PRIVATE_BODY not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


def test_infrastructure_error_does_not_chain_http_details() -> None:
    """Unexpected provider failures retain a generic type-only message."""
    with pytest.raises(AIError) as exc_info:
        _client()._handle_error_as_result(_http_error(500))

    assert "gemini: infrastructure error" in str(exc_info.value)
    assert _PRIVATE_URL not in str(exc_info.value)
    assert _PRIVATE_BODY not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


class _ResponseHTTP:
    """HTTP stub returning a canned successful response."""

    def __init__(self, response: HttpResponse) -> None:
        self.response = response

    async def post(self, path: str, **kwargs: Any) -> HttpResponse:
        del path, kwargs
        return self.response


async def test_content_filter_error_does_not_echo_provider_block_reason() -> None:
    """Parser diagnostics are replaced with a static content-filter message."""
    client = _client()
    client._http = _ResponseHTTP(
        HttpResponse(
            status=200,
            json={"promptFeedback": {"blockReason": _PRIVATE_BODY}},
        )
    )  # type: ignore[assignment]

    result = await client._do_complete([{"role": "user", "content": "hi"}])

    assert result.is_err()
    error = result.unwrap_err()
    assert isinstance(error, LLMContentFilterError)
    assert "blocked" in str(error)
    assert _PRIVATE_BODY not in str(error)
    assert "AIza-private-api-key" not in str(error)
