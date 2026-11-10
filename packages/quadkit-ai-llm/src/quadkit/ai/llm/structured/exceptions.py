"""Exceptions for structured output handling."""

from __future__ import annotations

from quadkit.ai.llm.exceptions import ExtractionError


class StructuredOutputError(ExtractionError):
    """Base exception for structured output errors."""

    CODE = "AI_STRUCTURED_OUTPUT_ERROR"
    _code: str = "QK_ERR_LLM_027"


class ParseError(StructuredOutputError):
    """Raised when response cannot be parsed."""

    CODE = "AI_PARSE_ERROR"
    _code: str = "QK_ERR_LLM_028"


class SchemaValidationError(StructuredOutputError):
    """Raised when parsed response fails validation."""

    CODE = "AI_SCHEMA_VALIDATION_ERROR"
    _code: str = "QK_ERR_LLM_019"
