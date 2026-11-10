"""Shared helpers for Google Gemini and Vertex AI clients.

Both :class:`~quadkit.ai.llm.clients.gemini.GeminiClient` and
:class:`~quadkit.ai.llm.clients.vertex_ai.VertexAIClient` target the same
Gemini model contract.  This module holds all shared message conversion,
response parsing, thinking injection, and tool-formatting utilities so that
neither client imports private symbols from the other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.clients._message_utils import serialize_content_for_gemini
from quadkit.ai.llm.clients._tools_utils import parse_json_arguments
from quadkit.ai.llm.types import (
    AIError,
    Completion,
    FunctionCall,
    StreamChunk,
    ThinkingResult,
    TokenUsage,
    ToolCall,
)
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str
from quadkit.serialization import loads as _loads

if TYPE_CHECKING:
    from collections.abc import Iterator

    from quadkit.ai.llm.config import ClientConfig

logger = get_logger(__name__)


__all__ = [
    "inject_thinking_config",
    "messages_to_gemini",
    "parse_gemini_response",
    "parse_gemini_response_with_tools",
    "parse_gemini_sse_body",
    "tool_to_gemini_function",
]


def inject_thinking_config(gen_config: dict[str, Any], config: ClientConfig) -> None:
    """Inject ``thinkingConfig`` into a Gemini ``generationConfig`` dict.

    When ``config.thinking.suppress`` is set, injects ``thinkingBudget: 0`` to
    disable thinking.  Gemini 3 models use ``thinkingLevel``; Gemini 2.5 models
    use ``thinkingBudget``.

    Args:
        gen_config: The ``generationConfig`` sub-dict to mutate in place.
        config: LLM configuration.
    """
    if config.thinking is None:
        return
    if config.thinking.suppress:
        gen_config["thinkingConfig"] = {"thinkingBudget": 0}
        return
    if config.thinking.level:
        gen_config["thinkingConfig"] = {"thinkingLevel": config.thinking.level}
    else:
        gen_config["thinkingConfig"] = {"thinkingBudget": config.thinking.budget_tokens}


def messages_to_gemini(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert OpenAI-format messages to Gemini ``contents`` format.

    System messages are prepended as a text part to the first user turn
    (Gemini has no top-level system role).  Image URL content parts are
    converted to ``inline_data`` for data URIs, or kept as text references
    for external URLs.

    Assistant turns that requested tools emit ``functionCall`` parts; tool
    results (``Role.TOOL``) emit ``functionResponse`` parts so multi-turn
    tool conversations round-trip correctly.

    Args:
        messages: OpenAI-compatible message list or ChatMessage objects.

    Returns:
        Gemini-format ``contents`` list.
    """
    system_text: str | None = None
    contents: list[dict[str, Any]] = []

    for msg in messages:
        role: str = _role_str(msg)
        content: Any = (
            msg.get("content", "")
            if isinstance(msg, dict)
            else getattr(msg, "content", "")
        )
        tool_calls: Any = (
            msg.get("tool_calls")
            if isinstance(msg, dict)
            else getattr(msg, "tool_calls", None)
        )

        if role == "system":
            system_text = (
                content if isinstance(content, str) else _extract_text(content)
            )
            continue

        gemini_role = "user" if role in ("user", "tool", "function") else "model"
        parts: list[dict[str, Any]] = []

        # Prepend system text to the first user turn
        if system_text and gemini_role == "user" and not contents:
            parts.append({"text": system_text})
            system_text = None

        # Use the multimodal serializer for MessageContent
        serialized = serialize_content_for_gemini(content)
        if serialized and role != "tool":
            parts.extend(serialized)

        if role == "tool":
            tool_call_id: str = (
                msg.get("tool_call_id", "")
                if isinstance(msg, dict)
                else getattr(msg, "tool_call_id", "")
            )
            if tool_call_id:
                parts.append(
                    {
                        "functionResponse": {
                            "name": tool_call_id,
                            "response": {"content": _extract_text(content)},
                        }
                    }
                )
        elif role == "assistant" and tool_calls:
            for call in tool_calls:
                fn = getattr(call, "function", None)
                if fn is None or not getattr(fn, "name", None):
                    continue
                parts.append(
                    {
                        "functionCall": {
                            "name": fn.name,
                            "args": parse_json_arguments(fn.arguments),
                        }
                    }
                )

        # Drop empty text parts when the turn carries tool parts; Gemini
        # rejects empty text blocks alongside functionCall/functionResponse.
        if any("functionCall" in p or "functionResponse" in p for p in parts):
            parts = [p for p in parts if p != {"text": ""}]

        contents.append({"role": gemini_role, "parts": parts})

    if system_text:
        logger.warning(
            "gemini_system_message_dropped",
            reason="first_non_system_message_was_not_user_role",
        )

    return contents


def parse_gemini_response(data: dict[str, Any], model: str) -> Completion:
    """Parse a Gemini ``generateContent`` response into a ``Completion``.

    Separates ``thought`` parts (thinking) from answer parts.  Populates
    :attr:`~quadkit.ai.llm.types.Completion.thinking` with a
    :class:`~quadkit.contracts.ai.thinking.ThinkingResult` when the model
    produced thinking output.

    Args:
        data: Parsed JSON response dict from the Gemini API.
        model: Model identifier used for the ``Completion`` metadata.

    Returns:
        Normalised :class:`~quadkit.ai.llm.types.Completion`.

    Raises:
        AIError: When the response has no candidates (e.g. blocked by safety filters).
    """
    candidates = data.get("candidates")
    if not candidates:
        raise AIError("Gemini returned no candidates")

    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])

    thinking_parts: list[str] = []
    answer_parts: list[str] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        text = p.get("text", "")
        if p.get("thought"):
            thinking_parts.append(text)
        else:
            answer_parts.append(text)

    usage_meta = data.get("usageMetadata", {})
    reasoning_tokens: int | None = usage_meta.get("thoughtsTokenCount") or None
    usage = TokenUsage(
        prompt_tokens=usage_meta.get("promptTokenCount", 0),
        completion_tokens=usage_meta.get("candidatesTokenCount", 0),
        total_tokens=usage_meta.get("totalTokenCount", 0),
    )

    thinking: ThinkingResult | None = None
    if thinking_parts:
        thinking = ThinkingResult(
            content="".join(thinking_parts),
            tokens=reasoning_tokens,
        )

    return Completion(
        content="".join(answer_parts),
        model=model,
        thinking=thinking,
        usage=usage,
    )


