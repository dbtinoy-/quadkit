"""Shared types for the relay protocol conversion engine.

This module owns the stable enums, JSON aliases, usage accounting, loss
records, conversion results, and payload unions that cross every relay
wire format.  Concrete wire DTOs live in ``relay.dto``; the canonical IR
lives in ``relay.ir``; engine-side services live in the
``the optional provider`` extension package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeAlias, TypeVar

from quadkit.contracts.ai.llm import TokenUsage
from quadkit.contracts.ai.relay.dto import (
    ClaudeRequest,
    ClaudeResponse,
    GeminiRequest,
    GeminiResponse,
    OpenAIChatRequest,
    OpenAIChatResponse,
    ResponsesRequest,
    ResponsesResponse,
)

__all__ = [
    "ConversionQuality",
    "JsonObject",
    "JsonValue",
    "RelayConvertResult",
    "RelayFormat",
    "RelayLoss",
    "RelayRequestPayload",
    "RelayResponsePayload",
    "RelayUsage",
]


class RelayFormat(StrEnum):
    """The four text wire protocols supported by the relay engine.

    Attributes:
        OPENAI_CHAT: OpenAI Chat Completions (``/v1/chat/completions``).
        OPENAI_RESPONSES: OpenAI Responses (``/v1/responses``).
        CLAUDE: Anthropic Messages (``/v1/messages``).
        GEMINI: Google Gemini ``generateContent``.
    """

    OPENAI_CHAT = "openai_chat"
    OPENAI_RESPONSES = "openai_responses"
    CLAUDE = "claude"
    GEMINI = "gemini"


class ConversionQuality(StrEnum):
    """Semantic closeness between two wire protocols.

    Attributes:
        GOOD: Core structures are close; lossless in practice.
        FAIR: Main capabilities convert, some features adapt or drop.
        DISCOURAGED: Requires a multi-hop path; higher semantic-loss risk.
    """

    GOOD = "GOOD"
    FAIR = "FAIR"
    DISCOURAGED = "DISCOURAGED"


JsonValue: TypeAlias = dict[str, Any] | list[Any] | str | int | float | bool | None
"""A JSON-compatible value."""

JsonObject: TypeAlias = dict[str, JsonValue]
"""A JSON object (wire request/response fragment)."""


@dataclass(frozen=True)
class RelayUsage:
    """Unified token usage, normalized across upstream response formats.

    Attributes:
        prompt_tokens: Input tokens (total, all subcategories).
        completion_tokens: Output tokens (total, all subcategories).
        cache_read_tokens: Cached input tokens (Claude ``cache_read``, OpenAI ``cached_tokens``).
        cache_creation_tokens: Cache-creation input tokens (Claude only).
        reasoning_tokens: Output tokens spent on reasoning (Claude/Gemini thinking).
        audio_input_tokens: Audio input tokens (OpenAI audio models).
        audio_output_tokens: Audio output tokens (OpenAI audio models).
        image_tokens: Image input tokens (OpenAI image models).
        input_tokens: Responses-style input count carried by the source
            (Claude stamps prompt+cache; Gemini leaves it zero).
        output_tokens: Responses-style output count carried by the source
            (only the OpenAI response format stamps it).
        total_tokens_override: Explicit total when the source reports one
            that is not the sum of prompt and completion (Gemini counts
            thinking tokens inside both).
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    reasoning_tokens: int = 0
    audio_input_tokens: int = 0
    audio_output_tokens: int = 0
    image_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens_override: int | None = None

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed (prompt + completion or explicit override)."""
        if self.total_tokens_override is not None:
            return self.total_tokens_override
        return self.prompt_tokens + self.completion_tokens

    def to_token_usage(self) -> TokenUsage:
        """Map to the shared ``TokenUsage`` without double counting.

        Returns:
            A ``TokenUsage`` with the derived total; detailed sub-category
            counts remain available on this object.
        """
        return TokenUsage(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
        )


@dataclass(frozen=True)
class RelayLoss:
    """A semantic loss recorded during conversion.

    Attributes:
        field: Source wire field (or feature) that was dropped or adapted.
        target: Target format the loss applies to.
        reason: Machine-readable reason (e.g. ``json_mode_not_supported``).
        severity: ``error``, ``warning``, or ``info``.
    """

    field: str
    target: RelayFormat
    reason: str
    severity: str = "warning"


T = TypeVar("T")


@dataclass(frozen=True)
class RelayConvertResult(Generic[T]):
    """Outcome of a conversion with audit metadata.

    Attributes:
        value: The converted object.
        source: Source wire format.
        target: Target wire format.
        converter_id: Converter identifier (``"<src>_to_<dst>"``).
        quality: Semantic closeness of the conversion.
        steps: Actual conversion path taken (source, canonical_ir, target,
            plus named adaptations when present).
        usage: Normalized usage when converting responses; ``None`` otherwise.
        losses: Semantic losses recorded during conversion.
        warnings: Human-readable compatibility notes.
    """

    value: T
    source: RelayFormat
    target: RelayFormat
    converter_id: str
    quality: ConversionQuality
    steps: tuple[str, ...] = field(default_factory=tuple)
    usage: RelayUsage | None = None
    losses: tuple[RelayLoss, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


RelayRequestPayload: TypeAlias = (
    OpenAIChatRequest | ResponsesRequest | ClaudeRequest | GeminiRequest
)
"""Union of every request wire DTO the relay engine accepts."""

RelayResponsePayload: TypeAlias = (
    OpenAIChatResponse | ResponsesResponse | ClaudeResponse | GeminiResponse
)
"""Union of every non-stream response wire DTO the relay engine emits."""
