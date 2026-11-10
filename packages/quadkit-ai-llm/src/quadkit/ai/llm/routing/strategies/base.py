"""Base definitions and shared helpers for routing strategies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.exceptions import LLMQuotaExceededError, LLMRateLimitError
from quadkit.ai.llm.routing.types import InferenceResult
from quadkit.ai.llm.types import ChatMessage, Role
from quadkit.contracts.ai.multimodal import ImageUrlPart, TextPart
from quadkit.contracts.web.http_models import HttpStatusError
from quadkit.logging import get_logger, safe_error_type
from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.ai.llm.routing.config import (
        LLMConfig,
    )
    from quadkit.ai.llm.types import AIError
    from quadkit.contracts.ai import LLMClientProtocol
    from quadkit.contracts.ai.routing import QuotaBackendProtocol

logger = get_logger(__name__)


def _extract_status_code(exc: AIError) -> int | None:
    """Extract the HTTP status code from an ``AIError``, if available.

    Typed errors map directly (rate limit → 429, quota → 402) since clients
    that return ``Err(...)`` carry no ``__cause__`` chain to inspect.
    """
    if isinstance(exc, LLMRateLimitError):
        return 429
    if isinstance(exc, LLMQuotaExceededError):
        return 402
    status_code: int | None = getattr(exc, "status_code", None)
    if status_code is None and exc.__cause__ is not None:
        status_code = getattr(exc.__cause__, "status_code", None)
        if status_code is None and isinstance(exc.__cause__, HttpStatusError):
            status_code = exc.__cause__.status
    return status_code


async def _attempt_provider(
    *,
    client: LLMClientProtocol,
    provider_name: str,
    model: str,
    messages: list[Any],
    temperature: float,
    max_tokens: int | None,
) -> InferenceResult:
    """Make a single completion request against *client*.

    Accepts both ``ChatMessage`` objects and OpenAI-compatible dicts;
    dicts are normalised to ``ChatMessage`` before dispatch.
    Multimodal content (list payloads with ``image_url``/``text`` parts) is
    preserved as typed ``ContentPart`` objects so vision models receive the
    full payload.
    """
    t0 = ambient_clock.monotonic()

    chat_messages: list[ChatMessage] = []
    for msg in messages:
        if isinstance(msg, ChatMessage):
            chat_messages.append(msg)
        elif isinstance(msg, dict):
            raw_content = msg.get("content", "")
            if isinstance(raw_content, list):
                content_parts: list[TextPart | ImageUrlPart] = []
                for part in raw_content:
                    if not isinstance(part, dict):
                        continue
                    part_type = part.get("type")
                    if part_type == "text":
                        content_parts.append(TextPart(text=part.get("text", "")))
                    elif part_type == "image_url":
                        img = part.get("image_url", {})
                        if isinstance(img, dict):
                            url = img.get("url", "")
                            detail = img.get("detail", "auto")
                        else:
                            url = str(img)
                            detail = "auto"
                        content_parts.append(ImageUrlPart(url=url, detail=detail))
                content: str | list = content_parts if content_parts else ""
            else:
                content = str(raw_content)
            role_str = msg.get("role", "user")
            try:
                role = Role(role_str)
            except ValueError:
                role = Role.USER
            chat_messages.append(ChatMessage(role=role, content=content))

    result = await client.complete(
        messages=chat_messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if result.is_err():
        raise result.unwrap_err()
    completion = result.unwrap()
    latency_ms = (ambient_clock.monotonic() - t0) * 1000.0
    usage = completion.usage
    if usage is None:
        prompt_tokens = 0
        completion_tokens = 0
    else:
        prompt_tokens = usage.prompt_tokens  # type: ignore[attr-defined]
        completion_tokens = usage.completion_tokens  # type: ignore[attr-defined]
    return InferenceResult(
        provider=provider_name,
        model=model,
        content=completion.content,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


async def _handle_free_failure(
    *,
    exc: AIError,
    provider_key: str,
    model: str,
    quota: QuotaBackendProtocol,
    cooldown_seconds: int,
) -> None:
    """Update quota state after a cascade-entry failure.

    429 (throttle) cools the entry down for *cooldown_seconds*; 402
    (payment) exhausts it for the rest of the UTC day; anything else is
    recorded as a plain error.  State is keyed per cascade entry
    (``ProviderConfig.key``), so one entry's failure never poisons its
    siblings.
    """
    status_code = _extract_status_code(exc)
    if status_code == 429:
        until = datetime.now(UTC) + timedelta(seconds=cooldown_seconds)
        logger.warning(
            "strategy_entry_throttled",
            cooldown_seconds=cooldown_seconds,
        )
        await quota.mark_exhausted(provider_key, until=until)
    elif status_code == 402:
        logger.warning("strategy_entry_payment_exhausted", status_code=status_code)
        await quota.mark_exhausted(provider_key)
    else:
        logger.warning(
            "strategy_entry_failed",
            status_code=status_code,
            error_type=safe_error_type(exc),
        )
        await quota.record_error(provider_key)


def _gen_defaults(
    config: LLMConfig,
    kwargs: dict[str, Any],
) -> tuple[float, int | None]:
    """Resolve temperature and max_tokens from config + overrides."""
    defaults = config.defaults
    return (
        kwargs.get("temperature", defaults.temperature),
        kwargs.get("max_tokens", defaults.max_tokens),
    )


def _estimate_prompt_tokens(messages: list[Any]) -> int:
    """Rough token estimate for prompt messages (~4 chars per token)."""
    total_chars = 0
    for msg in messages:
        if isinstance(msg, dict):
            total_chars += len(str(msg.get("content", "")))
        elif hasattr(msg, "content"):
            total_chars += len(str(msg.content))
        else:
            total_chars += len(str(msg))
    return max(1, total_chars // 4)
