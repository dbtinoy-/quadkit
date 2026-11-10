"""Response formatting utilities for LLM outputs."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from quadkit.ai.llm.types import Completion
    from quadkit.contracts.core import JSON

from quadkit.ai.llm.structured.exceptions import ParseError
from quadkit.ai.llm.structured.extractor import JSONExtractor


class ResponseFormatter:
    """Format and convert LLM responses to various types.

    Example:
        >>> formatter = ResponseFormatter()
        >>> completion = Completion(content="42", ...)
        >>> num = formatter.to_int(completion)
        >>> print(num)
        42
    """

    @staticmethod
    def to_json(completion: Completion) -> JSON:
        """Convert response to JSON.

        Args:
            completion: LLM completion

        Returns:
            Parsed JSON

        Example:
            >>> data = formatter.to_json(completion)
        """
        data = JSONExtractor.extract(completion.content)
        # If the extractor returned an array, return the first object for callers that
        # expect a JSON object (this is a best-effort convenience behavior).
        if isinstance(data, list):
            if not data:
                msg = "Expected JSON object, got empty array"
                raise ParseError(msg)
            if not isinstance(data[0], dict):
                msg = f"Expected JSON object, got array of {type(data[0])}"
                raise ParseError(msg)
            return cast("dict[str, Any]", data[0])
        return cast("dict[str, Any]", data)

    @staticmethod
    def to_string(completion: Completion, strip: bool = True) -> str:
        """Convert response to string.

        Args:
            completion: LLM completion
            strip: Whether to strip whitespace

        Returns:
            Response string

        Example:
            >>> text = formatter.to_string(completion)
        """
        content = completion.content
        return content.strip() if strip else content

    @staticmethod
    def to_int(completion: Completion) -> int:
        """Convert response to integer.

        Args:
            completion: LLM completion

        Returns:
            Parsed integer

        Raises:
            ParseError: If conversion fails

        Example:
            >>> num = formatter.to_int(completion)
        """
        content = completion.content.strip()

        # Try direct conversion
        try:
            return int(content)
        except ValueError:
            pass

        # Try extracting number from text
        numbers = re.findall(r"-?\d+", content)
        if numbers:
            return int(numbers[0])

        msg = f"Cannot convert to int: {content}"
        raise ParseError(msg)

    @staticmethod
    def to_float(completion: Completion) -> float:
        """Convert response to float.

        Args:
            completion: LLM completion

        Returns:
            Parsed float

        Raises:
            ParseError: If conversion fails

        Example:
            >>> num = formatter.to_float(completion)
        """
        content = completion.content.strip()

        # Try direct conversion
        try:
            return float(content)
        except ValueError:
            pass

        # Try extracting number from text
        numbers = re.findall(r"-?\d+\.?\d*", content)
        if numbers:
            return float(numbers[0])

        msg = f"Cannot convert to float: {content}"
        raise ParseError(msg)

    @staticmethod
    def to_bool(completion: Completion) -> bool:
        """Convert response to boolean.

        Args:
            completion: LLM completion

        Returns:
            Parsed boolean

        Example:
            >>> result = formatter.to_bool(completion)
        """
        content = completion.content.strip().lower()

        # Check common boolean representations
        if content in ("true", "yes", "1", "y", "correct", "affirmative"):
            return True
        if content in ("false", "no", "0", "n", "incorrect", "negative"):
            return False

        msg = f"Cannot convert to bool: {content}"
        raise ParseError(msg)

    @staticmethod
    def to_list(completion: Completion, separator: str = "\n") -> list[str]:
        """Convert response to list of strings.

        Args:
            completion: LLM completion
            separator: String separator (default: newline)

        Returns:
            List of strings

        Example:
            >>> items = formatter.to_list(completion)
        """
        content = completion.content.strip()

        # Try parsing as JSON array first
        try:
            result = JSONExtractor.extract(content)
            if isinstance(result, list):
                return list(map(str, result))
        except ParseError:
            pass

        # Split by separator and clean up
        items = content.split(separator)
        return list(map(str.strip, filter(str.strip, items)))
