"""Anthropic request-payload helpers.

Private helpers for building Anthropic API payloads, split out of
``clients.anthropic`` to keep the client module focused on the request
lifecycle (mirrors the ``_bedrock_*`` sibling pattern).
"""

from __future__ import annotations

from typing import Any

from quadkit.ai.llm.clients._message_utils import serialize_content_for_anthropic

__all__ = [
    "_tool_result_text",
    "_tool_to_anthropic",
]


def _tool_to_anthropic(tool: Any) -> dict[str, Any]:
    """Convert a tool descriptor to Anthropic ``tool_use`` format.

    Supports objects that expose a ``__tool_schema__`` class attribute
    (Quadkit tool convention) as well as plain dicts in OpenAI tool format.

    Args:
        tool: A class with ``__tool_schema__``, or a dict with a ``function``
            key in OpenAI tool format.

    Returns:
        Anthropic tool dict with ``name``, ``description``, and
        ``input_schema`` keys.
    """
    if hasattr(tool, "__tool_schema__"):
        schema: dict[str, Any] = tool.__tool_schema__
        return {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "input_schema": schema.get(
                "parameters", {"type": "object", "properties": {}}
            ),
        }
    if isinstance(tool, dict):
        func = tool.get("function", tool)
        return {
            "name": func.get("name", ""),
            "description": func.get("description", ""),
            "input_schema": func.get(
                "parameters", {"type": "object", "properties": {}}
            ),
        }
    return {
        "name": getattr(tool, "name", str(tool)),
        "description": getattr(tool, "description", ""),
        "input_schema": getattr(tool, "parameters", None)
        or {"type": "object", "properties": {}},
    }


def _tool_result_text(content: Any) -> str:
    """Extract plain text from tool-result content.

    Args:
        content: Message content (str or list of content parts).

    Returns:
        Joined text string.
    """
    if isinstance(content, str):
        return content
    blocks = serialize_content_for_anthropic(content)
    return " ".join(str(b.get("text", "")) for b in blocks if b.get("type") == "text")
