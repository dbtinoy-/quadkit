"""Utility functions for structured LLM output handling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from quadkit.contracts.ai import LLMClientProtocol
    from quadkit.contracts.core import JSON
    from quadkit.domain import DomainModel

from quadkit.ai.llm.structured.parser import StructuredOutputParser

T = TypeVar("T", bound="DomainModel")


def create_json_mode_messages(
    prompt: str,
    schema: type[DomainModel] | None = None,
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    """Create messages for JSON mode with optional schema.

    Args:
        prompt: User prompt
        schema: Optional Pydantic model for schema
        system_prompt: Optional system prompt (default: JSON instruction)

    Returns:
        Messages list for LLM

    Example:
        >>> messages = create_json_mode_messages(
        ...     "Extract person info",
        ...     schema=Person
        ... )
    """
    # Default JSON system prompt
    if system_prompt is None:
        system_prompt = (
            "You are a helpful assistant that responds in valid JSON format. "
            "Always return properly formatted JSON without any additional text or explanation."
        )

    messages = [{"role": "system", "content": system_prompt}]

    # Add schema if provided
    if schema:
        parser = StructuredOutputParser(schema)
        schema_text = parser.get_schema_prompt()
        prompt = f"{schema_text}\n\n{prompt}"

    messages.append({"role": "user", "content": prompt})

    return messages


async def complete_with_schema(
    client: LLMClientProtocol,
    prompt: str,
    schema: type[T],
    system_prompt: str | None = None,
    **kwargs: Any,
) -> T:
    """Complete with automatic schema parsing and validation.

    Args:
        client: LLM client
        prompt: User prompt
        schema: Pydantic model for validation
        system_prompt: Optional system prompt
        **kwargs: Additional completion arguments

    Returns:
        Validated schema instance

    Example:
        >>> from quadkit.ai.llm import OpenAIClient
        >>>
        >>> client = OpenAIClient(api_key="sk-...")
        >>> person = await complete_with_schema(
        ...     client,
        ...     "Extract person from: John Doe, age 30",
        ...     schema=Person
        ... )
    """
    messages = create_json_mode_messages(prompt, schema, system_prompt)

    result = await client.complete(messages=messages, **kwargs)  # type: ignore[arg-type]
    if result.is_err():
        raise result.unwrap_err()
    completion = result.unwrap()

    parser = StructuredOutputParser(schema)
    return cast("T", parser.parse(completion))


async def complete_with_json(
    client: LLMClientProtocol,
    prompt: str,
    system_prompt: str | None = None,
    **kwargs: Any,
) -> JSON:
    """Complete and parse response as JSON.

    Args:
        client: LLM client
        prompt: User prompt
        system_prompt: Optional system prompt
        **kwargs: Additional completion arguments

    Returns:
        Parsed JSON

    Example:
        >>> data = await complete_with_json(
        ...     client,
        ...     "Generate a config with 3 fields"
        ... )
    """
    from quadkit.ai.llm.structured.formatter import ResponseFormatter

    messages = create_json_mode_messages(prompt, system_prompt=system_prompt)

    result = await client.complete(messages=messages, **kwargs)  # type: ignore[arg-type]
    if result.is_err():
        raise result.unwrap_err()
    completion = result.unwrap()

    return ResponseFormatter.to_json(completion)  # type: ignore[arg-type]
