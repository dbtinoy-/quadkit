"""OpenAI Chat Completions wire DTO family."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.ai.relay.dto.common import require_field

__all__ = [
    "OpenAIChatChoice",
    "OpenAIChatMessage",
    "OpenAIChatRequest",
    "OpenAIChatResponse",
    "OpenAIChatStreamChoice",
    "OpenAIChatStreamChunk",
    "OpenAIChatStreamDelta",
]


@dataclass(frozen=True)
class OpenAIChatMessage:
    """A message in OpenAI Chat Completions format.

    Attributes:
        role: ``system``, ``user``, ``assistant``, ``tool``, ``function``.
        content: String content, or ``None`` for tool-call turns.
        name: Optional author name.
        tool_call_id: Id of the tool call this message answers.
        tool_calls: Tool calls on an assistant message, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    role: str
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {**self.passthrough, "role": self.role}

        data["content"] = self.content
        if self.name is not None:
            data["name"] = self.name
        if self.tool_call_id is not None:
            data["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            data["tool_calls"] = self.tool_calls
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenAIChatMessage:
        """Build a message from a wire dict, capturing unknown keys."""
        known = {"role", "content", "name", "tool_call_id", "tool_calls"}
        return cls(
            role=data.get("role", "user"),
            content=data.get("content"),
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class OpenAIChatRequest:
    """OpenAI Chat Completions request body.

    Attributes:
        model: Model name.
        messages: Message list.
        temperature: Sampling temperature (``None`` = omitted upstream).
        top_p: Nucleus sampling (``None`` = omitted upstream).
        max_tokens: Max output tokens (``None`` = omitted upstream).
        max_completion_tokens: Max completion tokens (``None`` = omitted
            upstream; normalized against ``max_tokens`` by the mapper).
        stream: Whether the caller wants a stream.
        stream_options: ``{"include_usage": bool}`` or ``None``.
        tools: Raw tool definitions, or ``None``.
        tool_choice: Tool choice directive, or ``None``.
        parallel_tool_calls: Parallel tool-call flag, or ``None``.
        stop: Stop string or list of strings, or ``None``.
        response_format: JSON-mode config, or ``None``.
        reasoning: Reasoning config (e.g. ``{"effort": ...}``), or ``None``.
        service_tier: Service tier, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    model: str
    messages: list[OpenAIChatMessage]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    stream: bool = False
    stream_options: dict[str, Any] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    parallel_tool_calls: bool | None = None
    stop: str | list[str] | None = None
    response_format: dict[str, Any] | None = None
    reasoning: dict[str, Any] | None = None
    service_tier: str | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {
            **self.passthrough,
            "model": self.model,
            "messages": [m.to_dict() for m in self.messages],
        }
        if self.temperature is not None:
            data["temperature"] = self.temperature
        if self.top_p is not None:
            data["top_p"] = self.top_p
        if self.max_tokens is not None:
            data["max_tokens"] = self.max_tokens
        if self.max_completion_tokens is not None:
            data["max_completion_tokens"] = self.max_completion_tokens
        data["stream"] = self.stream
        if self.stream_options is not None:
            data["stream_options"] = self.stream_options
        if self.tools is not None:
            data["tools"] = self.tools
        if self.tool_choice is not None:
            data["tool_choice"] = self.tool_choice
        if self.parallel_tool_calls is not None:
            data["parallel_tool_calls"] = self.parallel_tool_calls
        if self.stop is not None:
            data["stop"] = self.stop
        if self.response_format is not None:
            data["response_format"] = self.response_format
        if self.reasoning is not None:
            data["reasoning"] = self.reasoning
        if self.service_tier is not None:
            data["service_tier"] = self.service_tier
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenAIChatRequest:
        """Build a request from a wire dict, capturing unknown keys.

        Raises:
            RelayError: With code ``malformed_payload`` when ``model``
                is absent.
        """
        known = {
            "model",
            "messages",
            "temperature",
            "top_p",
            "max_tokens",
            "max_completion_tokens",
            "stream",
            "stream_options",
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "stop",
            "response_format",
            "reasoning",
            "service_tier",
        }
        return cls(
            model=require_field(data, "model"),
            messages=[OpenAIChatMessage.from_dict(m) for m in data.get("messages", [])],
            temperature=data.get("temperature"),
            top_p=data.get("top_p"),
            max_tokens=data.get("max_tokens"),
            max_completion_tokens=data.get("max_completion_tokens"),
            stream=bool(data.get("stream", False)),
            stream_options=data.get("stream_options"),
            tools=data.get("tools"),
            tool_choice=data.get("tool_choice"),
            parallel_tool_calls=data.get("parallel_tool_calls"),
            stop=data.get("stop"),
            response_format=data.get("response_format"),
            reasoning=data.get("reasoning"),
            service_tier=data.get("service_tier"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class OpenAIChatChoice:
    """One choice in a non-streamed completion response.

    Attributes:
        index: Choice index.
        message: Assistant message, or ``None``.
        finish_reason: ``stop``, ``length``, ``tool_calls``, etc.
        logprobs: Token log-probability info, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    index: int = 0
    message: OpenAIChatMessage | None = None
    finish_reason: str | None = None
    logprobs: Any | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {**self.passthrough, "index": self.index}
        if self.message is not None:
            data["message"] = self.message.to_dict()
        if self.finish_reason is not None:
            data["finish_reason"] = self.finish_reason
        if self.logprobs is not None:
            data["logprobs"] = self.logprobs
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenAIChatChoice:
        """Build a choice from a wire dict, capturing unknown keys."""
        known = {"index", "message", "finish_reason", "logprobs"}
        message = data.get("message")
        return cls(
            index=data.get("index", 0),
            message=OpenAIChatMessage.from_dict(message)
            if isinstance(message, dict)
            else None,
            finish_reason=data.get("finish_reason"),
            logprobs=data.get("logprobs"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class OpenAIChatResponse:
    """Non-streamed Chat Completions response body.

    Attributes:
        id: Completion id.
        model: Model name.
        choices: Completion choices.
        object: Object type (``chat.completion``).
        created: Unix timestamp.
        usage: Raw usage dict, or ``None``.
        system_fingerprint: System fingerprint, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    id: str
    model: str
    choices: list[OpenAIChatChoice]
    object: str = "chat.completion"
    created: int = 0
    usage: dict[str, Any] | None = None
    system_fingerprint: str | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {
            **self.passthrough,
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [c.to_dict() for c in self.choices],
        }
        if self.usage is not None:
            data["usage"] = self.usage
        if self.system_fingerprint is not None:
            data["system_fingerprint"] = self.system_fingerprint
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenAIChatResponse:
        """Build a response from a wire dict, capturing unknown keys.

        Raises:
            RelayError: With code ``malformed_payload`` when ``id`` or
                ``model`` is absent.
        """
        known = {
            "id",
            "object",
            "created",
            "model",
            "choices",
            "usage",
            "system_fingerprint",
        }
        return cls(
            id=require_field(data, "id"),
            object=data.get("object", "chat.completion"),
            created=data.get("created", 0),
            model=require_field(data, "model"),
            choices=[OpenAIChatChoice.from_dict(c) for c in data.get("choices", [])],
            usage=data.get("usage"),
            system_fingerprint=data.get("system_fingerprint"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class OpenAIChatStreamDelta:
    """Delta payload inside one stream choice.

    Attributes:
        role: Role announcement (``assistant``), or ``None``.
        content: Text delta, or ``None``.
        reasoning_content: Reasoning text delta, or ``None``.
        tool_calls: Partial tool-call fragments (raw wire shape), or ``None``.
        refusal: Refusal text delta, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    role: str | None = None
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    refusal: str | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {**self.passthrough}
        if self.role is not None:
            data["role"] = self.role
        if self.content is not None:
            data["content"] = self.content
        if self.reasoning_content is not None:
            data["reasoning_content"] = self.reasoning_content
        if self.tool_calls is not None:
            data["tool_calls"] = self.tool_calls
        if self.refusal is not None:
            data["refusal"] = self.refusal
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenAIChatStreamDelta:
        """Build a delta from a wire dict, capturing unknown keys."""
        known = {"role", "content", "reasoning_content", "tool_calls", "refusal"}
        return cls(
            role=data.get("role"),
            content=data.get("content"),
            reasoning_content=data.get("reasoning_content"),
            tool_calls=data.get("tool_calls"),
            refusal=data.get("refusal"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class OpenAIChatStreamChoice:
    """One choice inside a stream chunk.

    Attributes:
        index: Choice index.
        delta: Delta payload, or ``None``.
        finish_reason: Terminal finish reason, or ``None``.
        logprobs: Token log-probability info, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    index: int = 0
    delta: OpenAIChatStreamDelta | None = None
    finish_reason: str | None = None
    logprobs: Any | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {**self.passthrough, "index": self.index}
        if self.delta is not None:
            data["delta"] = self.delta.to_dict()
        if self.finish_reason is not None:
            data["finish_reason"] = self.finish_reason
        if self.logprobs is not None:
            data["logprobs"] = self.logprobs
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenAIChatStreamChoice:
        """Build a choice from a wire dict, capturing unknown keys."""
        known = {"index", "delta", "finish_reason", "logprobs"}
        delta = data.get("delta")
        return cls(
            index=data.get("index", 0),
            delta=OpenAIChatStreamDelta.from_dict(delta)
            if isinstance(delta, dict)
            else None,
            finish_reason=data.get("finish_reason"),
            logprobs=data.get("logprobs"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class OpenAIChatStreamChunk:
    """One SSE chunk of a streamed Chat Completions response.

    Attributes:
        id: Completion id.
        model: Model name.
        choices: Stream choices.
        object: Object type (``chat.completion.chunk``).
        created: Unix timestamp.
        usage: Final usage dict (usage-only terminal chunk), or ``None``.
        system_fingerprint: System fingerprint, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    id: str
    model: str
    choices: list[OpenAIChatStreamChoice]
    object: str = "chat.completion.chunk"
    created: int = 0
    usage: dict[str, Any] | None = None
    system_fingerprint: str | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {
            **self.passthrough,
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [c.to_dict() for c in self.choices],
        }
        if self.usage is not None:
            data["usage"] = self.usage
        if self.system_fingerprint is not None:
            data["system_fingerprint"] = self.system_fingerprint
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenAIChatStreamChunk:
        """Build a chunk from a wire dict, capturing unknown keys.

        Raises:
            RelayError: With code ``malformed_payload`` when ``id`` or
                ``model`` is absent.
        """
        known = {
            "id",
            "object",
            "created",
            "model",
            "choices",
            "usage",
            "system_fingerprint",
        }
        return cls(
            id=require_field(data, "id"),
            object=data.get("object", "chat.completion.chunk"),
            created=data.get("created", 0),
            model=require_field(data, "model"),
            choices=[
                OpenAIChatStreamChoice.from_dict(c) for c in data.get("choices", [])
            ],
            usage=data.get("usage"),
            system_fingerprint=data.get("system_fingerprint"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )
