"""MCP adapters for integrating with other Quadkit components."""

from __future__ import annotations

from quadkit.ai.mcp.adapters.skill_adapter import SkillToolAdapter
from quadkit.ai.mcp.adapters.tool_adapter import ToolRegistryAdapter

__all__ = ["SkillToolAdapter", "ToolRegistryAdapter"]
