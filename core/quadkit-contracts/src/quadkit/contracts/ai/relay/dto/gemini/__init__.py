"""Gemini ``generateContent`` wire DTO family.

Field names follow the Gemini API camelCase wire format; the DTO layer
accepts documented snake_case aliases only where noted.

Modules are split for the 500-LOC ratchet; import from this package
for the canonical top-level names."""

from __future__ import annotations

from quadkit.contracts.ai.relay.dto.gemini.parts import GeminiContent, GeminiPart
from quadkit.contracts.ai.relay.dto.gemini.request import GeminiRequest
from quadkit.contracts.ai.relay.dto.gemini.response import (
    GeminiCandidate,
    GeminiGroundingMetadata,
    GeminiPromptFeedback,
    GeminiResponse,
    GeminiSafetyRating,
    GeminiUsageMetadata,
)

__all__ = [
    "GeminiCandidate",
    "GeminiContent",
    "GeminiGroundingMetadata",
    "GeminiPart",
    "GeminiPromptFeedback",
    "GeminiRequest",
    "GeminiResponse",
    "GeminiSafetyRating",
    "GeminiUsageMetadata",
]
