"""Model Output Parser (supports QuadKit DomainModel and Pydantic BaseModel)."""

from __future__ import annotations

from typing import Generic, TypeVar, cast

from quadkit.ai.llm.structured.exceptions import ParseError, SchemaValidationError
from quadkit.ai.llm.structured.parser import (
    extract_json_block,
    validate_against_model,
)
from quadkit.logging import get_logger

logger = get_logger(__name__)

TModel = TypeVar("TModel")


class PydanticOutputParser(Generic[TModel]):
    """Parse LLM JSON responses into typed ``DomainModel`` or Pydantic models."""

    def __init__(self, model: type[TModel]) -> None:
        self._model = model

    def parse(self, text: str) -> TModel:
        """Parse text into a validated model instance."""
        parse_error_type: str | None = None
        try:
            parsed = extract_json_block(text)
        except ValueError as exc:
            parse_error_type = type(exc).__name__

        if parse_error_type is not None:
            raise ParseError(
                "Invalid JSON response",
                details={"error_type": parse_error_type},
            ) from None

        validation_error_type: str | None = None
        try:
            validated = validate_against_model(parsed, self._model)
        except (TypeError, ValueError) as exc:
            validation_error_type = type(exc).__name__
        else:
            return cast("TModel", validated)

        raise SchemaValidationError(
            "Model validation failed",
            details={"error_type": validation_error_type},
        ) from None

    def get_format_instructions(self) -> str:
        """Return format instructions derived from ``model_json_schema()``."""
        from quadkit.serialization import dumps_str

        model_schema_fn = getattr(self._model, "model_json_schema", None)
        schema = model_schema_fn() if callable(model_schema_fn) else {"type": "object"}
        schema_str = dumps_str(schema, indent=2)
        return (
            f"Your response should be a valid JSON object matching this schema:\n\n"
            f"{schema_str}\n\n"
            "Do not include any text before or after the JSON. "
            "Do not use markdown code fences."
        )


DomainModelOutputParser = PydanticOutputParser

__all__ = ["DomainModelOutputParser", "PydanticOutputParser"]
