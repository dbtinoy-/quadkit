"""Request-side mapping helpers for the Bedrock ``Converse`` API.

Builds the ``converse`` / ``converse_stream`` request payloads from
OpenAI-compatible message lists, including extended-thinking injection
and tool-spec conversion. Response parsing lives in
:mod:`quadkit.ai.llm.clients._bedrock_mappers`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.clients._bedrock_mappers import extract_system, tool_to_bedrock
from quadkit.ai.llm.clients._tools_utils import _tool_schema_fields

if TYPE_CHECKING:
    from quadkit.contracts.ai.thinking import ThinkingConfig

__all__ = ["apply_thinking", "build_converse_request", "content_to_text"]


def content_to_text(content: Any) -> str:
    """Extract plain text from message content for tool-result payloads.

    Args:
        content: Message content (string or list of content parts).

    Returns:
        Plain text string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(p.get("text", ""))
            for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        )
    return str(content)


def apply_thinking(thinking: ThinkingConfig | None, request: dict[str, Any]) -> None:
    """Inject Bedrock extended-thinking parameters into the request payload.

    Sets ``additionalModelRequestFields.thinking`` when a thinking config is
    given. Also removes ``temperature`` from ``inferenceConfig`` because
    Bedrock Claude rejects that combination.

    Args:
        thinking: Extended-thinking configuration, or ``None`` to skip.
        request: Mutable Bedrock request dict.
    """
    if thinking is None:
        return
    request["additionalModelRequestFields"] = {
        "thinking": {
            "type": "enabled",
            "budget_tokens": thinking.budget_tokens,
        }
    }
    request.get("inferenceConfig", {}).pop("temperature", None)


def build_converse_request(
    *,
    model: str,
    bedrock_messages: list[dict[str, Any]],
    messages: list[Any],
    temperature: float,
    max_tokens: int | None,
    thinking: ThinkingConfig | None,
    tools: list[Any] | None = None,
) -> dict[str, Any]:
    """Build a Bedrock ``Converse`` request payload.

    Args:
        model: Bedrock model ARN or ID.
        bedrock_messages: Messages already converted to Bedrock format.
        messages: Original OpenAI-compatible messages (for system extraction).
        temperature: Sampling temperature (ignored with extended thinking).
        max_tokens: Maximum output tokens.
        thinking: Extended-thinking configuration, or ``None``.
        tools: Optional tool descriptors to advertise via ``toolConfig``.

    Returns:
        Bedrock ``Converse`` request dict.
    """
    request: dict[str, Any] = {
        "modelId": model,
        "messages": bedrock_messages,
        "inferenceConfig": {},
    }
    # Extended thinking is incompatible with temperature on Bedrock Claude
    apply_thinking(thinking, request)
    if "additionalModelRequestFields" not in request:
        request["inferenceConfig"]["temperature"] = temperature

    if max_tokens is not None:
        request["inferenceConfig"]["maxTokens"] = max_tokens

    system = extract_system(messages)
    if system:
        request["system"] = [{"text": system}]

    if tools:
        converted_tools = [
            tool_to_bedrock(t) for t in tools if _tool_schema_fields(t)[0]
        ]
        if converted_tools:
            request["toolConfig"] = {
                "tools": converted_tools,
                "toolChoice": {"auto": {}},
            }
    return request
