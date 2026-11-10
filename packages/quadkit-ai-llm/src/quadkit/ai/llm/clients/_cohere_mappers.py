"""Mapping helpers for Cohere request payloads and tool schemas."""

from __future__ import annotations

from typing import Any

from quadkit.ai.llm.clients._message_utils import serialize_text_only
from quadkit.ai.llm.clients._tools_utils import parse_json_arguments
from quadkit.ai.llm.http.client import ResilientHTTPClient
from quadkit.ai.llm.types import ChatMessage


def build_cohere_payload(
    *,
    client: ResilientHTTPClient,
    messages: list[ChatMessage] | list[dict[str, Any]],
    stream: bool,
    kwargs: dict[str, Any],
    default_model: str,
    logger: Any,
) -> tuple[ResilientHTTPClient, dict[str, Any], str]:
    """Build the Cohere API request payload from message history."""
    request_kwargs = kwargs.copy()
    model = request_kwargs.pop("model", None) or default_model
    temperature = request_kwargs.pop("temperature", 0.7)
    max_tokens = request_kwargs.pop("max_tokens", None)
    tools = request_kwargs.pop("tools", None)
    documents = request_kwargs.pop("documents", None)

    user_message = ""
    chat_history: list[dict[str, Any]] = []
    preamble: str | None = None
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            tool_call_id = msg.get("tool_call_id", "")
            tool_calls = msg.get("tool_calls", [])
        else:
            role = msg.role.value
            content = msg.content
            tool_call_id = msg.tool_call_id
            tool_calls = msg.tool_calls

        text_content = serialize_text_only(
            content,
            logger=logger,
            client_name="cohere",
        )
        if role == "system":
            preamble = text_content
        elif role == "tool":
            # Tool results are sent as a USER turn carrying tool_results
            chat_history.append(
                {
                    "role": "USER",
                    "message": text_content,
                    "tool_results": [
                        {
                            "call": {"name": tool_call_id or "", "parameters": {}},
                            "outputs": [{"tool_result": text_content}],
                        }
                    ],
                }
            )
        elif role == "user":
            user_message = text_content
        elif role == "assistant":
            if chat_history and user_message:
                chat_history.append({"role": "USER", "message": user_message})
                user_message = ""
            entry: dict[str, Any] = {"role": "CHATBOT", "message": text_content}
            serialized_calls = _cohere_assistant_tool_calls(tool_calls)
            if serialized_calls:
                entry["tool_calls"] = serialized_calls
            chat_history.append(entry)

    payload: dict[str, Any] = {
        "model": model,
        "message": user_message,
        "temperature": temperature,
        "stream": stream,
        **request_kwargs,
    }
    if preamble is not None:
        payload["preamble"] = preamble
    if chat_history:
        payload["chat_history"] = chat_history
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if tools:
        payload["tools"] = map_cohere_tools(tools)
    if documents:
        payload["documents"] = documents

    return client, payload, model


def _cohere_assistant_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    """Serialize assistant tool calls to Cohere ``tool_calls`` wire format.

    Args:
        tool_calls: Framework tool calls from a prior assistant turn.

    Returns:
        Cohere tool-call dicts (``{"name", "parameters"}``).
    """
    serialized: list[dict[str, Any]] = []
    for call in tool_calls or []:
        fn = getattr(call, "function", None)
        if fn is None or not getattr(fn, "name", None):
            continue
        serialized.append(
            {
                "name": fn.name,
                "parameters": parse_json_arguments(fn.arguments),
            }
        )
    return serialized


def map_cohere_tools(tools: list[Any]) -> list[dict[str, Any]]:
    """Convert Quadkit tool definitions into Cohere tool schema format."""
    cohere_tools: list[dict[str, Any]] = []
    for tool in tools:
        if isinstance(tool, dict):
            cohere_tools.append(tool)
            continue
        fn = getattr(tool, "function", tool)
        name: str = getattr(fn, "name", "") or ""
        description: str = getattr(fn, "description", "") or ""
        schema: dict[str, Any] = getattr(fn, "parameters", {}) or {}
        properties: dict[str, Any] = schema.get("properties", {})
        required_fields: list[str] = schema.get("required", [])
        param_defs: dict[str, Any] = {}
        for param_name, param_meta in properties.items():
            param_defs[param_name] = {
                "description": param_meta.get("description", ""),
                "type": param_meta.get("type", "str"),
                "required": param_name in required_fields,
            }
        cohere_tools.append(
            {
                "name": name,
                "description": description,
                "parameter_definitions": param_defs,
            }
        )
    return cohere_tools


COHERE_MODELS = {
    "command-r-plus": {
        "context_window": 128000,
        "supports_tools": True,
        "supports_rag": True,
        "description": "Most capable - best for RAG and complex tasks",
    },
    "command-r": {
        "context_window": 128000,
        "supports_tools": True,
        "supports_rag": True,
        "description": "Balanced - RAG-optimized, cost-effective",
    },
    "command": {
        "context_window": 4096,
        "supports_tools": False,
        "supports_rag": False,
        "description": "General purpose completion",
    },
    "command-light": {
        "context_window": 4096,
        "supports_tools": False,
        "supports_rag": False,
        "description": "Fast, lightweight completion",
    },
    "embed-english-v3.0": {
        "dimension": 1024,
        "description": "Best English embeddings",
    },
    "embed-multilingual-v3.0": {
        "dimension": 1024,
        "description": "100+ languages supported",
    },
    "embed-english-light-v3.0": {
        "dimension": 384,
        "description": "Lightweight English embeddings",
    },
}
