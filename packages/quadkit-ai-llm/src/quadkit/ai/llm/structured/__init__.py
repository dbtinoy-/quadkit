"""Structured output extraction from LLM responses.

Public API
----------
StructuredExtractor:
    Core class — wraps an LLM client and extracts validated, typed objects.

    Example::

        from quadkit.ai.llm.structured import StructuredExtractor
        from pydantic import BaseModel

        class Reply(BaseModel):
            summary: str
            confidence: float

        extractor = StructuredExtractor(llm_client)
        result = await extractor.extract(
            prompt="Summarise this ticket.",
            output_model=Reply,
        )

Parser helpers (advanced / testing use):
    extract_json_block:   Pull JSON out of raw LLM output (strips fences, etc.)
    validate_against_model:  Validate a dict against a Pydantic / dataclass model.
    build_json_schema:    Generate a JSON Schema dict from a model class.
"""

from __future__ import annotations

from quadkit.ai.llm.structured.extractor import StructuredExtractor
from quadkit.ai.llm.structured.parser import (
    build_json_schema,
    extract_json_block,
    validate_against_model,
)

__all__ = [
    "StructuredExtractor",
    "build_json_schema",
    "extract_json_block",
    "validate_against_model",
]
