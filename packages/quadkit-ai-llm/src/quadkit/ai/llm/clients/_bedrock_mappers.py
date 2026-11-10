"""Mapping helpers for Bedrock request and response payloads."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.types import (
    Completion,
    FunctionCall,
    StreamChunk,
    ThinkingResult,
    TokenUsage,
    ToolCall,
)
from quadkit.serialization import dumps_str

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from concurrent.futures import ThreadPoolExecutor


def extract_system(messages: list[Any]) -> str:
    """Extract the system prompt from a message list.

    Args:
        messages: OpenAI-compatible message list (dicts or ChatMessage).

    Returns:
        Combined system prompt text, or empty string when absent.
    """
    parts: list[str] = []
    for msg in messages:
        role = (
            msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "role", "")
        )
        role_str = role.value if hasattr(role, "value") else str(role)
        if role_str == "system":
            content = (
                msg.get("content", "")
                if isinstance(msg, dict)
                else getattr(msg, "content", "")
            )
            if isinstance(content, list):
                parts.extend(p.get("text", "") for p in content if isinstance(p, dict))
            else:
                parts.append(str(content))
    return " ".join(parts)


def parse_bedrock_response(raw: dict[str, Any], model: str) -> Completion:
    """Parse a Bedrock ``Converse`` response to a :class:`Completion`.

    Args:
        raw: Raw response dict from ``boto3`` ``converse()``.
        model: Model ID for the ``Completion`` metadata.

    Returns:
        Normalised :class:`~quadkit.ai.llm.types.Completion`.
    """
    output = raw.get("output", {}).get("message", {})
    content_blocks = output.get("content", [])

    text_parts: list[str] = []
    thinking_parts: list[str] = []
    thinking_signature: str | None = None
    tool_calls: list[ToolCall] = []

    for block in content_blocks:
        if "text" in block:
            text_parts.append(block["text"])
        elif "reasoningContent" in block:
            rc = block["reasoningContent"]
            # Bedrock Claude: {reasoningText: {text: "...", signature: "..."}}
            rt = rc.get("reasoningText", {})
            if rt.get("text"):
                thinking_parts.append(rt["text"])
            if rt.get("signature"):
                thinking_signature = rt["signature"]
        elif "toolUse" in block:
            tu = block["toolUse"]
            tool_calls.append(
                ToolCall(
                    id=tu.get("toolUseId", tu.get("name", "")),
                    type="function",
                    function=FunctionCall(
                        name=tu.get("name", ""),
                        arguments=dumps_str(tu.get("input", {})),
                    ),
                )
            )

    usage_raw = raw.get("usage", {})
    usage = TokenUsage(
        prompt_tokens=usage_raw.get("inputTokens", 0),
        completion_tokens=usage_raw.get("outputTokens", 0),
        total_tokens=usage_raw.get("totalTokens", 0),
    )
    thinking_text = "".join(thinking_parts) or None
    thinking: ThinkingResult | None = (
        ThinkingResult(content=thinking_text, signature=thinking_signature)
        if thinking_text
        else None
    )

    return Completion(
        content="".join(text_parts),
        model=model,
        finish_reason=raw.get("stopReason"),
        thinking=thinking,
        usage=usage,
        tool_calls=tool_calls or None,
    )


async def bedrock_stream_chunks(
    raw_stream: Any,
    model: str,
    thread_pool: ThreadPoolExecutor,
) -> AsyncIterator[StreamChunk]:
    """Yield :class:`StreamChunk` objects from a Bedrock ``ConverseStream`` response.

    Bedrock returns an event-stream dict with a ``stream`` key containing an
    iterator of typed event dicts.  Events of type ``contentBlockDelta`` carry
    incremental text in ``delta.text``.

    Args:
        raw_stream: Raw ``converse_stream()`` response from boto3.
        model: Model label for each chunk.

    Yields:
        :class:`StreamChunk` with incremental text deltas.
    """
    stream = raw_stream.get("stream", [])
    loop = asyncio.get_event_loop()
    index = 0

    def _next_event(it: Any) -> Any:
        try:
            return next(it)
        except StopIteration:
            return None

    it = iter(stream)
    while True:
        event = await loop.run_in_executor(thread_pool, _next_event, it)
        if event is None:
            break
        if "contentBlockDelta" in event:
            delta_obj = event["contentBlockDelta"].get("delta", {})
            if "text" in delta_obj:
                yield StreamChunk(
                    delta=delta_obj["text"],
                    model=model,
                    finish_reason=None,
                    index=index,
                )
                index += 1
            elif "reasoningContent" in delta_obj:
                # Bedrock Claude thinking delta
                thinking_text = delta_obj["reasoningContent"].get("text", "")
                if thinking_text:
                    yield StreamChunk(
                        thinking_delta=thinking_text,
                        is_thinking=True,
                        model=model,
                        finish_reason=None,
                        index=index,
                    )
                    index += 1
        elif "messageStop" in event:
            stop_reason = event["messageStop"].get("stopReason")
            yield StreamChunk(
                delta="", model=model, finish_reason=stop_reason, index=index
            )
            break


def tool_to_bedrock(tool: Any) -> dict[str, Any]:
    """Convert a tool descriptor to Bedrock ``ToolSpec`` format.

    Args:
        tool: A class with ``__tool_schema__``, or a dict in OpenAI tool format.

    Returns:
        Bedrock ``ToolSpec`` dict wrapped in a ``{"toolSpec": {...}}`` envelope.
    """
    if hasattr(tool, "__tool_schema__"):
        schema: dict[str, Any] = tool.__tool_schema__
        return {
            "toolSpec": {
                "name": schema["name"],
                "description": schema.get("description", ""),
                "inputSchema": {"json": schema.get("parameters", {})},
            }
        }
    if isinstance(tool, dict):
        func = tool.get("function", tool)
        return {
            "toolSpec": {
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "inputSchema": {"json": func.get("parameters", {})},
            }
        }
    return {
        "toolSpec": {
            "name": getattr(tool, "name", str(tool)),
            "description": getattr(tool, "description", ""),
            "inputSchema": {
                "json": getattr(tool, "parameters", None)
                or {
                    "type": "object",
                    "properties": {},
                }
            },
        }
    }
