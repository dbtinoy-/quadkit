"""Enum Output Parser."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from quadkit.ai.llm.structured.exceptions import ParseError
from quadkit.ai.llm.structured.parser import extract_json_block
from quadkit.logging import (
    get_logger,
    safe_error_type,
)

if TYPE_CHECKING:
    from typing import TypeVar

    T = TypeVar("T", bound=Enum)
else:
    T = None

logger = get_logger(__name__)


class EnumOutputParser:
    """Parse LLM responses into Enum members.

    Extracts JSON from the response and maps it to an Enum member.
    Supports both string values and integer values.

    Example:
        >>> from enum import Enum
        >>>
        >>> class Status(Enum):
        ...     ACTIVE = "active"
        ...     INACTIVE = "inactive"
        >>>
        >>> parser = EnumOutputParser(Status)
        >>> result = parser.parse('"active"')
        >>> assert result == Status.ACTIVE
    """

    def __init__(self, enum: type[Enum]) -> None:
        """Initialize with an Enum class.

        Args:
            enum: Enum subclass to parse into.
        """
        self._enum = enum

    def parse(self, text: str) -> Enum:
        """Parse text into an Enum member.

        Args:
            text: Raw LLM response text that may contain JSON with enum value.

        Returns:
            Corresponding Enum member.

        Raises:
            ParseError: When JSON cannot be extracted or enum value is invalid.
        """
        try:
            parsed = extract_json_block(text)
        except ValueError as exc:
            raise ParseError(
                f"Invalid JSON response ({safe_error_type(exc)})"
            ) from None

        if not isinstance(parsed, (str, int)):
            raise ParseError(
                f"Expected string or int for enum, got {type(parsed).__name__}"
            )

        error_type: str | None = None
        try:
            result = self._enum(parsed)
        except ValueError as exc:
            error_type = type(exc).__name__

        if error_type is not None:
            raise ParseError(
                "Invalid enum value",
                details={"error_type": error_type},
            ) from None
        return result

    def get_format_instructions(self) -> str:
        """Return format instructions for the LLM.

        Returns:
            Format instruction string telling the model to output a valid
            enum value.
        """
        valid_values = [e.value for e in self._enum]
        values_str = ", ".join(repr(v) for v in valid_values)
        return (
            f"Your response should be one of: {values_str}. "
            "Return just the value, not a JSON object. "
            "Do not include any text before or after the value."
        )


__all__ = ["EnumOutputParser"]
