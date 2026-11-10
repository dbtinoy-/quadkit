"""LLM package exceptions."""

from __future__ import annotations

from copy import copy

from quadkit.contracts.ai.exceptions import (
    ExtractionError as _ContractsExtractionError,
)
from quadkit.contracts.ai.exceptions import LLMError as _ContractsLLMError

__all__ = [
    "EmbeddingError",
    "ExtractionError",
    "ExtractionMaxRetriesError",
    "ExtractionParseError",
    "ExtractionValidationError",
    "InvalidRequestError",
    "LLMAuthenticationError",
    "LLMContentFilterError",
    "LLMError",
    "LLMModelNotFoundError",
    "LLMQuotaExceededError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "ModelNotFoundError",
    "ModelRevisionMismatchError",
    "ProviderConnectionError",
    "StreamError",
    "TokenLimitError",
    "sanitize_llm_error",
]


class LLMError(_ContractsLLMError):
    """Base exception for all LLM-domain errors in quadkit-ai-llm."""

    _code: str = "QK_ERR_LLM_002"


class LLMAuthenticationError(LLMError):
    """Invalid API key or credentials — infrastructure error, raised not wrapped.

    Raised as an exception (NOT wrapped in ``Result``).
    Indicates a misconfiguration the application cannot route around.
    """

    _code: str = "QK_ERR_LLM_003"


class InvalidRequestError(LLMError):
    """Error raised when a request to an LLM provider is invalid."""

    _code: str = "QK_ERR_LLM_004"


class ModelNotFoundError(LLMError):
    """Model unavailable or not found — recoverable via fallback routing."""

    _code: str = "QK_ERR_LLM_005"


class LLMModelNotFoundError(ModelNotFoundError):
    """Model unavailable or not found — recoverable via fallback routing.

    Returned as ``Err`` from ``LLMClientProtocol.complete()`` / ``stream_chat()``.
    The caller should route to a different model or provider.
    """

    _code: str = "QK_ERR_LLM_006"


class LLMRateLimitError(LLMError):
    """Rate limit exceeded — recoverable via backoff/retry.

    Returned as ``Err`` from ``LLMClientProtocol.complete()`` / ``stream_chat()``.
    The caller should implement exponential backoff or route to another provider.
    """

    _code: str = "QK_ERR_LLM_007"


class LLMQuotaExceededError(LLMError):
    """API quota or billing limit exceeded — recoverable by routing elsewhere.

    Returned as ``Err`` from ``LLMClientProtocol.complete()`` / ``stream_chat()``.
    The caller should route the request to a different provider or account.
    """

    _code: str = "QK_ERR_LLM_008"


class LLMContentFilterError(LLMError):
    """Content blocked by provider safety filter — recoverable via reformulation.

    Returned as ``Err`` from ``LLMClientProtocol.complete()`` / ``stream_chat()``.
    The caller should reformulate the prompt or inform the user.
    """

    _code: str = "QK_ERR_LLM_009"


class TokenLimitError(LLMError):
    """Error raised when the token limit for a request is exceeded."""

    _code: str = "QK_ERR_LLM_010"


class ProviderConnectionError(LLMError):
    """Error raised when connection to an LLM provider fails."""

    _code: str = "QK_ERR_LLM_011"


class StreamError(LLMError):
    """Error raised during LLM response streaming."""

    _code: str = "QK_ERR_LLM_012"


class ExtractionError(_ContractsExtractionError):
    """Base class for structured extraction errors in quadkit-ai-llm."""

    _code: str = "QK_ERR_LLM_013"


class ExtractionParseError(ExtractionError):
    """Error raised when extraction response cannot be parsed as JSON."""

    _code: str = "QK_ERR_LLM_014"


class ExtractionValidationError(ExtractionError):
    """Error raised when parsed extraction response fails schema validation."""

    _code: str = "QK_ERR_LLM_015"


class ExtractionMaxRetriesError(ExtractionError):
    """Error raised when extraction max retries are exhausted."""

    _code: str = "QK_ERR_LLM_016"


class ModelRevisionMismatchError(LLMError):
    """Raised when the provider returns a model revision that violates the pin policy."""

    _code: str = "QK_ERR_LLM_017"


class LLMTimeoutError(LLMError):
    """Request exceeded the client timeout — recoverable by routing elsewhere.

    Returned as ``Err`` from ``LLMClientProtocol.complete()`` / ``stream_chat()``.
    Not retried in place: the request already consumed a full timeout window,
    so the caller (router cascade) should advance to another provider.
    """

    _code: str = "QK_ERR_LLM_018"


class EmbeddingError(LLMError):
    """Raised when embedding generation fails.

    Covers missing credentials, provider HTTP failures (mapped to
    :class:`LLMAuthenticationError` / :class:`LLMRateLimitError` where
    specific), malformed provider responses, and local model load failures.
    """

    _code: str = "QK_ERR_LLM_029"


def sanitize_llm_error(error: Exception) -> LLMError:
    """Return an LLM error without provider-controlled text or cause details.

    Known LLM exception subtypes are preserved so routing and retry policies
    can continue to branch on their types. Other exceptions are mapped to a
    generic :class:`LLMError`.
    """
    if not isinstance(error, LLMError):
        return LLMError(
            "LLM provider request failed",
            details={"error_type": type(error).__name__},
        )

    safe_error = copy(error)
    error_type = type(error).__name__
    if isinstance(error, LLMAuthenticationError):
        message = "LLM provider authentication failed"
    elif isinstance(error, LLMRateLimitError):
        message = "LLM provider rate limit exceeded"
    elif isinstance(error, LLMTimeoutError):
        message = "LLM provider request timed out"
    else:
        message = "LLM provider request failed"

    safe_error.message = message
    safe_error.details = {"error_type": error_type}
    safe_error.cause = None
    safe_error.hint = None
    safe_error.args = (message,)
    safe_error.__cause__ = None
    safe_error.__context__ = None
    safe_error.__suppress_context__ = True
    return safe_error
