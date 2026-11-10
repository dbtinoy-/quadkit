"""Tools module for agent tools."""
from __future__ import annotations

from quadkit.ai.agents.tools.base import AbstractTool
from quadkit.ai.agents.tools.decorator import tool
from quadkit.ai.agents.tools.registry import ToolRegistryImpl
from quadkit.ai.agents.tools.schema import generate_json_schema

ToolBase = AbstractTool

__all__ = [
    "AbstractTool",
    "ToolBase",
    "ToolRegistryImpl",
    "generate_json_schema",
    "tool",
]
