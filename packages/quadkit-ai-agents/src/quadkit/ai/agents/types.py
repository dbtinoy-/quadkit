"""Agent types — concrete implementations for agent execution.

Defines ToolExecutionRecord and ReasoningStep (concrete agent data structures).
AgentResponse is re-exported from contracts as it's used in protocol signatures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from quadkit.contracts.ai.agents import AgentResponse


@dataclass
class ToolExecutionRecord:
    """Record of a single tool invocation during agent execution.

    Captures the tool name, arguments, result (or error), and timing
    for observability and debugging.
    """

    tool_name: str
    """Name of the tool that was called."""

    arguments: dict[str, Any] = field(default_factory=dict)
    """Arguments passed to the tool."""

    result: Any = None
    """Return value from the tool (None if error)."""

    error: str | None = None
    """Error message if the tool call failed."""

    duration_ms: float = 0.0
    """Execution time in milliseconds."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    """When the tool was called."""

    @property
    def succeeded(self) -> bool:
        """Whether the tool call completed without error."""
        return self.error is None


@dataclass
class ReasoningStep:
    """A single step in the agent's reasoning process.

    Each step captures the agent's thought, the action it decided
    to take (if any), the tool call (if any), and the observation
    from the tool result or LLM response.
    """

    step_number: int
    """Sequential step number (1-based)."""

    thought: str = ""
    """The agent's reasoning at this step."""

    action: str | None = None
    """The action decided (tool name or 'respond')."""

    tool_call: ToolExecutionRecord | None = None
    """Tool call details (if action was a tool call)."""

    observation: str | None = None
    """Result of the action — tool output or final response."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    """When this step occurred."""


__all__ = [
    "AgentResponse",
    "ReasoningStep",
    "ToolExecutionRecord",
]
