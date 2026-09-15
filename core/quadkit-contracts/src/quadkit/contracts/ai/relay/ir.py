"""Canonical intermediate representation for relay conversion.

Every wire protocol maps into this IR and back. The IR reuses
``ChatMessage`` / ``ToolCall`` / ``ToolDefinition`` / ``ThinkingConfig``
/ ``ThinkingResult`` from ``quadkit.contracts.ai`` so downstream
packages never see protocol-specific shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.ai.agents import ToolDefinition
from quadkit.contracts.ai.llm import ChatMessage, ToolCall
from quadkit.contracts.ai.relay.types import RelayFormat, RelayUsage
from quadkit.contracts.ai.thinking import ThinkingConfig, ThinkingResult

__all__ = [
    "RelayRequest",
    "RelayResponse",
    "StreamDelta",
    "StreamState",
    "normalize_finish_reason",
]


def normalize_finish_reason(raw: str | None) -> str | None:
    """Normalize a wire finish reason to the canonical set.

    Canonical values are ``stop``, ``length``, ``tool_calls``,
    ``function_call``, ``content_filter``, and ``other``.  ``None`` and
    empty strings pass through as ``None``; unrecognized values map to
    ``other``.

    Args:
        raw: Raw finish reason from any wire format (e.g. ``end_turn``,
            ``STOP``, ``max_tokens``, ``tool_use``, ``safety``).

    Returns:
        The canonical finish reason, or ``None`` when absent.
    """
    if not raw:
        return None
    normalized = raw.strip().lower()
    if normalized in {"stop", "end_turn", "stop_sequence", "completed"}:
        return "stop"
    if normalized in {"length", "max_tokens"}:
        return "length"
    if normalized in {"tool_calls", "tool_use"}:
        return "tool_calls"
    if normalized in {"function_call", "malformed_function_call"}:
        return "function_call"
    if normalized in {
        "content_filter",
        "safety",
        "recitation",
        "prohibited_content",
        "blocklist",
        "spii",
        "image_safety",
    }:
        return "content_filter"
    if normalized in {"other", "model_finish_reason_unspecified", "error"}:
        return "other"
    return "other"


@dataclass(frozen=True)
class RelayRequest:
    """Format-agnostic chat request.

    Attributes:
        model: Model name as the upstream should see it (already mapped).
        messages: Chat messages in the canonical shape.
        system: Explicit system text (protocols that separate it).
        tools: Tool definitions, or empty list when none.
        tool_choice: Tool selection policy (``"auto"``, ``"none"``, or a
            protocol-specific dict), or ``None`` when unset.
        temperature: Sampling temperature, or ``None`` when unset.
        top_p: Nucleus sampling probability, or ``None`` when unset.
        top_k: Top-k sampling count, or ``None`` when unset.
        max_tokens: Max output tokens, or ``None`` when unset.
        stop_sequences: Stop strings, or empty list when none.
        response_format: Structured output request (e.g.
            ``{"type": "json_object"}``), or ``None``.
        stream: Whether the caller expects a streamed response.
        include_usage: Request usage in stream chunks.
        parallel_tool_calls: Whether parallel tool calls are allowed,
            or ``None`` when the protocol has no such knob.
        thinking: Thinking/reasoning config, or ``None``.
        metadata: Protocol-specific passthrough key/value pairs.
        passthrough: Unknown request fields preserved verbatim.
    """

    model: str
    messages: list[ChatMessage]
    system: str | None = None
    tools: list[ToolDefinition] = field(default_factory=list)
    tool_choice: str | dict[str, Any] | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_tokens: int | None = None
    stop_sequences: list[str] = field(default_factory=list)
    response_format: dict[str, Any] | None = None
    stream: bool = False
    include_usage: bool = False
    parallel_tool_calls: bool | None = None
    thinking: ThinkingConfig | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    passthrough: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RelayResponse:
    """Format-agnostic non-streamed response.

    Attributes:
        id: Upstream response id, or ``None`` when absent.
        model: Model name reported by the upstream.
        created: Epoch seconds the response was created, or ``None``.
        content: Generated text (empty string when the turn is tool-only).
        thinking: Reasoning output, or ``None``.
        tool_calls: Tool calls requested by the model, or empty list.
        tool_results: Tool results carried by the response payload as
            canonical ``role="tool"`` messages, or empty list.
        finish_reason: Normalized finish reason (``stop``, ``length``,
            ``tool_calls``, ``content_filter``, ``function_call``,
            ``other``), or ``None``.
        status: Upstream response status (e.g. ``completed``,
            ``incomplete``, ``failed``), or ``None``.
        incomplete_details: Reason the response was cut short (e.g.
            ``{"reason": "max_output_tokens"}``), or ``None``.
        usage: Normalized usage, or ``None`` when the upstream omitted it.
        passthrough: Unknown response fields preserved verbatim.
    """

    model: str
    id: str | None = None
    created: int | None = None
    content: str = ""
    thinking: ThinkingResult | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ChatMessage] = field(default_factory=list)
    finish_reason: str | None = None
    status: str | None = None
    incomplete_details: dict[str, Any] | None = None
    usage: RelayUsage | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StreamDelta:
    """One logical stream update in canonical form.

    Attributes:
        kind: Event kind (``content``, ``role``, ``tool_call``,
            ``finish``, ``usage``, ``thinking``, ``status``).
        content: Text delta, or ``None`` when this delta is not text.
        thinking_delta: Reasoning text delta, or ``None``.
        is_thinking: Whether the delta belongs to a thinking block.
        tool_call_index: Index of the tool call this delta updates,
            or ``None``.
        tool_call_id: Tool call id fragment, or ``None``.
        tool_call_name: Tool call name fragment, or ``None``.
        tool_call_arguments: Partial JSON argument text, or ``None``.
        block_index: Claude content block index, or ``None``.
        output_index: OpenAI Responses output item index, or ``None``.
        finish_reason: Terminal finish reason for the whole stream, or ``None``.
        status: Target status value (e.g. ``in_progress``, ``completed``),
            or ``None``.
        usage: Final usage for the whole stream, or ``None`` (usually last chunk).
        role: Role announcement delta (``assistant``), or ``None``.
        passthrough: Unknown event fields preserved verbatim.
    """

    kind: str = "content"
    content: str | None = None
    thinking_delta: str | None = None
    is_thinking: bool = False
    tool_call_index: int | None = None
    tool_call_id: str | None = None
    tool_call_name: str | None = None
    tool_call_arguments: str | None = None
    block_index: int | None = None
    output_index: int | None = None
    finish_reason: str | None = None
    status: str | None = None
    usage: RelayUsage | None = None
    role: str | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StreamState:
    """Immutable stream descriptor; one instance per upstream stream.

    Attributes:
        source: Upstream wire format.
        target: Downstream wire format.
        model: Model name to stamp on emitted chunks.
        include_usage: Whether to emit a final usage event.
        tool_calls: Accumulated tool calls across chunks.
        thinking_signatures: Claude thinking signatures, in order.
        is_done: Whether the stream has been finalized.
        usage: Usage accumulated from upstream chunks.
    """

    source: RelayFormat
    target: RelayFormat
    model: str
    include_usage: bool = False
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking_signatures: list[str] = field(default_factory=list)
    is_done: bool = False
    usage: RelayUsage | None = None
