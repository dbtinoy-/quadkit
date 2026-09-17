"""Wire-accurate DTOs for the four relay protocols.

Each DTO carries only the fields the conversion engine semantically
understands. Unknown upstream fields land in ``passthrough`` and are
re-emitted verbatim on ``to_dict()`` so a gateway can forward request
bodies without data loss.

This package replaces the historical flat ``dto.py`` module.  The public
import path ``quadkit.contracts.ai.relay.dto`` is preserved: every
previously public name is re-exported here from its focused submodule.
"""

from __future__ import annotations

from quadkit.contracts.ai.relay.dto.claude import (
    ClaudeContent,
    ClaudeMessage,
    ClaudeRequest,
    ClaudeResponse,
    ClaudeStreamEvent,
    ClaudeUsage,
)
from quadkit.contracts.ai.relay.dto.gemini import (
    GeminiCandidate,
    GeminiContent,
    GeminiGroundingMetadata,
    GeminiPart,
    GeminiPromptFeedback,
    GeminiRequest,
    GeminiResponse,
    GeminiSafetyRating,
    GeminiUsageMetadata,
)
from quadkit.contracts.ai.relay.dto.openai_chat import (
    OpenAIChatChoice,
    OpenAIChatMessage,
    OpenAIChatRequest,
    OpenAIChatResponse,
    OpenAIChatStreamChoice,
    OpenAIChatStreamChunk,
    OpenAIChatStreamDelta,
)
from quadkit.contracts.ai.relay.dto.openai_responses import (
    ResponsesEvent,
    ResponsesIncompleteDetails,
    ResponsesItem,
    ResponsesRequest,
    ResponsesResponse,
    ResponsesUsage,
)

__all__ = [
    "ClaudeContent",
    "ClaudeMessage",
    "ClaudeRequest",
    "ClaudeResponse",
    "ClaudeStreamEvent",
    "ClaudeUsage",
    "GeminiCandidate",
    "GeminiContent",
    "GeminiGroundingMetadata",
    "GeminiPart",
    "GeminiPromptFeedback",
    "GeminiRequest",
    "GeminiResponse",
    "GeminiSafetyRating",
    "GeminiUsageMetadata",
    "OpenAIChatChoice",
    "OpenAIChatMessage",
    "OpenAIChatRequest",
    "OpenAIChatResponse",
    "OpenAIChatStreamChoice",
    "OpenAIChatStreamChunk",
    "OpenAIChatStreamDelta",
    "ResponsesEvent",
    "ResponsesIncompleteDetails",
    "ResponsesItem",
    "ResponsesRequest",
    "ResponsesResponse",
    "ResponsesUsage",
]
