"""Root hook payload surface for quadkit-ai-agents.

Defines canonical payload dataclasses for agent-lifecycle hook points. Actual
hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "AgentCompletedHook",
    "AgentStartedHook",
    "AgentToolCalledHook",
]


@dataclass(frozen=True, kw_only=True)
class AgentStartedHook:
    """Payload fired when an agent begins executing a run.

    Attributes:
        agent_name: Name of the agent that started (e.g. ``"order_agent"``).
    """

    agent_name: str


@dataclass(frozen=True, kw_only=True)
class AgentCompletedHook:
    """Payload fired when an agent finishes a run (success or error).

    Attributes:
        agent_name: Name of the agent that completed its run.
    """

    agent_name: str


@dataclass(frozen=True, kw_only=True)
class AgentToolCalledHook:
    """Payload fired each time an agent dispatches a tool call.

    Attributes:
        agent_name: Name of the agent that issued the tool call.
        tool_name: Name of the tool that was called.
    """

    agent_name: str
    tool_name: str
