"""Output Parser contracts for G-04 parity.

Defines output parsers analogous to LangChain's output parsers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any, cast


class BaseOutputParser(ABC):
    """Base class for output parsers (like LangChain's BaseOutputParser)."""

    @abstractmethod
    def parse(self, text: str) -> Any:
        """Parse text into structured output.

        Args:
            text: Text to parse.

        Returns:
            Parsed output.
        """
        ...

    def get_format_instructions(self) -> str:
        """Get format instructions for the model.

        Returns:
            Format instructions string.
        """
        return ""


class JSONOutputParser(BaseOutputParser):
    """Parse JSON responses (like LangChain's JsonOutputParser)."""

    def parse(self, text: str) -> dict[str, Any]:
        """Parse JSON from text.

        Args:
            text: Text containing JSON.

        Returns:
            Parsed JSON as dict.
        """
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        return cast("dict[str, Any]", json.loads(text))

    def get_format_instructions(self) -> str:
        return "Return a valid JSON object."


class XMLOutputParser(BaseOutputParser):
    """Parse XML responses (like LangChain's XMLOutputParser)."""

    def parse(self, text: str) -> Any:
        """Parse XML from text."""
        return text.strip()

    def get_format_instructions(self) -> str:
        return "Return XML."


class PydanticOutputParser(BaseOutputParser):
    """Parse into Pydantic model (like LangChain's PydanticOutputParser)."""

    def __init__(self, model: type) -> None:
        self.model = model

    def parse(self, text: str) -> Any:
        """Parse text into Pydantic model."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        data = json.loads(text.strip())
        return self.model(**data)

    def get_format_instructions(self) -> str:
        return "Return a valid JSON object."


__all__ = [
    "BaseOutputParser",
    "JSONOutputParser",
    "PydanticOutputParser",
    "XMLOutputParser",
]
