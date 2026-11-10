"""Typed response value types for structured LLM outputs.

Response-type enum and frozen payload containers shared by the response
adapters and the :class:`~quadkit.ai.llm.structured.typed_responses.TypedResponseFactory`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "AudioTranscription",
    "FunctionCall",
    "ResponseType",
    "StructuredData",
    "TypedResponse",
]


class ResponseType(StrEnum):
    """Types of structured responses supported."""

    TEXT = "text"
    JSON = "json"
    FUNCTION_CALL = "function_call"
    STRUCTURED = "structured"
    AUDIO = "audio"


@dataclass(frozen=True)
class FunctionCall:
    """Represents a function call response.

    Attributes:
        function_name: Name of the function to call
        arguments: Dict of argument name to value
        raw_content: Original response text before parsing
    """

    function_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_content: str = ""


@dataclass(frozen=True)
class StructuredData:
    """Container for structured response data.

    Attributes:
        data: The parsed structured data (dict or any type)
        schema: Optional schema or format description
        raw_content: Original response text before parsing
    """

    data: Any
    schema: str | None = None
    raw_content: str = ""


@dataclass(frozen=True)
class AudioTranscription:
    """Container for audio transcription response.

    Attributes:
        text: Transcribed text
        duration_seconds: Duration of audio file
        language: Detected language code
        confidence: Confidence score for transcription
        metadata: Additional transcription metadata
    """

    text: str
    duration_seconds: float | None = None
    language: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TypedResponse:
    """Response with type information and payload.

    Attributes:
        response_type: Type of response
        payload: The typed response payload (could be dict, FunctionCall, etc.)
        raw_content: Original response text
        metadata: Additional metadata
        parse_success: Whether parsing succeeded
        parse_error: Error message if parsing failed
    """

    response_type: ResponseType
    payload: Any
    raw_content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    parse_success: bool = True
    parse_error: str | None = None
