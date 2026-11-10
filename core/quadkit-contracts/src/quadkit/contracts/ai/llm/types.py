"""LLM type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import replace as _dc_replace
from enum import StrEnum
from typing import Any

from quadkit.contracts.ai.multimodal import MessageContent
from quadkit.contracts.ai.thinking import ThinkingResult


class Role(StrEnum):
    """Concrete chat message role constants shared across AI packages."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    FUNCTION = "function"


@dataclass(frozen=True)
class ChatMessage:
    """Concrete chat message data class shared across AI packages.

    Satisfies ``ChatMessageProtocol``.  Suitable for construction in any
    package that needs to build messages without importing from
    ``quadkit-ai-llm``.
    """

    role: str
    content: MessageContent
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None
    """Native tool calls requested by the LLM (assistant messages only).

    When present, the message carries the function-call requests of an
    assistant turn so the provider can re-emit them to the model before
    the matching ``tool`` role responses.
    """
    thinking_blocks: list[dict[str, Any]] | None = None
    """Raw provider thinking blocks for multi-turn re-injection.

    Anthropic: list of ``{type, thinking, signature}`` dicts from a prior
    assistant turn with extended thinking enabled.  Must be passed back
    verbatim to continue a thinking-enabled conversation.
    """
    metadata: dict[str, Any] | None = None
    """Provider-specific metadata for cache control and annotations."""


@dataclass(frozen=True)
class Completion:
    """Minimal completion data class shared across AI packages.

    Satisfies ``CompletionProtocol``.  Used by consumers that build
    fallback completions without depending on ``quadkit-ai-llm``'s
    full Pydantic model.
    """

    content: str
    model: str
    thinking: ThinkingResult | None = None
    usage: dict[str, int] | None = None
    finish_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FunctionCall:
    """Function call request from LLM."""

    name: str
    arguments: dict[str, Any] | str = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    """Tool call request from LLM."""

    id: str
    type: str = "function"
    function: FunctionCall | None = None


@dataclass(frozen=True)
class TokenUsage:
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class StreamChunk:
    """A chunk of streamed completion."""

    delta: str | None = None
    model: str | None = None
    finish_reason: str | None = None
    role: str | None = None
    index: int = 0
    thinking_delta: str | None = None
    is_thinking: bool = False


@dataclass(frozen=True)
class StreamEvent:
    """Protocol for streaming events."""

    type: str
    content: str | None = None
    tool_call: Any | None = None
    error: str | None = None


@dataclass(frozen=True)
class TokenBudget:
    """Immutable token budget that pipeline stages consult.

    Every field is calculated once at the start of a request. Stages read
    remaining capacity via properties — they never mutate the budget.
    Builder methods return new instances (immutable value semantics).
    """

    model_context_limit: int
    reserved_for_output: int
    system_prompt_tokens: int
    tool_definitions_tokens: int
    rag_context_tokens: int = 0
    history_tokens: int = 0

    @property
    def total_used(self) -> int:
        """Total tokens consumed by all components."""
        return (
            self.system_prompt_tokens
            + self.tool_definitions_tokens
            + self.rag_context_tokens
            + self.history_tokens
            + self.reserved_for_output
        )

    @property
    def remaining(self) -> int:
        """Tokens available for additional content."""
        return max(0, self.model_context_limit - self.total_used)

    @property
    def remaining_for_history(self) -> int:
        """Tokens available specifically for chat history."""
        used = (
            self.system_prompt_tokens
            + self.tool_definitions_tokens
            + self.rag_context_tokens
            + self.reserved_for_output
        )
        return max(0, self.model_context_limit - used)

    @property
    def over_budget(self) -> bool:
        """True if total consumption exceeds the model context limit."""
        return self.total_used > self.model_context_limit

    def with_rag_tokens(self, rag_tokens: int) -> TokenBudget:
        """Return a new budget with updated RAG token count."""
        return _dc_replace(self, rag_context_tokens=rag_tokens)

    def with_history_tokens(self, history_tokens: int) -> TokenBudget:
        """Return a new budget with updated history token count."""
        return _dc_replace(self, history_tokens=history_tokens)
