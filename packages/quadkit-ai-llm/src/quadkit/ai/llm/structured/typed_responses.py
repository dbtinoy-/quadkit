"""Typed response adapters for structured LLM outputs.

Provides adapters for different response formats: JSON, function calling,
text with optional structured data, audio transcription, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import re

from quadkit.ai.llm.structured.response_types import (
    AudioTranscription,
    FunctionCall,
    ResponseType,
    StructuredData,
    TypedResponse,
)
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization.backends.json import JSONDecodeError, loads

logger = get_logger(__name__)

__all__ = [
    "AbstractResponseTypeAdapter",
    "AudioResponseAdapter",
    "AudioTranscription",
    "FunctionCall",
    "FunctionCallResponseAdapter",
    "JSONResponseAdapter",
    "ResponseType",
    "StructuredData",
    "StructuredResponseAdapter",
    "TextResponseAdapter",
    "TypedResponse",
    "TypedResponseFactory",
]


class AbstractResponseTypeAdapter(ABC):
    """Abstract base for response type adapters.

    Adapters parse LLM responses into structured formats.
    """

    def __init__(self, response_type: ResponseType) -> None:
        """Initialize adapter.

        Args:
            response_type: Type of response to handle
        """
        self.response_type = response_type

    @abstractmethod
    async def parse(self, content: str) -> TypedResponse:
        """Parse response content into typed response.

        Args:
            content: The raw response content

        Returns:
            TypedResponse with parsed payload

        Raises:
            ValueError: If content cannot be parsed as expected type
        """


class TextResponseAdapter(AbstractResponseTypeAdapter):
    """Adapter for plain text responses.

    Simply returns the content as-is with minimal processing.
    """

    def __init__(self) -> None:
        """Initialize text adapter."""
        super().__init__(ResponseType.TEXT)

    async def parse(self, content: str) -> TypedResponse:
        """Parse text response.

        Args:
            content: Plain text content

        Returns:
            TypedResponse with text payload
        """
        logger.debug(
            "text_response_parsed",
            content_length=len(content),
        )

        return TypedResponse(
            response_type=ResponseType.TEXT,
            payload=content,
            raw_content=content,
            parse_success=True,
        )


class JSONResponseAdapter(AbstractResponseTypeAdapter):
    """Adapter for JSON responses.

    Extracts and validates JSON from response text.
    """

    def __init__(self) -> None:
        """Initialize JSON adapter."""
        super().__init__(ResponseType.JSON)

    async def parse(self, content: str) -> TypedResponse:
        """Parse JSON response.

        Args:
            content: Response content (may contain JSON in markdown code block)

        Returns:
            TypedResponse with parsed JSON dict

        Raises:
            ValueError: If JSON is invalid
        """
        # Try to extract JSON from markdown code blocks first
        json_match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # Try to find JSON object using bracket-counting scanner
            from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

            candidates = extract_json_objects(content)
            json_text = candidates[0] if candidates else content

        try:
            parsed = loads(json_text)
            logger.debug(
                "json_response_parsed",
                keys=list(parsed.keys()) if isinstance(parsed, dict) else None,
            )

            return TypedResponse(
                response_type=ResponseType.JSON,
                payload=parsed,
                raw_content=content,
                parse_success=True,
            )

        except JSONDecodeError as e:
            error_type = type(e).__name__
            logger.warning(
                "json_parse_failed",
                error_type=error_type,
            )

            return TypedResponse(
                response_type=ResponseType.JSON,
                payload=None,
                raw_content=content,
                parse_success=False,
                parse_error=f"Invalid JSON response ({error_type})",
            )


class FunctionCallResponseAdapter(AbstractResponseTypeAdapter):
    """Adapter for function call responses.

    Parses function names and arguments from response text.
    """

    def __init__(self) -> None:
        """Initialize function call adapter."""
        super().__init__(ResponseType.FUNCTION_CALL)

    async def parse(self, content: str) -> TypedResponse:
        """Parse function call response.

        Expected format: function_name(arg1=value1, arg2=value2)
        Or JSON format: {"function": "name", "arguments": {...}}

        Args:
            content: Response content

        Returns:
            TypedResponse with FunctionCall payload
        """
        # Try JSON format first
        json_match = re.search(r"\{.*\"function\".*\}", content, re.DOTALL)
        if json_match:
            try:
                data = loads(json_match.group(0))
                func_call = FunctionCall(
                    function_name=data.get("function", ""),
                    arguments=data.get("arguments", {}),
                    raw_content=content,
                )
                logger.debug(
                    "function_call_parsed",
                    function=func_call.function_name,
                )

                return TypedResponse(
                    response_type=ResponseType.FUNCTION_CALL,
                    payload=func_call,
                    raw_content=content,
                    parse_success=True,
                )
            except JSONDecodeError:
                pass

        # Try regex format: function_name(args)
        func_match = re.search(r"(\w+)\s*\((.*?)\)", content)
        if func_match:
            function_name = func_match.group(1)
            args_str = func_match.group(2)

            # Simple argument parsing
            arguments = {}
            if args_str:
                # Parse key=value pairs
                arg_pairs = re.findall(r"(\w+)\s*=\s*([^,]+)", args_str)
                for key, value in arg_pairs:
                    # Try to parse as JSON value
                    try:
                        arguments[key] = loads(value.strip())
                    except (JSONDecodeError, ValueError):
                        arguments[key] = value.strip().strip("'\"")

            func_call = FunctionCall(
                function_name=function_name,
                arguments=arguments,
                raw_content=content,
            )

            logger.debug(
                "function_call_parsed",
                function=function_name,
                args_count=len(arguments),
            )

            return TypedResponse(
                response_type=ResponseType.FUNCTION_CALL,
                payload=func_call,
                raw_content=content,
                parse_success=True,
            )

        # Failed to parse
        logger.warning("function_call_parse_failed", content_length=len(content))

        return TypedResponse(
            response_type=ResponseType.FUNCTION_CALL,
            payload=None,
            raw_content=content,
            parse_success=False,
            parse_error="Could not parse function call format",
        )


class StructuredResponseAdapter(AbstractResponseTypeAdapter):
    """Adapter for structured data responses.

    Handles responses validated against a schema.
    """

    def __init__(self, schema: str | None = None) -> None:
        """Initialize structured response adapter.

        Args:
            schema: Optional schema description or JSON schema
        """
        super().__init__(ResponseType.STRUCTURED)
        self.schema = schema

    async def parse(self, content: str) -> TypedResponse:
        """Parse structured response.

        Args:
            content: Response content

        Returns:
            TypedResponse with StructuredData payload
        """
        # Try to extract JSON first (same as JSONResponseAdapter)
        json_match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
        if json_match:
            json_text: str | None = json_match.group(1)
        else:
            from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

            candidates = extract_json_objects(content)
            json_text = candidates[0] if candidates else None

        if json_text is not None:
            try:
                parsed = loads(json_text)
                structured_data = StructuredData(
                    data=parsed,
                    schema=self.schema,
                    raw_content=content,
                )

                logger.debug(
                    "structured_response_parsed",
                    schema=self.schema,
                )

                return TypedResponse(
                    response_type=ResponseType.STRUCTURED,
                    payload=structured_data,
                    raw_content=content,
                    parse_success=True,
                    metadata={"schema": self.schema} if self.schema else {},
                )

            except JSONDecodeError as e:
                error_type = type(e).__name__
                logger.warning(
                    "structured_parse_failed",
                    error_type=error_type,
                )

                return TypedResponse(
                    response_type=ResponseType.STRUCTURED,
                    payload=None,
                    raw_content=content,
                    parse_success=False,
                    parse_error=f"Invalid structured JSON response ({error_type})",
                    metadata={"schema": self.schema} if self.schema else {},
                )

        # No JSON found
        return TypedResponse(
            response_type=ResponseType.STRUCTURED,
            payload=None,
            raw_content=content,
            parse_success=False,
            parse_error="No JSON structure found in response",
            metadata={"schema": self.schema} if self.schema else {},
        )


class AudioResponseAdapter(AbstractResponseTypeAdapter):
    """Adapter for audio transcription responses.

    Parses audio transcription metadata and content.
    """

    def __init__(self) -> None:
        """Initialize audio adapter."""
        super().__init__(ResponseType.AUDIO)

    async def parse(self, content: str) -> TypedResponse:
        """Parse audio transcription response.

        Args:
            content: Transcription response content

        Returns:
            TypedResponse with AudioTranscription payload
        """
        # Try JSON format first using bracket-counting scanner
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        candidates = extract_json_objects(content)
        if candidates:
            try:
                data = loads(candidates[0])
                transcription = AudioTranscription(
                    text=data.get("text", ""),
                    duration_seconds=data.get("duration_seconds"),
                    language=data.get("language"),
                    confidence=data.get("confidence"),
                    metadata=data.get("metadata", {}),
                )

                logger.debug(
                    "audio_transcription_parsed",
                    duration=transcription.duration_seconds,
                    language=transcription.language,
                )

                return TypedResponse(
                    response_type=ResponseType.AUDIO,
                    payload=transcription,
                    raw_content=content,
                    parse_success=True,
                )

            except JSONDecodeError:
                pass

        # Fallback: treat entire content as transcription text
        transcription = AudioTranscription(text=content.strip())

        logger.debug("audio_transcription_parsed_as_text")

        return TypedResponse(
            response_type=ResponseType.AUDIO,
            payload=transcription,
            raw_content=content,
            parse_success=True,
        )


class TypedResponseFactory:
    """Factory for creating appropriate response adapters."""

    def __init__(self) -> None:
        """Initialize factory."""
        self._adapters = {
            ResponseType.TEXT: TextResponseAdapter(),
            ResponseType.JSON: JSONResponseAdapter(),
            ResponseType.FUNCTION_CALL: FunctionCallResponseAdapter(),
            ResponseType.AUDIO: AudioResponseAdapter(),
        }

    def get_adapter(
        self,
        response_type: ResponseType,
        schema: str | None = None,
    ) -> AbstractResponseTypeAdapter:
        """Get adapter for response type.

        Args:
            response_type: Type of response
            schema: Optional schema for STRUCTURED type

        Returns:
            AbstractResponseTypeAdapter instance
        """
        if response_type == ResponseType.STRUCTURED:
            return StructuredResponseAdapter(schema=schema)

        if response_type not in self._adapters:
            raise ValueError(f"Unknown response type: {response_type}")

        return self._adapters[response_type]

    def register_adapter(
        self,
        response_type: ResponseType,
        adapter: AbstractResponseTypeAdapter,
    ) -> None:
        """Register custom adapter.

        Args:
            response_type: Response type it handles
            adapter: Adapter instance
        """
        self._adapters[response_type] = adapter
        logger.info(
            "typed_response_adapter_registered",
            response_type=response_type.value,
        )
