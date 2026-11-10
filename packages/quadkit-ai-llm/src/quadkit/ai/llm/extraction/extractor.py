"""Structured extraction using the instructor library.

This module provides `InstructorExtractor` for extracting typed Pydantic models
from LLM completions. It uses the standard instructor library approach but
avoids coupling to provider-specific client patching by using the generic
`LLMClientProtocol.complete()` method.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import ValidationError

from quadkit.ai.llm.exceptions import (
    ExtractionError,
    ExtractionMaxRetriesError,
    ExtractionParseError,
    ExtractionValidationError,
)
from quadkit.contracts.ai.llm import (
    ChatMessage,
    LLMClientProtocol,
    Role,
)
from quadkit.logging import get_logger, safe_error_type
from quadkit.result import Err, Ok, Result
from quadkit.serialization import JSONDecodeError, loads

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = get_logger(__name__)

T = TypeVar("T", bound="BaseModel")


class InstructorExtractor:
    """Structured extraction from LLM completions using instructor library.

    Extracts typed Pydantic models from LLM responses by:
    1. Building a ChatMessage list with extraction instructions
    2. Calling llm_client.complete() to get a Completion
    3. Parsing the completion text as JSON
    4. Validating against the response_model
    5. Retrying on validation/parse failures up to max_retries

    Unlike direct instructor usage, this implementation uses the standard
    `LLMClientProtocol.complete()` method, avoiding coupling to provider-specific
    client patching mechanisms.

    Example::

        from pydantic import BaseModel

        class UserInfo(BaseModel):
            name: str
            age: int

        extractor = InstructorExtractor(llm_client)
        result = await extractor.extract(
            prompt="Extract user info from: 'John is 30 years old'",
            response_model=UserInfo,
        )
        if result.is_ok():
            user = result.unwrap()
            print(user.name, user.age)
        else:
            error = result.unwrap_err()
            # handle ExtractionError
    """

    def __init__(
        self,
        llm_client: LLMClientProtocol,
        mode: str = "json",
        max_retries: int = 3,
    ) -> None:
        """Initialize InstructorExtractor.

        Args:
            llm_client: LLMClientProtocol instance for making LLM calls.
            mode: Instructor patching mode (reserved for future provider-level
                  integration; currently unused).
            max_retries: Maximum number of retries on validation/parse failure.
        """
        self.llm_client = llm_client
        self.mode = mode
        self.max_retries = max_retries

    async def extract(
        self,
        prompt: str,
        response_model: type[T],
        context: list | None = None,
        **kwargs: Any,
    ) -> Result[T, ExtractionError]:
        """Extract a structured response_model instance from an LLM call.

        Args:
            prompt: User prompt for extraction.
            response_model: Pydantic BaseModel class to extract and validate.
            context: Optional list of additional ChatMessage objects for context.
            **kwargs: Additional parameters passed to llm_client.complete().

        Returns:
            ``Ok(instance)`` on successful extraction and validation.
            ``Err(ExtractionError)`` on parse, validation, or max retries failure.

        Raises:
            Infrastructure exceptions (network errors, timeouts, etc.) from
            llm_client.complete() propagate naturally and are not caught.
        """
        # Build the messages list: optional context + user prompt
        messages: list[ChatMessage] = []

        if context:
            messages.extend(context)

        messages.append(ChatMessage(role=Role.USER, content=prompt))

        # Retry loop for extraction
        last_error: ExtractionError | None = None

        for attempt in range(self.max_retries):
            # Call LLM client to get completion
            # Infrastructure errors (network, auth, etc.) propagate naturally
            completion_result = await self.llm_client.complete(
                messages,
                **kwargs,
            )

            # Handle LLM error
            if completion_result.is_ok():
                completion = completion_result.unwrap()
            else:
                llm_error = completion_result.unwrap_err()
                error_type = safe_error_type(llm_error)
                logger.warning(
                    "extraction_llm_error",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    error_type=error_type,
                )
                # Convert LLM error to an extraction error without provider text.
                last_error = ExtractionError(
                    f"LLM call failed on attempt {attempt + 1}",
                    details={"error_type": error_type},
                )
                continue
            completion_text = completion.content

            # Try to parse JSON from completion text
            try:
                parsed_data = loads(completion_text)
            except JSONDecodeError as exc:
                error_type = safe_error_type(exc)
                logger.warning(
                    "extraction_parse_error",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    error_type=error_type,
                )
                last_error = ExtractionParseError(
                    f"Failed to parse JSON on attempt {attempt + 1}",
                    details={"error_type": error_type},
                )
                continue

            # Try to validate against response_model
            try:
                instance = response_model.model_validate(parsed_data)
                logger.info(
                    "extraction_success",
                    attempt=attempt + 1,
                )
                return Ok(instance)
            except ValidationError as exc:
                error_type = safe_error_type(exc)
                logger.warning(
                    "extraction_validation_error",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    error_type=error_type,
                )
                last_error = ExtractionValidationError(
                    f"Validation failed on attempt {attempt + 1}",
                    details={"error_type": error_type},
                )
                continue

        # All retries exhausted
        last_error_type = safe_error_type(last_error) if last_error else "UnknownError"
        logger.error(
            "extraction_max_retries_exceeded",
            max_retries=self.max_retries,
            last_error_type=last_error_type,
        )
        return Err(
            ExtractionMaxRetriesError(
                f"Failed after {self.max_retries} retries",
                details={"last_error_type": last_error_type},
            )
        )
