"""Format Fixing Parser with retry budget."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from quadkit.ai.llm.structured.exceptions import ParseError
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

T = TypeVar("T")


class FormatFixingParser:
    """Parser that retries with LLM-assisted fixing on parse failure.

    Wraps a base parser and, on parse failure, calls the LLM with a fixing
    prompt that includes the original output and the parse error. Retries
    are bounded by the retry_budget.

    Example:
        >>> parser = FormatFixingParser(
        ...     base_parser=JSONOutputParser(),
        ...     llm_client=llm_client,
        ...     retry_budget=3
        ... )
        >>> result = parser.parse('not valid json')
    """

    def __init__(
        self,
        base_parser: Any,
        llm_client: Any,
        *,
        retry_budget: int = 3,
        guard_check: Callable[[str], bool] | None = None,
    ) -> None:
        """Initialize the format fixing parser.

        Args:
            base_parser: The underlying parser to use for parsing.
            llm_client: LLM client to use for fixing attempts.
            retry_budget: Maximum number of fix attempts (default 3).
            guard_check: Optional guard function to validate malformed input
                before sending to LLM. Should return True if safe.
        """
        self._base_parser = base_parser
        self._llm_client = llm_client
        self._retry_budget = retry_budget
        self._guard_check = guard_check

    async def parse(self, text: str) -> Any:
        """Parse text, attempting fixes on failure.

        Args:
            text: Raw LLM response text to parse.

        Returns:
            Parsed output from the base parser.

        Raises:
            ParseError: When all fix attempts fail or guard check fails.
        """
        attempt = 0
        last_error: ParseError | None = None
        current_text = text

        while attempt <= self._retry_budget:
            try:
                return self._base_parser.parse(current_text)
            except ParseError as exc:
                last_error = exc
                attempt += 1

                error_type = type(exc).__name__
                if attempt > self._retry_budget:
                    logger.warning(
                        "format_fixing_exhausted",
                        attempts=attempt,
                        error_type=error_type,
                    )
                    break

                logger.debug(
                    "format_fixing_attempt",
                    attempt=attempt,
                    error_type=error_type,
                )

                safe_error_message = f"Output could not be parsed ({error_type})"
                current_text = await self._fix_with_llm(
                    current_text,
                    safe_error_message,
                )

        if last_error is not None:
            raise ParseError(
                "Format fixing failed after exhausting retries",
                details={"error_type": type(last_error).__name__},
            ) from None
        raise ParseError("Format fixing failed with no error recorded")

    async def _fix_with_llm(self, original_output: str, error_message: str) -> str:
        """Call LLM to fix the malformed output.

        Args:
            original_output: The original malformed output.
            error_message: The parse error message.

        Returns:
            Fixed output from the LLM.

        Raises:
            ParseError: When the LLM call fails.
        """
        if self._guard_check is not None:
            if not self._guard_check(original_output):
                raise ParseError(
                    "Guard check failed: input flagged as potentially unsafe"
                )

        fixing_prompt = self._build_fixing_prompt(original_output, error_message)

        try:
            response = await self._llm_client.complete(
                messages=[{"role": "user", "content": fixing_prompt}]
            )
            fixed = response.content if hasattr(response, "content") else str(response)
            logger.debug("format_fixing_llm_response", length=len(fixed))
            return fixed
        except Exception as exc:
            error_type = type(exc).__name__
            raise ParseError(
                "LLM fix call failed",
                details={"error_type": error_type},
            ) from None

    def _build_fixing_prompt(self, original_output: str, error_message: str) -> str:
        """Build the prompt for the LLM to fix the output.

        Args:
            original_output: The original malformed output.
            error_message: The parse error message.

        Returns:
            The complete prompt to send to the LLM.
        """
        return f"""The following output failed to parse:

Original output:
```
{original_output}
```

Parse error:
{error_message}

Please fix the output so it can be parsed correctly. Return only the fixed output, no explanations."""

    def get_format_instructions(self) -> str:
        """Return format instructions from the base parser.

        Returns:
            Format instructions from the wrapped parser.
        """
        if hasattr(self._base_parser, "get_format_instructions"):
            return str(self._base_parser.get_format_instructions())
        return ""


__all__ = ["FormatFixingParser"]
