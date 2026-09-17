"""Agent contracts for the Quadkit framework.

Exceptions, types, and protocols for agents, tools, and strategies.
"""

from __future__ import annotations

from quadkit.contracts.ai.agents.exceptions import AgentError as AgentError
from quadkit.contracts.ai.agents.exceptions import StrategyError as StrategyError
from quadkit.contracts.ai.agents.exceptions import ToolError as ToolError
from quadkit.contracts.ai.agents.protocols import (
    AgentExecutorProtocol as AgentExecutorProtocol,
)
from quadkit.contracts.ai.agents.protocols import AgentProtocol as AgentProtocol
from quadkit.contracts.ai.agents.protocols import (
    AgentStrategyProtocol as AgentStrategyProtocol,
)
from quadkit.contracts.ai.agents.protocols import MemoryProtocol as MemoryProtocol
from quadkit.contracts.ai.agents.protocols import (
    RunnableAgentProtocol as RunnableAgentProtocol,
)
from quadkit.contracts.ai.agents.protocols import (
    SkillComposerProtocol as SkillComposerProtocol,
)
from quadkit.contracts.ai.agents.protocols import StrategyProtocol as StrategyProtocol
from quadkit.contracts.ai.agents.protocols import ToolProtocol as ToolProtocol
from quadkit.contracts.ai.agents.protocols import (
    ToolRegistryProtocol as ToolRegistryProtocol,
)
from quadkit.contracts.ai.agents.types import AgentEvent as AgentEvent
from quadkit.contracts.ai.agents.types import AgentEventType as AgentEventType
from quadkit.contracts.ai.agents.types import (
    AgentExecutionContext as AgentExecutionContext,
)
from quadkit.contracts.ai.agents.types import AgentResponse as AgentResponse
from quadkit.contracts.ai.agents.types import ToolDefinition as ToolDefinition
from quadkit.contracts.ai.agents.types import ToolResult as ToolResult

__all__ = [
    "AgentError",
    "AgentEvent",
    "AgentEventType",
    "AgentExecutionContext",
    "AgentExecutorProtocol",
    "AgentProtocol",
    "AgentResponse",
    "AgentStrategyProtocol",
    "MemoryProtocol",
    "RunnableAgentProtocol",
    "SkillComposerProtocol",
    "StrategyError",
    "StrategyProtocol",
    "ToolDefinition",
    "ToolError",
    "ToolProtocol",
    "ToolRegistryProtocol",
    "ToolResult",
]
