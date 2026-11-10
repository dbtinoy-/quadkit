"""Error mapping for AWS Bedrock / boto3 exceptions.

Translates dynamic provider exceptions raised by ``botocore`` into typed
LLM errors. Authentication failures re-raise; recoverable failures are
returned as ``Err`` values.
"""

from __future__ import annotations

from typing import Any

from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
)
from quadkit.ai.llm.types import AIError
from quadkit.result import Err, Result

__all__ = ["error_to_result"]


def error_to_result(error: Exception) -> Result[Any, LLMError]:
    """Map a caught exception to ``Err`` or re-raise for infrastructure failures."""
    err_str = str(error)
    err_code = getattr(getattr(error, "response", {}).get("Error", {}), "Code", None)
    if err_code is None and hasattr(error, "response"):
        resp = error.response
        if isinstance(resp, dict):
            err_code = resp.get("Error", {}).get("Code", "")

    if err_code in (
        "AccessDeniedException",
        "AuthorizationException",
        "UnauthorizedException",
    ):
        raise LLMAuthenticationError("bedrock: authentication failed") from None
    if err_code in ("ThrottlingException", "TooManyRequestsException"):
        return Err(LLMRateLimitError("bedrock: rate limit exceeded"))
    if err_code in (
        "ModelNotReadyException",
        "ModelNotFoundException",
        "ResourceNotFoundException",
    ):
        return Err(LLMModelNotFoundError("bedrock: model not found"))
    if err_code == "ValidationException" and "content filter" in err_str.lower():
        return Err(LLMContentFilterError("bedrock: content filtered"))
    raise AIError("bedrock: infrastructure error") from None
