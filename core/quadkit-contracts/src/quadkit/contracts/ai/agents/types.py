"""Agent type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentEventType(str, Enum):
    """Event types emitted during agent streaming execution."""

    STARTED = "started"
    """Agent execution has started."""

    THOUGHT = "thought"
    """Agent emitted a thought/reasoning step."""

    TOOL_START = "tool_start"
    """Tool execution is about to start."""

    TOOL_END = "tool_end"
    """Tool execution has completed."""

    MESSAGE = "message"
    """Agent emitted a message (intermediate or final)."""

    ERROR = "error"
    """An error occurred during execution."""

    FINISHED = "finished"
    """Agent execution has finished."""


@dataclass(frozen=True)
class AgentEvent:
    """Event emitted during agent streaming execution.

    Attributes:
        type: The type of event.
        data: Event payload data.
        run_id: Unique identifier for this execution run.
    """

    type: AgentEventType
    """The type of event."""

    data: dict[str, Any]
    """Event payload data."""

    run_id: str
    """Unique identifier for this execution run."""


@dataclass(frozen=True)
class AgentResponse:
    """Complete response from an agent execution.

    Contains the final message, the full reasoning trace (steps),
    all tool calls made, token usage, cost, and timing metadata.

    Note: ToolCall and ReasoningStep are defined in quadkit-ai-agents
    and imported here for use in this type's field annotations.
    """

    message: str
    """The agent's final response to the user."""

    steps: list[Any] = field(default_factory=list)
    """Full reasoning trace — every thought, action, and observation."""

    tool_calls: list[Any] = field(default_factory=list)
    """All tool invocations made during this execution."""

    total_tokens: int = 0
    """Total LLM tokens consumed (prompt + completion)."""

    prompt_tokens: int = 0
    """Input (prompt) LLM tokens consumed. ``0`` when unknown."""

    completion_tokens: int = 0
    """Output (completion) LLM tokens consumed. ``0`` when unknown."""

    total_cost: float = 0.0
    """Estimated cost in USD."""

    duration_ms: float = 0.0
    """Total execution time in milliseconds."""

    session_id: str | None = None
    """Session identifier for multi-turn conversations."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata (model name, strategy used, etc.)."""

    @property
    def tool_call_count(self) -> int:
        """Number of tool calls made."""
        return len(self.tool_calls)

    @property
    def step_count(self) -> int:
        """Number of reasoning steps taken."""
        return len(self.steps)

    @property
    def successful_tool_calls(self) -> list[Any]:
        """Tool calls that completed without error."""
        return [tc for tc in self.tool_calls if getattr(tc, "succeeded", True)]

    @property
    def failed_tool_calls(self) -> list[Any]:
        """Tool calls that failed."""
        return [tc for tc in self.tool_calls if not getattr(tc, "succeeded", True)]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "message": self.message,
            "steps": len(self.steps),
            "tool_calls": len(self.tool_calls),
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_cost": self.total_cost,
            "duration_ms": self.duration_ms,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ToolDefinition:
    """Schema for a tool."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """Result of tool execution."""

    success: bool
    output: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class AgentExecutionContext:
    """Typed context for agent execution."""

    session_id: str | None = None
    tools: list[ToolDefinition] | None = None
    config: dict[str, Any] | None = None
