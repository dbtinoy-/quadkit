"""Agent delegation utilities.

Provides adapters for exposing agents as tools, enabling hierarchical
multi-agent delegation within any reasoning strategy.
"""

from __future__ import annotations

from quadkit.ai.agents.delegation.agent_tool import AgentAsToolAdapter

__all__ = ["AgentAsToolAdapter"]
