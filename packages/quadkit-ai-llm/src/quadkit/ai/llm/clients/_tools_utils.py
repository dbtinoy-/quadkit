"""Shared tool-calling helpers for LLM clients.

Utilities to convert tool descriptors (``ToolDefinition``, classes
exposing ``__tool_schema__``, or OpenAI-format dicts) into provider wire
formats, parse provider ``tool_calls`` responses back into framework
:class:`ToolCall` objects, and serialize assistant tool-call / tool-result
messages for multi-turn round trips.

The OpenAI-compatible helpers are reused by every provider whose API follows
the OpenAI chat-completions shape (OpenAI, Azure, Groq, Mistral, OpenRouter,
Cloudflare Workers AI, and the OpenAI-compatible family).
"""

from __future__ import annotations

from typing import Any

from quadkit.ai.llm.clients._message_utils import serialize_content_for_openai
from quadkit.ai.llm.types import ChatMessage, FunctionCall, ToolCall
from quadkit.serialization import dumps_str, loads_str


def _tool_schema_fields(tool: Any) -> tuple[str | None, str, dict[str, Any]]:
    """Extract ``(name, description, parameters)`` from a tool descriptor.

    Supports objects exposing a ``__tool_schema__`` class attribute (the
    Quadkit tool registration convention), ``ToolDefinition`` duck types
    (``name``/``description``/``parameters`` attributes), and OpenAI-format
    dicts (``{"function": {"name", "description", "parameters"}}``).

    Args:
        tool: Any tool descriptor.

    Returns:
        Tuple of (name, description, parameters).  ``name`` is ``None`` when
        the descriptor has no usable name.
    """
    schema = getattr(tool, "__tool_schema__", None)
    if isinstance(schema, dict) and schema.get("name"):
        return (
            str(schema["name"]),
            str(schema.get("description", "") or ""),
            dict(schema.get("parameters", {}) or {}),
        )
    if isinstance(tool, dict):
        func = tool.get("function", tool)
        if isinstance(func, dict):
            name = func.get("name")
            return (
                str(name) if name else None,
                str(func.get("description", "") or ""),
                dict(func.get("parameters", {}) or {}),
            )
    name = getattr(tool, "name", None)
    return (
        str(name) if name else None,
        str(getattr(tool, "description", "") or ""),
        dict(getattr(tool, "parameters", {}) or {}),
    )


def tool_to_openai_format(tool: Any) -> dict[str, Any] | None:
    """Convert a tool descriptor to OpenAI ``tools`` wire format.

    Args:
        tool: Tool descriptor (``ToolDefinition``, schema class, or dict).

    Returns:
        OpenAI tool dict (``{"type": "function", "function": {...}}``), or
        ``None`` when the descriptor has no usable name.
    """
    name, description, parameters = _tool_schema_fields(tool)
    if not name:
        return None
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def serialize_openai_tool_calls(
    tool_calls: list[ToolCall] | None,
) -> list[dict[str, Any]] | None:
    """Serialize framework ``ToolCall``s to OpenAI ``tool_calls`` wire format.

    Used to re-emit an assistant turn that requested tools before the
    matching ``tool`` role responses.

    Args:
        tool_calls: Framework tool calls from a prior assistant turn.

    Returns:
        OpenAI ``tool_calls`` dicts, or ``None`` when empty.
    """
    if not tool_calls:
        return None
    serialized: list[dict[str, Any]] = []
    for call in tool_calls:
        if call.function is None:
            continue
        arguments = call.function.arguments
        serialized.append(
            {
                "id": call.id,
                "type": call.type or "function",
                "function": {
                    "name": call.function.name,
                    "arguments": (
                        arguments
                        if isinstance(arguments, str)
                        else dumps_str(arguments)
                    ),
                },
            }
        )
    return serialized or None


def serialize_message_for_openai(msg: ChatMessage) -> dict[str, Any]:
    """Convert a ``ChatMessage`` to OpenAI message wire format.

    Includes ``name``, ``tool_call_id`` (tool results), and ``tool_calls``
    (assistant turns that requested tools) so multi-turn tool conversations
    round-trip correctly.

    Args:
        msg: Chat message to convert.

    Returns:
        OpenAI message dict.
    """
    result: dict[str, Any] = {
        "role": msg.role.value if hasattr(msg.role, "value") else msg.role,
        "content": serialize_content_for_openai(msg.content),
    }
    if msg.name:
        result["name"] = msg.name
    if msg.tool_call_id:
        result["tool_call_id"] = msg.tool_call_id
    tool_calls = serialize_openai_tool_calls(msg.tool_calls)
    if tool_calls:
        if not msg.content:
            result["content"] = None
        result["tool_calls"] = tool_calls
    return result


def _attr_or_key(obj: Any, key: str) -> Any:
    """Read ``key`` from a dict or via attribute access (SDK objects)."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def parse_openai_tool_calls(raw: Any) -> list[ToolCall] | None:
    """Parse OpenAI-format ``tool_calls`` into framework ``ToolCall`` objects.

    Accepts the OpenAI SDK response objects (``choice.message.tool_calls``)
    as well as plain dicts from OpenAI-compatible REST providers.

    Args:
        raw: List of tool call dicts or SDK objects (``None`` when absent).

    Returns:
        List of :class:`ToolCall` objects, or ``None`` when empty.
    """
    if not raw:
        return None
    calls: list[ToolCall] = []
    for call in raw:
        fn = _attr_or_key(call, "function") or {}
        calls.append(
            ToolCall(
                id=str(_attr_or_key(call, "id") or ""),
                type=str(_attr_or_key(call, "type") or "function"),
                function=FunctionCall(
                    name=str(_attr_or_key(fn, "name") or ""),
                    arguments=_attr_or_key(fn, "arguments") or "",
                ),
            )
        )
    return calls or None


def parse_json_arguments(arguments: Any) -> dict[str, Any]:
    """Parse ``function.arguments`` (string or dict) into a plain dict.

    Args:
        arguments: JSON-encoded string or dict from a provider response.

    Returns:
        Plain argument dict (``{}`` when unparseable).
    """
    if isinstance(arguments, dict):
        return dict(arguments)
    if isinstance(arguments, str):
        try:
            parsed = loads_str(arguments)
        except (TypeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}
