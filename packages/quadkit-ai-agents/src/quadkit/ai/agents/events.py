"""Domain events for quadkit-ai-agents — immutable facts emitted when agent operations complete.

These events are published through EventBusProtocol and consumed by
audit, analytics, cost tracking, and safety review systems.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent

__all__ = [
    "AgentRunCompletedEvent",
    "ToolExecutionCompletedEvent",
]


@dataclass(frozen=True, init=False)
class AgentRunCompletedEvent(DomainEvent):
    """Emitted when an agent run finishes (success or failure).

    Consumed by: audit, analytics, cost tracking, safety review.
    """

    agent_id: str
    run_id: str
    tool_calls_count: int
    success: bool


@dataclass(frozen=True, init=False)
class ToolExecutionCompletedEvent(DomainEvent):
    """Emitted when a tool call within an agent run completes.

    Consumed by: analytics, tool usage monitoring, safety review.
    """

    tool_name: str
    agent_id: str
    success: bool