def parse_gemini_response_with_tools(data: dict[str, Any], model: str) -> Completion:
    """Parse a Gemini response that may contain function-call parts.

    Handles both plain-text and ``functionCall`` parts in the response
    candidates, returning a :class:`Completion` with optional
    :attr:`~Completion.tool_calls` populated.

    Args:
        data: Parsed JSON from the Gemini ``generateContent`` endpoint.
        model: Model identifier used for the ``Completion`` metadata.

    Returns:
        Normalised :class:`~quadkit.ai.llm.types.Completion`.

    Raises:
        AIError: When the response has no candidates.
    """
    candidates = data.get("candidates")
    if not candidates:
        raise AIError("Gemini returned no candidates")

    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])

    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []

    for part in parts:
        if not isinstance(part, dict):
            continue
        if "text" in part:
            text_parts.append(part["text"])
        elif "functionCall" in part:
            fc = part["functionCall"]
            name: str = fc.get("name", "")
            args: dict[str, Any] = fc.get("args", {})
            tool_calls.append(
                ToolCall(
                    id=name,
                    type="function",
                    function=FunctionCall(
                        name=name,
                        arguments=dumps_str(args),
                    ),
                )
            )

    usage_meta = data.get("usageMetadata", {})
    usage = TokenUsage(
        prompt_tokens=usage_meta.get("promptTokenCount", 0),
        completion_tokens=usage_meta.get("candidatesTokenCount", 0),
        total_tokens=usage_meta.get("totalTokenCount", 0),
    )

    return Completion(
        content="".join(text_parts),
        model=model,
        usage=usage,
        tool_calls=tool_calls or None,
    )


def parse_gemini_sse_body(body: str, model: str) -> Iterator[StreamChunk]:
    """Yield :class:`StreamChunk` objects from a Gemini SSE response body.

    Gemini streams a JSON array over SSE.  Each ``data:`` line carries a
    ``generateContentResponse`` object whose ``candidates[0].content.parts``
    contain incremental text deltas.  Parts with ``thought=True`` are yielded
    as thinking chunks.

    Args:
        body: Full SSE response body text.
        model: Model label embedded in each :class:`StreamChunk`.

    Yields:
        :class:`StreamChunk` with incremental text or thinking deltas.
    """
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        raw = stripped[len("data:") :].strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            chunk_data: dict[str, Any] = _loads(raw)
        except (ValueError, TypeError):
            continue
        candidates = chunk_data.get("candidates", [])
        for i, cand in enumerate(candidates):
            parts = cand.get("content", {}).get("parts", [])
            finish = cand.get("finishReason")
            for part in parts:
                if not isinstance(part, dict) or "text" not in part:
                    continue
                if part.get("thought"):
                    yield StreamChunk(
                        thinking_delta=part["text"],
                        is_thinking=True,
                        model=model,
                        finish_reason=finish,
                        index=i,
                    )
                else:
                    yield StreamChunk(
                        delta=part["text"],
                        model=model,
                        finish_reason=finish,
                        index=i,
                    )


def tool_to_gemini_function(tool: Any) -> dict[str, Any]:
    """Convert a tool descriptor to a Gemini ``FunctionDeclaration``.

    Supports objects that expose a ``__tool_schema__`` class attribute
    (following the Quadkit tool registration convention) as well as plain
    dictionaries in OpenAI tool format.

    Args:
        tool: A :class:`ToolCall`, class with ``__tool_schema__``, or dict
            with ``function`` key in OpenAI tool format.

    Returns:
        Gemini ``FunctionDeclaration`` dict with ``name``, ``description``,
        and ``parameters`` keys.
    """
    if hasattr(tool, "__tool_schema__"):
        schema: dict[str, Any] = tool.__tool_schema__
        return {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": schema.get("parameters", {}),
        }
    if isinstance(tool, dict):
        func = tool.get("function", tool)
        return {
            "name": func.get("name", ""),
            "description": func.get("description", ""),
            "parameters": func.get("parameters", {}),
        }
    return {
        "name": getattr(tool, "name", str(tool)),
        "description": getattr(tool, "description", "") or "",
        "parameters": getattr(tool, "parameters", None) or {},
    }


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────


def _role_str(msg: Any) -> str:
    """Convert a Quadkit role string to a Gemini role string.

    Args:
        msg: A dict or object with a ``role`` attribute (e.g. 'user', 'assistant', 'tool').

    Returns:
        'user' for user/tool/function roles, 'model' for all others.
    """
    role = (
        msg.get("role", "user")
        if isinstance(msg, dict)
        else getattr(msg, "role", "user")
    )
    return role.value if hasattr(role, "value") else str(role)


def _extract_text(content: Any) -> str:
    """Extract plain text from a mixed OpenAI content list.

    Args:
        content: Content field from an OpenAI message; may be a list of
            typed parts or any other value.

    Returns:
        Concatenated text string.
    """
    if isinstance(content, list):
        return " ".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return str(content)
