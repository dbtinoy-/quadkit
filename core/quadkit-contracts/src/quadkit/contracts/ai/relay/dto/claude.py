"""Anthropic Claude Messages wire DTO family."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.ai.relay.dto.common import require_field

__all__ = [
    "ClaudeContent",
    "ClaudeMessage",
    "ClaudeRequest",
    "ClaudeResponse",
    "ClaudeStreamEvent",
    "ClaudeUsage",
]


@dataclass(frozen=True)
class ClaudeContent:
    """A content block in a Claude message.

    Attributes:
        type: ``text``, ``image``, ``tool_use``, ``tool_result``, ``thinking``.
        text: Text for ``text`` blocks.
        thinking: Thinking text for ``thinking`` blocks.
        signature: Thinking signature for ``thinking`` blocks.
        tool_use_id: Tool-use id.
        name: Tool name.
        input: Tool call arguments.
        image_source: ``{"type": "base64", "media_type": ..., "data": ...}`` or ``None``.
        tool_result_content: Content of a tool result block.
        passthrough: Unknown fields preserved verbatim.
    """

    type: str = "text"
    text: str | None = None
    thinking: str | None = None
    signature: str | None = None
    tool_use_id: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None
    image_source: dict[str, Any] | None = None
    tool_result_content: list[ClaudeContent] | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict."""
        data: dict[str, Any] = {**self.passthrough, "type": self.type}
        if self.text is not None:
            data["text"] = self.text
        if self.thinking is not None:
            data["thinking"] = self.thinking
        if self.signature is not None:
            data["signature"] = self.signature
        if self.tool_use_id is not None:
            if self.type == "tool_result":
                data["tool_use_id"] = self.tool_use_id
            else:
                data["id"] = self.tool_use_id
        if self.name is not None:
            data["name"] = self.name
        if self.input is not None:
            data["input"] = self.input
        if self.image_source is not None:
            data["source"] = self.image_source
        if self.tool_result_content is not None:
            texts = [
                block.text for block in self.tool_result_content if block.type == "text"
            ]
            if len(self.tool_result_content) == 1 and texts[0] is not None:
                data["content"] = texts[0]
            else:
                data["content"] = [c.to_dict() for c in self.tool_result_content]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaudeContent:
        """Build a content block from a wire dict, capturing unknown keys."""
        known = {
            "type",
            "text",
            "thinking",
            "signature",
            "id",
            "tool_use_id",
            "name",
            "input",
            "source",
            "content",
        }
        block_type = data.get("type", "text")
        content = data.get("content")
        return cls(
            type=block_type,
            text=data.get("text"),
            thinking=data.get("thinking"),
            signature=data.get("signature"),
            tool_use_id=(
                data.get("tool_use_id")
                if block_type == "tool_result"
                else data.get("id")
            ),
            name=data.get("name"),
            input=data.get("input"),
            image_source=data.get("source"),
            tool_result_content=(
                [ClaudeContent.from_dict(c) for c in content if isinstance(c, dict)]
                if isinstance(content, list)
                else (
                    [ClaudeContent(type="text", text=content)]
                    if isinstance(content, str)
                    else None
                )
            ),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class ClaudeMessage:
    """A message in Claude Messages format.

    Attributes:
        role: ``user`` or ``assistant``.
        content: Plain text, or a list of content blocks.
    """

    role: str
    content: str | list[ClaudeContent]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict."""
        if isinstance(self.content, str):
            return {"role": self.role, "content": self.content}
        return {"role": self.role, "content": [c.to_dict() for c in self.content]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaudeMessage:
        """Build a message from a wire dict."""
        content = data.get("content", [])
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        return cls(
            role=data["role"],
            content=[ClaudeContent.from_dict(c) for c in content],
        )


@dataclass(frozen=True)
class ClaudeRequest:
    """Claude Messages request body.

    Attributes:
        model: Model name.
        max_tokens: Max output tokens (required by the protocol).
        messages: Message list.
        system: System text, or ``None``.
        temperature: Sampling temperature, or ``None``.
        top_p: Nucleus sampling, or ``None``.
        stream: Whether the caller wants a stream.
        tools: Raw tool definitions, or ``None``.
        tool_choice: Tool choice directive, or ``None``.
        stop_sequences: Stop strings, or ``None``.
        thinking: Thinking config dict, or ``None``.
        metadata: Request metadata, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    model: str
    max_tokens: int
    messages: list[ClaudeMessage]
    system: str | list[dict[str, Any]] | None = None
    temperature: float | None = None
    top_p: float | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    stop_sequences: list[str] | None = None
    thinking: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {
            **self.passthrough,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [m.to_dict() for m in self.messages],
        }
        if self.system is not None:
            data["system"] = self.system
        if self.temperature is not None:
            data["temperature"] = self.temperature
        if self.top_p is not None:
            data["top_p"] = self.top_p
        if self.stream:
            data["stream"] = True
        if self.tools is not None:
            data["tools"] = self.tools
        if self.tool_choice is not None:
            data["tool_choice"] = self.tool_choice
        if self.stop_sequences is not None:
            data["stop_sequences"] = self.stop_sequences
        if self.thinking is not None:
            data["thinking"] = self.thinking
        if self.metadata is not None:
            data["metadata"] = self.metadata
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaudeRequest:
        """Build a request from a wire dict, capturing unknown keys.

        Raises:
            RelayError: With code ``malformed_payload`` when ``model``,
                ``max_tokens``, or ``messages`` is absent.
        """
        known = {
            "model",
            "max_tokens",
            "messages",
            "system",
            "temperature",
            "top_p",
            "stream",
            "tools",
            "tool_choice",
            "stop_sequences",
            "thinking",
            "metadata",
        }
        return cls(
            model=require_field(data, "model"),
            max_tokens=require_field(data, "max_tokens"),
            messages=[ClaudeMessage.from_dict(m) for m in data.get("messages", [])],
            system=data.get("system"),
            temperature=data.get("temperature"),
            top_p=data.get("top_p"),
            stream=bool(data.get("stream", False)),
            tools=data.get("tools"),
            tool_choice=data.get("tool_choice"),
            stop_sequences=data.get("stop_sequences"),
            thinking=data.get("thinking"),
            metadata=data.get("metadata"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class ClaudeUsage:
    """Claude Messages usage accounting.

    Attributes:
        input_tokens: Input tokens.
        output_tokens: Output tokens.
        cache_creation_input_tokens: Cache-creation input tokens.
        cache_read_input_tokens: Cached input tokens read.
        passthrough: Unknown fields preserved verbatim.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    passthrough: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict."""
        data: dict[str, Any] = {
            **self.passthrough,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaudeUsage:
        """Build usage from a wire dict, capturing unknown keys."""
        known = {
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        }
        return cls(
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            cache_creation_input_tokens=data.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=data.get("cache_read_input_tokens", 0),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class ClaudeResponse:
    """Non-streamed Claude Messages response body.

    Attributes:
        id: Message id.
        model: Model name.
        content: Content blocks (text, thinking, tool_use, ...).
        type: Object type (``message``).
        role: Message role (``assistant``).
        stop_reason: ``end_turn``, ``max_tokens``, ``tool_use``, etc.
        stop_sequence: Stop sequence that ended generation, or ``None``.
        usage: Token usage, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    id: str
    model: str
    content: list[ClaudeContent] = field(default_factory=list)
    type: str = "message"
    role: str = "assistant"
    stop_reason: str | None = None
    stop_sequence: str | None = None
    usage: ClaudeUsage | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {
            **self.passthrough,
            "id": self.id,
            "type": self.type,
            "role": self.role,
            "model": self.model,
            "content": [c.to_dict() for c in self.content],
        }
        if self.stop_reason is not None:
            data["stop_reason"] = self.stop_reason
        if self.stop_sequence is not None:
            data["stop_sequence"] = self.stop_sequence
        if self.usage is not None:
            data["usage"] = self.usage.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaudeResponse:
        """Build a response from a wire dict, capturing unknown keys.

        Raises:
            RelayError: With code ``malformed_payload`` when ``id`` or
                ``model`` is absent.
        """
        known = {
            "id",
            "type",
            "role",
            "model",
            "content",
            "stop_reason",
            "stop_sequence",
            "usage",
        }
        usage = data.get("usage")
        return cls(
            id=require_field(data, "id"),
            type=data.get("type", "message"),
            role=data.get("role", "assistant"),
            model=require_field(data, "model"),
            content=[ClaudeContent.from_dict(c) for c in data.get("content", [])],
            stop_reason=data.get("stop_reason"),
            stop_sequence=data.get("stop_sequence"),
            usage=ClaudeUsage.from_dict(usage) if isinstance(usage, dict) else None,
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class ClaudeStreamEvent:
    """One SSE event in Claude Messages streaming.

    The ``type`` field is the discriminator: ``message_start``,
    ``content_block_start``, ``content_block_delta``,
    ``content_block_stop``, ``message_delta``, ``message_stop``,
    ``ping``, or ``error``.

    Attributes:
        type: Event type discriminator.
        message: ``message_start`` payload.
        index: Content block index for block lifecycle events.
        content_block: ``content_block_start`` block payload.
        delta: Raw delta payload (``text_delta``, ``input_json_delta``,
            ``thinking_delta``, message_delta).
        usage: Usage on ``message_start`` / ``message_delta``.
        stop_reason: Stop reason on ``message_delta``.
        stop_sequence: Stop sequence on ``message_delta``.
        error: Raw error payload for ``error`` events.
        passthrough: Unknown fields preserved verbatim.
    """

    type: str
    message: ClaudeResponse | None = None
    index: int | None = None
    content_block: ClaudeContent | None = None
    delta: dict[str, Any] | None = None
    usage: ClaudeUsage | None = None
    stop_reason: str | None = None
    stop_sequence: str | None = None
    error: dict[str, Any] | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {**self.passthrough, "type": self.type}
        if self.message is not None:
            data["message"] = self.message.to_dict()
        if self.index is not None:
            data["index"] = self.index
        if self.content_block is not None:
            data["content_block"] = self.content_block.to_dict()
        if self.delta is not None:
            data["delta"] = self.delta
        if self.usage is not None:
            data["usage"] = self.usage.to_dict()
        if self.stop_reason is not None:
            data["stop_reason"] = self.stop_reason
        if self.stop_sequence is not None:
            data["stop_sequence"] = self.stop_sequence
        if self.error is not None:
            data["error"] = self.error
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaudeStreamEvent:
        """Build an event from a wire dict, capturing unknown keys."""
        known = {
            "type",
            "message",
            "index",
            "content_block",
            "delta",
            "usage",
            "stop_reason",
            "stop_sequence",
            "error",
        }
        message = data.get("message")
        content_block = data.get("content_block")
        usage = data.get("usage")
        return cls(
            type=data.get("type", "ping"),
            message=ClaudeResponse.from_dict(message)
            if isinstance(message, dict)
            else None,
            index=data.get("index"),
            content_block=(
                ClaudeContent.from_dict(content_block)
                if isinstance(content_block, dict)
                else None
            ),
            delta=data.get("delta"),
            usage=ClaudeUsage.from_dict(usage) if isinstance(usage, dict) else None,
            stop_reason=data.get("stop_reason"),
            stop_sequence=data.get("stop_sequence"),
            error=data.get("error"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )
