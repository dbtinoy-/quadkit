"""Type definitions for LLM module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from quadkit.ai.llm.exceptions import LLMError
from quadkit.contracts.ai.llm import (
    FunctionCall,
    Role,
    TokenUsage,
    ToolCall,
)
from quadkit.contracts.ai.multimodal import MessageContent
from quadkit.contracts.ai.thinking import ThinkingResult
from quadkit.contracts.core import Metadata
from quadkit.domain import DomainModel
from quadkit.validation import Field


@dataclass(init=False)
class ChatMessage(DomainModel):
    """A single chat message.

    Implements ChatMessageProtocol with DomainModel semantics for validation.

    Example:
        >>> msg = ChatMessage(role="user", content="Hello, how are you?")
    """

    role: Role = Field(description="Message role")
    content: MessageContent = Field(description="Message content")
    name: str | None = Field(default=None, description="Optional name for the message")
    tool_call_id: str | None = Field(
        default=None,
        description="ID of tool call this message responds to",
    )
    tool_calls: list[ToolCall] | None = Field(
        default=None,
        description=(
            "Native tool calls for an assistant turn, re-emitted to the model "
            "before the matching ``tool`` role responses"
        ),
    )
    thinking_blocks: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Raw provider thinking/reasoning blocks for multi-turn re-injection. "
            "Anthropic: list of {type, thinking, signature} dicts from a prior "
            "assistant turn with extended thinking enabled."
        ),
    )


@dataclass(init=False)
class Completion(DomainModel):
    """LLM completion response.

    Implements completion semantics with DomainModel for validation and additional fields.

    Example:
        >>> completion = Completion(
        ...     content="Hello! I'm doing well, thank you.",
        ...     model="gpt-4-turbo",
        ...     usage=TokenUsage(prompt_tokens=10, completion_tokens=8, total_tokens=18)
        ... )
    """

    content: str = Field(description="Generated completion text")
    model: str = Field(description="Model used for generation")
    provider: str = Field(default="", description="Provider that handled the request")
    model_revision: str = Field(
        default="", description="Provider-reported model revision"
    )
    prompt_hash: bytes | None = Field(
        default=None, description="SHA-256 hash of the prompt"
    )
    completion_tokens: int = Field(default=0, description="Tokens in the completion")
    prompt_tokens: int = Field(default=0, description="Tokens in the prompt")
    request_id: str | None = Field(default=None, description="Provider-side request ID")
    finish_reason: str | None = Field(
        default=None,
        description="Reason completion finished",
    )
    role: Role | None = Field(
        default=None,
        description="Role associated with this completion",
    )
    tool_calls: list[ToolCall] | None = Field(
        default=None,
        description="Tool calls requested by LLM",
    )
    usage: TokenUsage | None = Field(default=None, description="Token usage stats")
    thinking: ThinkingResult | None = Field(
        default=None,
        description=(
            "Normalised thinking/reasoning output from the model. "
            "None when thinking is disabled or the provider does not support it."
        ),
    )
    metadata: Metadata = Field(default_factory=dict, description="Additional metadata")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Completion timestamp",
    )


@dataclass(init=False)
class StreamChunk(DomainModel):
    """A chunk of streamed completion.

    Implements streaming semantics with DomainModel for validation.

    Example:
        >>> chunk = StreamChunk(delta="Hello", model="gpt-4-turbo", finish_reason=None)
    """

    delta: str | None = Field(default=None, description="Text delta for this chunk")
    content: str | None = Field(
        default=None, description="Compatibility alias for text delta"
    )
    tokens_used: int = Field(default=0, description="Tokens represented by this chunk")
    metadata: Metadata = Field(
        default_factory=dict, description="Additional chunk metadata"
    )
    model: str | None = Field(default=None, description="Model generating the stream")
    finish_reason: str | None = Field(
        default=None,
        description="Reason stream finished (on last chunk)",
    )
    role: Role | None = Field(
        default=None,
        description="Role associated with this chunk",
    )
    index: int = Field(default=0, description="Chunk index in stream")
    thinking_delta: str | None = Field(
        default=None,
        description="Thinking content delta for this chunk (during streaming).",
    )
    is_thinking: bool = Field(
        default=False,
        description="True when this chunk contains thinking content rather than answer text.",
    )

    def __post_init__(self) -> None:
        if (
            self.delta is not None
            and self.content is not None
            and self.delta != self.content
        ):
            raise ValueError("delta and content must match when both are provided")
        if self.delta is None and self.content is not None:
            self.delta = self.content
        if self.content is None and self.delta is not None:
            self.content = self.delta


from quadkit.ai.llm.exceptions import (
    InvalidRequestError,
    LLMAuthenticationError,
    LLMRateLimitError,
)

AIError = LLMError

__all__ = [
    "AIError",
    "ChatMessage",
    "Completion",
    "FunctionCall",
    "InvalidRequestError",
    "LLMAuthenticationError",
    "LLMError",
    "LLMRateLimitError",
    "Role",
    "StreamChunk",
    "ThinkingResult",
    "TokenUsage",
    "ToolCall",
]
